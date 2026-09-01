# Expert Decision Replay Platform Main Entry
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.base import Base
from app.database.connection import engine

# Import all models
from app import models

# Import Routers
from app.api.user_api import router as user_router
from app.api.role_api import router as role_router
from app.api.team_api import router as team_router
from app.api import decision_api
from app.api import alternative_api
from app.api import review_api
from app.api.replay_api import router as replay_router
from app.api.dashboard_api import router as dashboard_router
from app.api.profile_api import router as profile_router
from app.api.audit_api import router as audit_router
from app.api.notification_api import router as notification_router
from app.api.upload_api import router as upload_router
from app.api.discussion_api import router as discussion_router
from app.api.settings_api import router as settings_router
from app.api.support_api import router as support_router
from app.api.email_api import router as email_router

import os
import threading

app = FastAPI(
    title="Expert Decision Replay Platform",
    version="1.0.0",
    description="A centralized platform for managing organizational decisions."
)

@app.on_event("startup")
def startup_db_init():
    def _async_init():
        try:
            Base.metadata.create_all(bind=engine)
            from app.database.connection import ensure_user_schema_columns
            ensure_user_schema_columns()
            print("[SERVER] Database schema & baseline initialization complete.")
        except Exception as db_init_err:
            print(f"[SERVER WARNING] Background database initialization note: {db_init_err}")

    threading.Thread(target=_async_init, daemon=True).start()

allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000").split(",")
allowed_origins = [orig.strip() for orig in allowed_origins if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(role_router)
app.include_router(upload_router)
app.include_router(team_router)
app.include_router(user_router)
app.include_router(decision_api.router)
app.include_router(alternative_api.router)
app.include_router(review_api.router)
app.include_router(replay_router)
app.include_router(dashboard_router)
app.include_router(profile_router)
app.include_router(audit_router)
app.include_router(notification_router)
app.include_router(discussion_router)
app.include_router(settings_router)
app.include_router(support_router)
app.include_router(email_router)

@app.get("/")
@app.get("/health")
@app.get("/ping")
def home():
    return {
        "status": "healthy",
        "message": "Expert Decision Replay Platform API is Running"
    }