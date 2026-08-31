from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.replay import ReplayCreate, ReplayResponse
from app.services.replay_service import ReplayService

router = APIRouter(
    prefix="/replays",
    tags=["Replays"]
)


@router.post(
    "",
    response_model=ReplayResponse
)
@router.post(
    "/",
    response_model=ReplayResponse
)
def create_replay(
    replay: ReplayCreate,
    db: Session = Depends(get_db)
):
    return ReplayService.create_replay(
        db,
        replay
    )


@router.get(
    "",
    response_model=list[ReplayResponse]
)
@router.get(
    "/",
    response_model=list[ReplayResponse]
)
def get_all_replays(
    db: Session = Depends(get_db)
):
    return ReplayService.get_all_replays(db)


@router.get(
    "/{decision_id}",
    response_model=list[ReplayResponse]
)
def get_replay_by_decision(
    decision_id: int,
    db: Session = Depends(get_db)
):
    return ReplayService.get_by_decision(
        db,
        decision_id
    )