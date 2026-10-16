from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import QUEBETError
from app.core.logging import configure_logging
from app.core.neo4j_client import close_neo4j_client
from app.core.redis_client import close_redis_client
from app.core.vector_store import close_vector_store
from app.middleware.tracing import TracingMiddleware

# Initialize production structured logging
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan setup and teardown."""
    # Database schema is managed strictly via Alembic migrations (alembic upgrade head).
    logger.info("QUEBET AI Backend Core initializing...")
    yield
    # Cleanup resources on shutdown
    logger.info("Closing backend resources...")
    await close_redis_client()
    await close_neo4j_client()
    await close_vector_store()
    await engine.dispose()
    logger.info("QUEBET AI Backend Core shutdown complete.")


def create_application() -> FastAPI:
    """FastAPI Application Factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Middleware Stack (Execution order is bottom-up: Tracing -> CORS -> Routing)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TracingMiddleware)

    # Exception Handlers
    @app.exception_handler(QUEBETError)
    async def quebet_error_handler(request: Request, exc: QUEBETError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": exc.detail,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # Server-side structured logging sanitizes secrets and logs full diagnostic info
        logger.exception("Unhandled server exception: %s", str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred. Please contact support.",
                    "details": {},
                },
            },
        )

    # Root probe
    @app.get("/")
    async def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "online",
            "docs": f"{settings.API_V1_STR}/docs",
        }

    # Mount v1 routes
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_application()
