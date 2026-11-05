"""مهاجرت اولیه — ایجاد کامل ساختار مطابق مدل‌ها

Revision ID: 0001
Revises:
Create Date: 2026-11-06
"""
from alembic import op

from app.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ساختار اولیه از متادیتای مدل‌ها ساخته می‌شود تا مدل و پایگاه همیشه هم‌خوان باشند.
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
