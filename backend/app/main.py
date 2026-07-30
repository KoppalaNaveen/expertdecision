from fastapi import FastAPI

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

# Create all database tables
Base.metadata.create_all(bind=engine)

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Expert Decision Replay Platform",
    version="1.0.0",
    description="A centralized platform for managing organizational decisions."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(role_router)
from app.api import upload_api
app.include_router(upload_api.router)
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
from app.api import discussion_api
app.include_router(discussion_api.router)
from app.api import settings_api
from app.api import support_api

app.include_router(settings_api.router)
app.include_router(support_api.router)

@app.get("/")
def home():
    return {
        "message": "Expert Decision Replay Platform API is Running"
    }