"""نقطه ورود FastAPI — راندمان (سند ۹ و ۱۱.۳)."""
from __future__ import annotations

import logging
import time
import uuid as _uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from app.api.v1.deps import MUTATING_METHODS
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.models.calendar import SystemSetting
from app.models.enums import JobStatus
from app.models.ops import BackgroundJob
from app.models.base import utcnow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("randeman")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("سامانه راندمان آماده شد — env=%s", settings.env)
    yield
    engine.dispose()


def create_app() -> FastAPI:
    docs_url = "/docs" if settings.docs_enabled else None
    openapi_url = "/openapi.json" if settings.docs_enabled else None
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_subtitle,
        version="1.0.0",
        docs_url=docs_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.trusted_proxies = {p.strip() for p in settings.trusted_proxies.split(",") if p.strip()}

    @app.middleware("http")
    async def request_guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = _uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        started = time.perf_counter()
        # CSRF: سربرگ سفارشی برای عملیات تغییردهنده
        if request.method in MUTATING_METHODS and request.headers.get("x-requested-with") != "XMLHttpRequest":
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "csrf_required", "message": "درخواست بدون نشان CSRF", "request_id": request_id}},
            )
        response = await call_next(request)
        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        logger.info("%s %s -> %s (%.0fms) rid=%s", request.method, request.url.path, response.status_code, elapsed, request_id)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):  # type: ignore[no-untyped-def]
        rid = getattr(request.state, "request_id", "")
        return JSONResponse(status_code=422, content={"error": {
            "code": "validation_error", "message": "ورودی نامعتبر است", "request_id": rid,
            "details": [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()[:8]],
        }})

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):  # type: ignore[no-untyped-def]
        rid = getattr(request.state, "request_id", "")
        logger.exception("خطای غیرمنتظره rid=%s: %s", rid, exc)
        return JSONResponse(status_code=500, content={"error": {
            "code": "internal_error", "message": "خطای داخلی — با پشتیبانی تماس بگیرید", "request_id": rid,
        }})

    app.include_router(api_router)

    @app.get("/healthz", tags=["health"], include_in_schema=True)
    def healthz() -> dict:
        """زنده‌بودن — بدون جزئیات حساس."""
        return {"status": "ok", "app": settings.app_name}

    @app.get("/readyz", tags=["health"])
    def readyz() -> JSONResponse:
        """آمادگی: پایگاه داده، ضربان Worker و در دسترس بودن ClamAV — سند ۱۷ و تصمیم ۲۵.۲."""
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
                hb = db.get(SystemSetting, "worker_heartbeat")
                pending = int(db.scalar(select(func.count()).select_from(BackgroundJob).where(
                    BackgroundJob.status == JobStatus.pending)) or 0)
        except Exception:
            return JSONResponse(status_code=503, content={"status": "db_unavailable"})
        heartbeat = hb.value if hb else None
        worker_ok = False
        if isinstance(heartbeat, str):
            from datetime import datetime

            try:
                worker_ok = (utcnow() - datetime.fromisoformat(heartbeat)).total_seconds() < settings.worker_heartbeat_seconds * 3
            except ValueError:
                worker_ok = False
        # آزمون ClamAV پورت 3310 — نبود clamd مانع آماده‌سازی نیست؛ اسکن به قرنطینه منتقل می‌شود
        from app.services.document_service import clamd_ping

        clam_ok, clam_msg = clamd_ping()
        return JSONResponse(content={"status": "ok" if worker_ok else "degraded",
                                     "worker_heartbeat": heartbeat, "worker_alive": worker_ok,
                                     "pending_jobs": pending,
                                     "clamav": {"available": clam_ok, "host": settings.clamd_host,
                                                "port": settings.clamd_port, "message": clam_msg}})

    from starlette.middleware.cors import CORSMiddleware

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    # ارائه رابط ساخته‌شده از همان پورت — حالت تک‌پورت (پورت 8095؛ تصمیم ۲۵.۲)
    # استقرار عملیاتی کماکان Nginx 8087 است؛ این حالت برای راه‌اندازی سریع و آزمون است.
    if settings.serve_dist_dir:
        from pathlib import Path as _Path

        from fastapi.staticfiles import StaticFiles
        from starlette.responses import FileResponse

        _dist = _Path(settings.serve_dist_dir).resolve()
        if _dist.is_dir():
            _assets = _dist / "assets"
            if _assets.is_dir():
                app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

            @app.get("/{full_path:path}", include_in_schema=False,
                     summary="رابط کاربری (فایل‌های ساخته‌شده React)")
            def spa(full_path: str) -> Response:
                """فایل استاتیک یا index.html برای مسیرهای SPA."""
                if full_path.startswith(("api/", "docs", "openapi.json")):
                    return JSONResponse(status_code=404, content={"error": {"code": "not_found",
                                                                            "message": "مسیر یافت نشد"}})
                candidate = (_dist / full_path).resolve()
                if full_path and candidate.is_file() and str(candidate).startswith(str(_dist)):
                    return FileResponse(candidate)
                return FileResponse(_dist / "index.html")

            logger.info("حالت تک‌پورت فعال شد — رابط از %s ارائه می‌شود", _dist)

    return app


app = create_app()
