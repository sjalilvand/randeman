"""تجمیع روترهای API نسخه ۱ (سند ۱۱.۱)."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    activities, audit, auth, blockers, dashboards, documents, jobs, notifications,
    org, projects, reports, settings, tasks, users, weekly_reports,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(org.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(activities.router)
api_router.include_router(weekly_reports.router)
api_router.include_router(documents.router)
api_router.include_router(blockers.router)
api_router.include_router(notifications.router)
api_router.include_router(dashboards.router)
api_router.include_router(reports.router)
api_router.include_router(audit.router)
api_router.include_router(settings.router)
api_router.include_router(jobs.router)
