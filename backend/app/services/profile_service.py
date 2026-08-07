from sqlalchemy.orm import Session

from app.repositories.profile_repository import ProfileRepository


class ProfileService:

    @staticmethod
    def get_profile(db: Session, user_id: int, current_user_id: int = None):

        data = ProfileRepository.get_profile(db, user_id)

        if not data:
            return None

        user, role, team = data
        is_own_profile = current_user_id == user_id if current_user_id else False

        orig_email = (user.email_original or "").strip().lower()
        if not orig_email and user.email and "@" in user.email:
            orig_email = user.email.strip().lower()
        if not orig_email:
            orig_email = user.email or user.email_hash or "—"

        return {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "email_hash": user.email_hash,
            "email_original": orig_email,
            "employee_id": user.employee_id,
            "phone": user.phone,
            "designation": user.designation,
            "role": role.role_name if role else "User",
            "team": team.team_name if team else "General",
            "is_own_profile": is_own_profile
        }

    @staticmethod
    def update_profile(db: Session, user_id: int, profile):

        user = ProfileRepository.update_profile(
            db=db,
            user_id=user_id,
            full_name=profile.full_name,
            phone=profile.phone,
            designation=profile.designation
        )

        if not user:
            return None

        return {
            "message": "Profile Updated Successfully"
        }