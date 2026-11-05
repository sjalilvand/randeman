"""مستندات: بارگذاری امن، نسخه‌بندی و دانلود کنترل‌شده (سند ۵.۶)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.permissions import has_role
from app.models.document import Document, DocumentLink
from app.models.enums import DocumentStatus
from app.models.ops import BackgroundJob
from app.models.user import User
from app.services import document_service
from app.services.audit_svc import audit

router = APIRouter(prefix="/documents", tags=["documents"])

ENTITY_TYPES = {"task", "project", "blocker", "weekly_report"}


async def _store(
    db: OrmSession, file: UploadFile, user: User, *, title: str | None, description: str | None,
    category: str | None, confidentiality: str, entity_type: str | None, entity_id: uuid.UUID | None,
) -> Document:
    doc = await document_service.save_to_quarantine(db, file=file, user=user)
    doc.title = (title or doc.title)[:250]
    doc.description = description
    doc.category = category
    from app.models.enums import Confidentiality

    doc.confidentiality = Confidentiality(confidentiality)
    if entity_type or entity_id:
        if not entity_type or not entity_id or entity_type not in ENTITY_TYPES:
            raise HTTPException(422, "پیوند رکورد نامعتبر است")
        from app.models.ops import Blocker
        from app.models.project import Project
        from app.models.report import WeeklyReport
        from app.models.task import Task

        model = {"task": Task, "project": Project, "blocker": Blocker, "weekly_report": WeeklyReport}[entity_type]
        if db.get(model, entity_id) is None:
            raise HTTPException(404, f"رکورد مقصد {entity_type} یافت نشد")
        db.add(DocumentLink(document_id=doc.id, entity_type=entity_type, entity_id=entity_id, created_by=user.id))
    db.add(BackgroundJob(type="scan_document", payload={"document_id": str(doc.id)}))
    db.flush()
    return doc


def _payload(db: OrmSession, d: Document) -> dict:
    uploader = db.get(User, d.uploaded_by)
    links = db.execute(select(DocumentLink).where(DocumentLink.document_id == d.id)).scalars().all()
    return {
        "id": str(d.id), "group_uuid": str(d.group_uuid), "version": int(d.version),
        "original_name": d.original_name, "title": d.title, "description": d.description,
        "category": d.category, "extension": d.extension,
        "size_bytes": d.size_bytes, "confidentiality": d.confidentiality.value,
        "status": d.status.value, "scan_result": d.scan_result,
        "uploaded_by": str(d.uploaded_by), "uploader_name": uploader.full_name if uploader else "—",
        "created_at": d.created_at.isoformat(),
        "links": [{"entity_type": l.entity_type, "entity_id": str(l.entity_id)} for l in links],
    }


@router.post("", status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    category: str | None = Form(default=None),
    confidentiality: str = Form(default="internal"),
    entity_type: str | None = Form(default=None),
    entity_id: str | None = Form(default=None),
    actor: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
) -> dict:
    eid = uuid.UUID(str(entity_id)) if entity_id else None
    doc = await _store(db, file, actor, title=title, description=description, category=category,
                       confidentiality=confidentiality, entity_type=entity_type, entity_id=eid)
    audit(db, actor_id=actor.id, action="document_uploaded", entity_type="document", entity_id=doc.id,
          summary=f"بارگذاری {doc.original_name} — قرنطینه تا اسکن",
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, doc)


@router.post("/{document_id}/versions", status_code=201)
async def upload_new_version(
    document_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    note: str | None = Form(default=None),
    actor: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
) -> dict:
    base = db.get(Document, document_id)
    if base is None:
        raise HTTPException(404, "مستند یافت نشد")
    if base.uploaded_by != actor.id and not has_role(db, actor, "senior_manager", "pmo"):
        raise HTTPException(403, "مجوز افزودن نسخه ندارید")
    doc = await document_service.save_to_quarantine(db, file=file, user=actor)
    new_doc = document_service.add_version(
        db, base=base, new_stored=doc.stored_name, size=doc.size_bytes, sha=doc.sha256 or "", user=actor
    )
    new_doc.title, new_doc.description, new_doc.category = base.title, base.description, base.category
    new_doc.confidentiality = base.confidentiality
    for link in db.execute(select(DocumentLink).where(DocumentLink.document_id == base.id)).scalars().all():
        db.add(DocumentLink(document_id=new_doc.id, entity_type=link.entity_type, entity_id=link.entity_id, created_by=actor.id))
    db.add(BackgroundJob(type="scan_document", payload={"document_id": str(new_doc.id)}))
    audit(db, actor_id=actor.id, action="document_version_added", entity_type="document", entity_id=new_doc.id,
          summary=f"نسخه {int(new_doc.version)} از {base.title}", detail={"note": note},
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, new_doc)


@router.get("")
def list_documents(
    entity_type: str | None = None, entity_id: uuid.UUID | None = None, q: str | None = None,
    page: int = 1, size: int = 20,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    conds = []
    if not has_role(db, actor, "senior_manager", "pmo", "auditor", "observer", "sys_admin"):
        conds.append(or_(Document.uploaded_by == actor.id))
    if entity_type and entity_id:
        conds.append(Document.id.in_(
            select(DocumentLink.document_id).where(DocumentLink.entity_type == entity_type, DocumentLink.entity_id == entity_id)
        ))
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(Document.title.ilike(like), Document.original_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(Document).where(*conds)) or 0
    rows = db.execute(select(Document).where(*conds).order_by(Document.created_at.desc())
                      .offset((page - 1) * size).limit(size)).scalars().all()
    return {"items": [_payload(db, d) for d in rows], "total": int(total), "page": page, "size": size}


@router.get("/{document_id}")
def get_document(document_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    d = db.get(Document, document_id)
    if d is None:
        raise HTTPException(404, "مستند یافت نشد")
    allowed = d.uploaded_by == actor.id or has_role(db, actor, "senior_manager", "pmo", "auditor", "observer", "sys_admin")
    if not allowed:
        links = db.execute(select(DocumentLink).where(DocumentLink.document_id == d.id)).scalars().all()
        allowed = len(links) > 0 and _linked_visible(db, actor, links)
    if not allowed:
        raise HTTPException(404, "مستند یافت نشد")
    return _payload(db, d)


def _linked_visible(db: OrmSession, actor: User, links) -> bool:  # noqa: ANN001
    from app.core.permissions import can_view_project, can_view_task
    from app.models.project import Project
    from app.models.task import Task

    for l in links:
        if l.entity_type == "task":
            t = db.get(Task, l.entity_id)
            if t and can_view_task(db, actor, t):
                return True
        elif l.entity_type == "project":
            p = db.get(Project, l.entity_id)
            if p and can_view_project(db, actor, p):
                return True
    return False


@router.get("/{document_id}/download")
def download(document_id: uuid.UUID, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)):
    d = db.get(Document, document_id)
    if d is None:
        raise HTTPException(404, "مستند یافت نشد")
    allowed = d.uploaded_by == actor.id or has_role(db, actor, "senior_manager", "pmo", "auditor", "observer", "sys_admin")
    if not allowed:
        links = db.execute(select(DocumentLink).where(DocumentLink.document_id == d.id)).scalars().all()
        allowed = len(links) > 0 and _linked_visible(db, actor, links)
    if not allowed:
        raise HTTPException(404, "مستند یافت نشد")  # کنترل مستقل مجوز برای فایل (AC-07)
    if d.status != DocumentStatus.ready:
        raise HTTPException(423, "فایل هنوز در قرنطینه است یا رد شده و قابل دانلود نیست (AC-16)")
    path = document_service.file_path_for(d)
    if not path.exists():
        raise HTTPException(404, "فایل فیزیکی یافت نشد")
    audit(db, actor_id=actor.id, action="document_downloaded", entity_type="document", entity_id=d.id,
          summary=f"دانلود {d.original_name}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    return FileResponse(path, filename=d.original_name, media_type="application/octet-stream")
