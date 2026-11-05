"""مستندات: دریافت → قرنطینه → اعتبارسنجی → اسکن → آماده/رد (سند ۵.۶).

- نام ذخیره تصادفی و مستقل از نام اصلی
- محل ذخیره خارج از مسیر عمومی وب
- اگر سرویس اسکن در دسترس نباشد، فایل در قرنطینه می‌ماند و قابل دانلود نیست
"""
from __future__ import annotations

import hashlib
import socket
import struct
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session as OrmSession

from app.core.config import settings
from app.models.base import utcnow
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.user import User

_MAGIC = {
    "pdf": b"%PDF",
    "png": b"\x89PNG",
    "jpg": b"\xff\xd8",
    "jpeg": b"\xff\xd8",
    "zip": b"PK\x03\x04",  # docx/xlsx/pptx بسته ZIP هستند
}


def ensure_dirs() -> None:
    for p in (settings.documents_dir, settings.quarantine_dir, settings.exports_dir):
        Path(p).mkdir(parents=True, exist_ok=True)


def validate_upload(*, filename: str, size: int, head: bytes) -> str:
    """بررسی پسوند، حجم و امضای محتوا — خروجی: پسوند."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_ext_list():
        raise HTTPException(status_code=422, detail=f"پسوند «{ext or 'نامشخص'}» مجاز نیست")
    if size > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"حجم فایل بیش از {settings.max_upload_mb} مگابایت است")
    if size == 0:
        raise HTTPException(status_code=422, detail="فایل خالی است")
    magic_ok = False
    for sig in _MAGIC.values():
        if head.startswith(sig):
            magic_ok = True
            break
    if not magic_ok:
        try:
            head.decode("utf-8")
            magic_ok = True  # متن ساده
        except UnicodeDecodeError:
            magic_ok = False
    if not magic_ok:
        raise HTTPException(status_code=422, detail="ساختار فایل با پسوند اعلام‌شده سازگار نیست")
    return ext


async def save_to_quarantine(db: OrmSession, *, file: UploadFile, user: User) -> Document:
    """دریافت جریانی به فایل موقت — بارگذاری کامل در حافظه انجام نمی‌شود."""
    ensure_dirs()
    original = Path(file.filename or "بدون-نام").name
    stored = uuid.uuid4().hex
    tmp_path = Path(settings.quarantine_dir) / stored
    sha = hashlib.sha256()
    size = 0
    head = b""
    with tmp_path.open("wb") as out:
        while chunk := await file.read(1024 * 512):
            size += len(chunk)
            if size > settings.max_upload_mb * 1024 * 1024:
                out.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=422, detail=f"حجم فایل بیش از {settings.max_upload_mb} مگابایت است")
            if len(head) < 16:
                head += chunk
            sha.update(chunk)
            out.write(chunk)
    ext = validate_upload(filename=original, size=size, head=head[:16])

    doc = Document(
        group_uuid=uuid.uuid4(),
        version=1,
        original_name=original[:255],
        stored_name=stored,
        extension=ext,
        size_bytes=size,
        sha256=sha.hexdigest(),
        title=(file.title if hasattr(file, "title") else None) or original,  # توسط فراخوان به‌روزرسانی می‌شود
        status=DocumentStatus.quarantined,
        uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()
    return doc


def add_version(db: OrmSession, *, base: Document, new_stored: str, size: int, sha: str, user: User) -> Document:
    last = db.query(Document).filter(Document.group_uuid == base.group_uuid).order_by(Document.version.desc()).first()
    doc = Document(
        group_uuid=base.group_uuid,
        version=(int(last.version) + 1) if last else base.version + 1,
        original_name=base.original_name,
        stored_name=new_stored,
        extension=base.extension,
        size_bytes=size,
        sha256=sha,
        title=base.title,
        description=base.description,
        category=base.category,
        confidentiality=base.confidentiality,
        status=DocumentStatus.quarantined,
        uploaded_by=user.id,
        replaced_document_id=base.id,
    )
    db.add(doc)
    db.flush()
    return doc


def clamd_scan(path: Path) -> tuple[bool, str]:
    """اسکن با clamd روی پورت 3310 (INSTREAM). خطا ⇒ در دسترس نیست."""
    if not settings.clamd_host:
        return False, "سرویس اسکن در دسترس نیست: clamd پیکربندی نشده است"
    try:
        with socket.create_connection((settings.clamd_host, settings.clamd_port), timeout=settings.clamd_timeout) as s:
            s.sendall(b"zINSTREAM\0")
            with path.open("rb") as f:
                while chunk := f.read(8192):
                    s.sendall(struct.pack("!I", len(chunk)) + chunk)
            s.sendall(struct.pack("!I", 0))
            resp = s.recv(4096).decode(errors="ignore").strip("\x00").strip()
    except (OSError, socket.timeout) as exc:
        return False, f"سرویس اسکن در دسترس نیست: {exc}"
    ok = resp.upper().endswith("OK")
    return ok, resp


def finalize_scan(db: OrmSession, *, document_id: uuid.UUID) -> str:
    """توسط Worker اجرا می‌شود؛ نتیجه: ready | rejected | quarantined(ماندن)."""
    doc = db.get(Document, document_id)
    if doc is None:
        return "missing"
    qpath = Path(settings.quarantine_dir) / doc.stored_name
    if not qpath.exists():
        doc.scan_result = "فایل در قرنطینه یافت نشد"
        doc.status = DocumentStatus.rejected
        db.commit()
        return "rejected"
    ok, resp = clamd_scan(qpath)
    doc.scanned_at = utcnow()
    doc.scan_result = resp[:255]
    if ok:
        final = Path(settings.documents_dir) / doc.stored_name
        final.parent.mkdir(parents=True, exist_ok=True)
        qpath.replace(final)
        doc.status = DocumentStatus.ready
        db.commit()
        return "ready"
    if "در دسترس نیست" in resp:
        db.commit()
        return "quarantined"  # سرویس اسکن در دسترس نیست ⇒ فایل می‌ماند و قابل دانلود نمی‌شود
    doc.status = DocumentStatus.rejected
    db.commit()
    return "rejected"


def file_path_for(doc: Document) -> Path:
    base = Path(settings.documents_dir) if doc.status == DocumentStatus.ready else Path(settings.quarantine_dir)
    return base / doc.stored_name


def group_documents(db: OrmSession, group_uuid: uuid.UUID) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.group_uuid == group_uuid)
        .order_by(Document.version.desc())
        .all()
    )
