from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.database.connection import get_db

from app.schemas.team import (
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    TeamMemberResponse,
    UserTeamResponse
)

from app.services.team_service import TeamService


router = APIRouter(
    prefix="/teams",
    tags=["Teams"]
)


@router.post(
    "",
    response_model=TeamResponse,
    status_code=201
)
@router.post(
    "/",
    response_model=TeamResponse,
    status_code=201
)
def create_team(
    team: TeamCreate,
    db: Session = Depends(get_db)
):
    return TeamService.create_team(db, team)


@router.get(
    "",
    response_model=List[TeamResponse]
)
@router.get(
    "/",
    response_model=List[TeamResponse]
)
def get_all_teams(
    db: Session = Depends(get_db)
):
    return TeamService.get_all_teams(db)


@router.get(
    "/assignable-employees",
    response_model=List[Dict[str, Any]]
)
def get_assignable_employees(
    db: Session = Depends(get_db)
):
    """Returns active users for team member selection."""
    return TeamService.get_active_employees_for_assignment(db)


@router.get(
    "/my-team",
    response_model=UserTeamResponse
)
def get_my_team(
    user_id: Optional[int] = Query(None),
    employee_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Returns the team info and team members for the requested employee."""
    return TeamService.get_my_team(db, user_id=user_id, employee_id=employee_id)


@router.get(
    "/user/{user_id}",
    response_model=UserTeamResponse
)
def get_team_by_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Returns team information for a given user ID."""
    return TeamService.get_my_team(db, user_id=user_id)


@router.get(
    "/{team_id}",
    response_model=TeamResponse
)
def get_team(
    team_id: int,
    db: Session = Depends(get_db)
):
    return TeamService.get_team(db, team_id)


@router.get(
    "/{team_id}/employees",
    response_model=List[TeamMemberResponse]
)
def get_team_employees(
    team_id: int,
    db: Session = Depends(get_db)
):
    return TeamService.get_team_employees(db, team_id)


@router.put(
    "/{team_id}",
    response_model=TeamResponse
)
def update_team(
    team_id: int,
    team: TeamUpdate,
    db: Session = Depends(get_db)
):
    return TeamService.update_team(
        db,
        team_id,
        team
    )


@router.delete(
    "/{team_id}"
)
def delete_team(
    team_id: int,
    db: Session = Depends(get_db)
):
    return TeamService.delete_team(
        db,
        team_id
    )