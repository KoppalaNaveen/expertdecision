from sqlalchemy.orm import Session

from app.models.role import Role
from app.schemas.role import RoleCreate, RoleUpdate


class RoleRepository:

    @staticmethod
    def get_all_roles(db: Session):
        return db.query(Role).order_by(Role.id).all()

    @staticmethod
    def get_role_by_id(db: Session, role_id: int):
        return db.query(Role).filter(Role.id == role_id).first()

    @staticmethod
    def get_role_by_name(db: Session, role_name: str):
        return (
            db.query(Role)
            .filter(Role.role_name == role_name)
            .first()
        )

    @staticmethod
    def create_role(db: Session, role: RoleCreate):

        new_role = Role(
            role_name=role.role_name,
            description=role.description
        )

        db.add(new_role)
        db.commit()
        db.refresh(new_role)

        return new_role

    @staticmethod
    def update_role(
        db: Session,
        role_id: int,
        role: RoleUpdate
    ):

        existing_role = (
            db.query(Role)
            .filter(Role.id == role_id)
            .first()
        )

        if not existing_role:
            return None

        if role.role_name is not None:
            existing_role.role_name = role.role_name

        if role.description is not None:
            existing_role.description = role.description

        db.commit()
        db.refresh(existing_role)

        return existing_role

    @staticmethod
    def delete_role(
        db: Session,
        role_id: int
    ):

        role = (
            db.query(Role)
            .filter(Role.id == role_id)
            .first()
        )

        if not role:
            return None

        from app.models.user import User
        db.query(User).filter(User.role_id == role_id).update({User.role_id: None}, synchronize_session=False)
        db.delete(role)
        db.commit()

        return True