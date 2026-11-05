"""مقادیر کنترل‌شده وضعیت‌ها — مطابق سند بخش‌های ۵.۲، ۵.۳، ۵.۴، ۵.۵ و ۸.

نکته: مقدار هر عضو با نام آن یکسان است تا ذخیره‌سازی Enum در پایگاه داده شفاف باشد.
"""
from __future__ import annotations

import enum


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Complexity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ProjectStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"
    cancelled = "cancelled"


class Confidentiality(str, enum.Enum):
    internal = "internal"
    restricted = "restricted"
    secret = "secret"


class TaskStatus(str, enum.Enum):
    draft = "draft"
    assigned = "assigned"
    in_progress = "in_progress"
    ready_for_review = "ready_for_review"
    completed = "completed"
    needs_correction = "needs_correction"
    blocked = "blocked"
    cancelled = "cancelled"


class ActivityType(str, enum.Enum):
    execution = "execution"
    analysis = "analysis"
    meeting = "meeting"
    coordination = "coordination"
    documentation = "documentation"
    fix = "fix"
    training = "training"
    support = "support"
    other = "other"


class ReportStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    in_review = "in_review"
    approved = "approved"
    needs_correction = "needs_correction"


class ReviewActionType(str, enum.Enum):
    approve = "approve"
    request_correction = "request_correction"
    comment = "comment"


class BlockerType(str, enum.Enum):
    info_missing = "info_missing"
    inter_unit_dependency = "inter_unit_dependency"
    resource_shortage = "resource_shortage"
    awaiting_decision = "awaiting_decision"
    technical_issue = "technical_issue"
    priority_change = "priority_change"
    external_factor = "external_factor"
    other = "other"


class BlockerStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    cancelled = "cancelled"


class RiskStatus(str, enum.Enum):
    open = "open"
    mitigated = "mitigated"
    occurred = "occurred"
    closed = "closed"


class DocumentStatus(str, enum.Enum):
    quarantined = "quarantined"
    ready = "ready"
    rejected = "rejected"


class DeliverableStatus(str, enum.Enum):
    pending = "pending"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class OutboxStatus(str, enum.Enum):
    pending = "pending"
    processed = "processed"
    failed = "failed"


class ChangeRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
