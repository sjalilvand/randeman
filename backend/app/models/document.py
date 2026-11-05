"""مستندات: قرنطینه، اسکن، نسخه‌بندی و پیوند امن به رکوردها (سند ۵.۶)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, UTCDateTime
from app.models.enums import Confidentiality, DocumentStatus


class Document(Base, IdMixin, TimestampMixin):
    __tablename__ = "documents"

    group_uuid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)  # گروه نسخه‌ها
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)  # نام تصادفی، مستقل از نام اصلی
    extension: Mapped[str] = mapped_column(String(12), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidentiality: Mapped[Confidentiality] = mapped_column(Enum(Confidentiality), nullable=False, default=Confidentiality.internal)

    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.quarantined, index=True)
    scan_result: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    replaced_document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("documents.id"), nullable=True)


class DocumentLink(Base, IdMixin):
    """پیوند دارای کلید خارجی معتبر — در سرویس، وجود نوع و شناسه کنترل می‌شود (سند ۱۰.۶)."""

    __tablename__ = "document_links"

    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)  # task | project | blocker | weekly_report
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
