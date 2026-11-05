"""Test worker claim/finalize — scan job on quarantined file stays quarantined."""
import io
import uuid
from pathlib import Path

from app.core.config import settings
from app.models.document import Document
from app.models.enums import DocumentStatus, JobStatus
from app.models.ops import BackgroundJob
from app.worker import claim_job, handle_job


def test_worker_claims_and_scans(db):
    """AC-17 — اجرای مجدد کار پس‌زمینه بدون اثر تکراری؛ AC-16 — بدون clamd ماندن در قرنطینه."""
    # فایل در قرنطینه (بدون پیکربندی clamd)
    qdir = Path(settings.quarantine_dir)
    qdir.mkdir(parents=True, exist_ok=True)
    stored = uuid.uuid4().hex
    (qdir / stored).write_bytes(b"%PDF-1.7 test scan content")

    doc = Document(
        group_uuid=uuid.uuid4(), version=1, original_name="test.pdf", stored_name=stored,
        extension="pdf", size_bytes=24, title="تست اسکن", status=DocumentStatus.quarantined,
    )
    from tests.conftest import make_user

    user = make_user(db, "worker-emp", "employee")
    doc.uploaded_by = user.id
    db.add(doc)
    db.flush()

    job = BackgroundJob(type="scan_document", payload={"document_id": str(doc.id)})
    # صف کارهای تست‌های قبلی خالی شود تا همین کار برداشت شود
    db.query(BackgroundJob).filter(BackgroundJob.status == JobStatus.pending).delete()
    db.add(job)
    db.commit()

    claimed = claim_job(db)
    assert claimed is not None
    assert claimed.status == JobStatus.running
    assert claimed.leased_by is not None

    handle_job(db, claimed)
    db.refresh(doc)
    # بدون clamd پیکربندی‌شده: فایل در قرنطینه می‌ماند
    assert doc.status == DocumentStatus.quarantined
    assert "در دسترس نیست" in (doc.scan_result or "")


def test_outbox_processed(db):
    from app.services.notify import notify, process_outbox

    from app.models.enums import OutboxStatus
    from app.models.ops import OutboxEvent

    from tests.conftest import make_user

    user = make_user(db, "worker-outbox", "employee")
    notify(db, user_id=user.id, type="test.event", title="رویداد آزمون")
    db.commit()
    count = process_outbox(db)
    assert count >= 1
    remaining = db.query(OutboxEvent).filter(OutboxEvent.status == OutboxStatus.pending).count()
    assert remaining == 0
