from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get(
    "",
    response_model=DashboardResponse
)
@router.get(
    "/",
    response_model=DashboardResponse
)
@router.get(
    "/{user_id}",
    response_model=DashboardResponse
)
def get_dashboard(
    user_id: int = 1,
    db: Session = Depends(get_db)
):
    return DashboardService.get_dashboard(db, user_id)