from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.schemas.profile import (
    ProfileResponse,
    ProfileUpdate
)

from app.services.profile_service import ProfileService

router = APIRouter(
    prefix="/profile",
    tags=["Profile"]
)


@router.get(
    "/{user_id}",
    response_model=ProfileResponse
)
def get_profile(
    user_id: int,
    current_user_id: int = None,
    db: Session = Depends(get_db)
):

    profile = ProfileService.get_profile(db, user_id, current_user_id)

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    return profile


@router.put(
    "/{user_id}"
)
def update_profile(
    user_id: int,
    profile: ProfileUpdate,
    db: Session = Depends(get_db)
):

    response = ProfileService.update_profile(
        db,
        user_id,
        profile
    )

    if not response:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    return response