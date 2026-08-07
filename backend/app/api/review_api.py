from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.review import (
    ReviewCreate,
    ReviewResponse
)
from app.services.review_service import ReviewService

router = APIRouter(
    prefix="/reviews",
    tags=["Reviews"]
)


@router.post(
    "/",
    response_model=ReviewResponse
)
def create_review(
    review: ReviewCreate,
    db: Session = Depends(get_db)
):
    return ReviewService.create_review(
        db,
        review
    )


@router.get(
    "/",
    response_model=List[ReviewResponse]
)
def get_all_reviews(
    user_id: int = None,
    db: Session = Depends(get_db)
):
    return ReviewService.get_all_reviews(db, user_id=user_id)


@router.get(
    "/{decision_id}",
    response_model=List[ReviewResponse]
)
def get_reviews_by_decision(
    decision_id: int,
    db: Session = Depends(get_db)
):
    return ReviewService.get_reviews_by_decision(
        db,
        decision_id
    )