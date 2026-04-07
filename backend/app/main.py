"""FastAPI application entry point - Hakusan Monitor API v2.2."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "内部エラーが発生しました"}},
    )


# Rate limiting note: in production, use slowapi or nginx
# from slowapi import Limiter
# limiter = Limiter(key_func=get_remote_address)

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
