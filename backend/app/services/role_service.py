from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.schemas.role import RoleCreate, RoleUpdate
from app.repositories.role_repository import RoleRepository


class RoleService:

    @staticmethod
    def get_all_roles(db: Session):
        return RoleRepository.get_all_roles(db)

    @staticmethod
    def get_role_by_id(db: Session, role_id: int):

        role = RoleRepository.get_role_by_id(db, role_id)

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        return role

    @staticmethod
    def create_role(db: Session, role: RoleCreate):

        existing_role = RoleRepository.get_role_by_name(
            db,
            role.role_name
        )

        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role already exists"
            )

        res = RoleRepository.create_role(
            db,
            role
        )
        try:
            from app.services.audit_service import AuditService
            AuditService.log_event(db, user_id=1, action=f"Created role: {role.role_name}", details=f"Description: {role.description or 'Custom role'}", module="Roles", severity="Success")
        except Exception:
            pass
        return res

    @staticmethod
    def update_role(
        db: Session,
        role_id: int,
        role: RoleUpdate
    ):

        existing_role = RoleRepository.get_role_by_id(
            db,
            role_id
        )

        if not existing_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        if role.role_name:

            duplicate = RoleRepository.get_role_by_name(
                db,
                role.role_name
            )

            if duplicate and duplicate.id != role_id:

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Role name already exists"
                )

        updated = RoleRepository.update_role(
            db,
            role_id,
            role
        )
        try:
            from app.services.audit_service import AuditService
            AuditService.log_event(db, user_id=1, action=f"Updated role: {existing_role.role_name}", details=f"Role ID: {role_id}", module="Roles", severity="Warning")
        except Exception:
            pass
        return updated

    @staticmethod
    def delete_role(
        db: Session,
        role_id: int
    ):

        existing_role = RoleRepository.get_role_by_id(
            db,
            role_id
        )

        if not existing_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        role_name = existing_role.role_name
        RoleRepository.delete_role(
            db,
            role_id
        )
        try:
            from app.services.audit_service import AuditService
            AuditService.log_event(db, user_id=1, action=f"Deleted role: {role_name}", details=f"Role ID: {role_id}", module="Roles", severity="Critical")
        except Exception:
            pass

        return {
            "message": "Role deleted successfully"
        }