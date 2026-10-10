from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def setup_cors(app: FastAPI):
    normalized_origins = [origin.rstrip("/") for origin in settings.CORS_ORIGINS]
    local_dev_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$" if settings.DEBUG else None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=normalized_origins,
        allow_origin_regex=local_dev_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
