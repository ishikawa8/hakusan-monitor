"""FastAPI application entry point - Hakusan Monitor API v2.2."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database import init_db, close_db
from app.routers import health, public, admin, device

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting Hakusan Monitor API v2.2")

    # Create tables in development
    if settings.environment == "development":
        await init_db()
        logger.info("Database tables created (dev mode)")

    # Schedule background tasks
    from app.tasks.hourly_aggregation import aggregate_hourly
    from app.tasks.ai_worker import process_pending_images

    scheduler.add_job(aggregate_hourly, "interval", minutes=10, id="hourly_agg")
    scheduler.add_job(process_pending_images, "interval", minutes=5, id="ai_worker")
    scheduler.start()
    logger.info("Background scheduler started")

    yield

    scheduler.shutdown()
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="登山者モニタリングシステム API",
    description="白山国立公園 登山者モニタリングシステム バックエンドAPI (v2.2)",
    version="2.2.0",
    lifespan=lifespan,
)


# ---------- BUG-014 fix: DB接続エラーを確実にキャッチするミドルウェア ----------
class DBErrorCatchMiddleware(BaseHTTPMiddleware):
    """Catch DB connection errors (ConnectionRefusedError etc.) that bypass
    FastAPI's exception_handler and return a proper 500 JSON response."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(f"Middleware caught unhandled error: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "INTERNAL_ERROR", "message": "内部エラーが発生しました"}},
            )


app.add_middleware(DBErrorCatchMiddleware)


# ---------- BUG-017 fix: セキュリティヘッダー (設計書 8.3) ----------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers per design doc section 8.3."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# Global error handler (catches exceptions within FastAPI's routing layer)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "内部エラーが発生しました"}},
    )


# ---------- BUG-018 fix: レートリミット (設計書 4.1) ----------
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting enabled (slowapi)")
except ImportError:
    logger.warning(
        "slowapi not installed - rate limiting disabled. "
        "Install with: pip install slowapi"
    )

# Register routers
app.include_router(health.router)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(device.router)


@app.get("/")
async def root():
    return {
        "name": "登山者モニタリングシステム API",
        "version": "2.2.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
