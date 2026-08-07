from sqlalchemy.orm import Session

from app.models.user import User
from app.models.role import Role
from app.models.team import Team


class ProfileRepository:

    @staticmethod
    def get_profile(db: Session, user_id: int):

        return (
            db.query(User, Role, Team)
            .outerjoin(Role, User.role_id == Role.id)
            .outerjoin(Team, User.team_id == Team.id)
            .filter(User.id == user_id)
            .first()
        )

    @staticmethod
    def update_profile(
        db: Session,
        user_id: int,
        full_name: str,
        phone: str,
        designation: str
    ):

        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return None

        user.full_name = full_name
        user.phone = phone
        user.designation = designation

        db.commit()
        db.refresh(user)

        return user