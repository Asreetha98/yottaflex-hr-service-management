"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.router import api_router
from app.config import get_settings
from app.database import SessionLocal, engine
from app.exceptions import AppError
from app.models.base import Base

logger = logging.getLogger("yottaflex")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)
    if settings.auto_create_tables:
        # Import for side effects: registers every model on Base.metadata.
        import app.models  # noqa: F401

        Base.metadata.create_all(bind=engine)
    if settings.seed_reference_data:
        from app.seed import seed_all

        db = SessionLocal()
        try:
            seed_all(db, include_demo_users=settings.seed_demo_users)
        finally:
            db.close()
    logger.info("Application started (env=%s)", settings.app_env)
    yield
    logger.info("Application stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Deterministic HR service management and policy resolution platform (no runtime LLM).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
            headers=headers,
        )

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
