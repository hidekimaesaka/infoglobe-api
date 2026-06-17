from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.country_info import router as country_info_router
from app.api.routes.health import router as health_router
from app.api.routes.headlines import router as headlines_router
from app.core.config import settings
from app.middleware.rate_limit import RateLimitMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
    )
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.rate_limit_requests_per_minute,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {
            "app": "InfoGlobe",
            "message": "API FastAPI funcionando.",
            "docs": "/docs",
        }

    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(headlines_router, prefix=settings.api_prefix)
    app.include_router(country_info_router, prefix=settings.api_prefix)

    return app


app = create_app()
