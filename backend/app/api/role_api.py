from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.schemas.role import (
    RoleCreate,
    RoleUpdate,
    RoleResponse
)

from app.services.role_service import RoleService

router = APIRouter(
    prefix="/roles",
    tags=["Roles"]
)


# =====================================
# Get All Roles
# =====================================

@router.get(
    "",
    response_model=list[RoleResponse]
)
@router.get(
    "/",
    response_model=list[RoleResponse]
)
def get_all_roles(
    db: Session = Depends(get_db)
):
    return RoleService.get_all_roles(db)


# =====================================
# Get Role By ID
# =====================================

@router.get(
    "/{role_id}",
    response_model=RoleResponse
)
def get_role(
    role_id: int,
    db: Session = Depends(get_db)
):
    return RoleService.get_role_by_id(
        db,
        role_id
    )


# =====================================
# Create Role
# =====================================

@router.post(
    "",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED
)
@router.post(
    "/",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED
)
def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db)
):
    return RoleService.create_role(
        db,
        role
    )


# =====================================
# Update Role
# =====================================

@router.put(
    "/{role_id}",
    response_model=RoleResponse
)
def update_role(
    role_id: int,
    role: RoleUpdate,
    db: Session = Depends(get_db)
):
    return RoleService.update_role(
        db,
        role_id,
        role
    )


# =====================================
# Delete Role
# =====================================

@router.delete(
    "/{role_id}"
)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db)
):
    return RoleService.delete_role(
        db,
        role_id
    )