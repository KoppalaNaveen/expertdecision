from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Union

from app.models.team import Team
from app.models.user import User
from app.models.role import Role
from app.models.activity_log import ActivityLog
from app.schemas.team import TeamCreate, TeamUpdate, TeamResponse, TeamMemberResponse
from app.repositories.team_repository import TeamRepository


def _invalidate_caches():
    """Clear memory caches across services to ensure instant updates."""
    try:
        from app.repositories.dashboard_repository import _DASHBOARD_CACHE
        _DASHBOARD_CACHE.clear()
    except Exception:
        pass


class TeamService:

    @staticmethod
    def _log_activity(db: Session, user_id: Optional[int], action: str, details: str = ""):
        try:
            from app.services.audit_service import AuditService
            AuditService.log_event(
                db,
                user_id=user_id or 1,
                action=action,
                details=details,
                module="Teams",
                severity="Critical" if "deleted" in action.lower() else ("Warning" if "updated" in action.lower() else "Success")
            )
        except Exception as e:
            print(f"[TEAM LOG ERROR] {e}")

    @staticmethod
    def _resolve_user_ids(db: Session, raw_identifiers: Optional[List[Union[int, str]]]) -> List[int]:
        """
        Safely resolves a list of user IDs or employee_id strings (e.g., [1, 2] or ['EMP001', '5'])
        into validated, deduplicated numeric User IDs of active users.
        """
        if not raw_identifiers:
            return []

        resolved_ids = set()
        for raw in raw_identifiers:
            if raw is None:
                continue

            # Case 1: Pure integer or integer-like string
            if isinstance(raw, int) or (isinstance(raw, str) and raw.strip().isdigit()):
                u_id = int(raw)
                user = db.query(User).filter(User.id == u_id, User.is_active == True).first()
                if user:
                    resolved_ids.add(user.id)
                continue

            # Case 2: Employee ID string (e.g., "EMP8749", "AD123456")
            if isinstance(raw, str):
                emp_code = raw.strip()
                user = db.query(User).filter(User.employee_id == emp_code, User.is_active == True).first()
                if user:
                    resolved_ids.add(user.id)
                else:
                    # Also try case-insensitive or by email prefix
                    user = db.query(User).filter(User.employee_id.ilike(emp_code), User.is_active == True).first()
                    if user:
                        resolved_ids.add(user.id)

        return list(resolved_ids)

    @staticmethod
    def _format_team_response(team: Team) -> Dict[str, Any]:
        """Helper to format Team ORM model with populated employee list and count."""
        members = []
        if team.users:
            for u in team.users:
                # Include active users in the member list
                role_title = u.role.role_name if u.role else "Employee"
                orig_email = (u.email_original or "").strip().lower()
                if not orig_email and u.email and "@" in u.email:
                    orig_email = u.email.strip().lower()
                members.append({
                    "id": u.id,
                    "employee_id": u.employee_id or f"EMP-{u.id}",
                    "full_name": u.full_name,
                    "role_name": role_title,
                    "designation": u.designation or "Team Member",
                    "email": orig_email or u.email or "—"
                })

        return {
            "id": team.id,
            "team_name": team.team_name,
            "description": team.description or "",
            "employee_count": len(members),
            "employees": members
        }

    @staticmethod
    def seed_default_teams(db: Session):
        """Seeds standard EDRP enterprise teams if they do not already exist."""
        default_teams = [
            ("Engineering & Core Systems", "Core decision platform infrastructure, microservices, and backend APIs."),
            ("Cloud Infrastructure & DevOps", "Multi-cloud orchestration, disaster recovery, and 99.99% system availability."),
            ("Enterprise Security & Compliance", "SOC 2 compliance, zero-trust IAM, audit trail integrity, and data encryption."),
            ("Finance & Strategic Budgeting", "CapEx/OpEx allocation, financial ROI reviews, and enterprise vendor budgets."),
            ("AI & Decision Analytics", "Machine learning models, RAG repository intelligence, and throughput metrics."),
            ("Human Resources & Workplace Strategy", "Talent management, organizational policies, and workplace governance."),
            ("Product & Architecture Governance", "Strategic roadmap alignment, design systems, and stakeholder reviews."),
            ("Operations & Supply Chain", "Vendor partnerships, procurement SLAs, and operational logistics.")
        ]

        for name, desc in default_teams:
            existing = db.query(Team).filter(Team.team_name == name).first()
            if not existing:
                new_t = Team(team_name=name, description=desc)
                db.add(new_t)
        
        # Also clean up any legacy typo team name if present
        typo_team = db.query(Team).filter(Team.team_name == "databses mangement").first()
        if typo_team:
            typo_team.team_name = "Database Architecture & Scalability"
            typo_team.description = "Database cluster replication, schema management, and transactional high availability."

        try:
            db.commit()
        except Exception:
            db.rollback()

    @staticmethod
    def create_team(db: Session, team: TeamCreate) -> Dict[str, Any]:
        existing = TeamRepository.get_team_by_name(db, team.team_name.strip())
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Team '{team.team_name}' already exists"
            )

        new_team = Team(
            team_name=team.team_name.strip(),
            description=(team.description or "").strip()
        )
        db.add(new_team)
        db.commit()
        db.refresh(new_team)

        # Assign selected employees to this newly created team
        resolved_ids = TeamService._resolve_user_ids(db, team.employee_ids)
        if resolved_ids:
            for u_id in resolved_ids:
                user = db.query(User).filter(User.id == u_id).first()
                if user:
                    user.team_id = new_team.id
            db.commit()
            db.refresh(new_team)

        _invalidate_caches()
        TeamService._log_activity(db, None, f"Created Team: {new_team.team_name}", f"Assigned {len(resolved_ids)} employees")
        return TeamService._format_team_response(new_team)

    @staticmethod
    def get_all_teams(db: Session) -> List[Dict[str, Any]]:
        # Auto-seed standard EDRP teams if few exist
        if db.query(Team).count() < 4:
            TeamService.seed_default_teams(db)

        teams = TeamRepository.get_all_teams(db)
        return [TeamService._format_team_response(t) for t in teams]

    @staticmethod
    def get_team(db: Session, team_id: int) -> Dict[str, Any]:
        team = TeamRepository.get_team_by_id(db, team_id)
        if not team:
            raise HTTPException(
                status_code=404,
                detail="Team not found"
            )
        return TeamService._format_team_response(team)

    @staticmethod
    def update_team(db: Session, team_id: int, data: TeamUpdate) -> Dict[str, Any]:
        team = TeamRepository.get_team_by_id(db, team_id)
        if not team:
            raise HTTPException(
                status_code=404,
                detail="Team not found"
            )

        # Check if new name conflicts with another team
        new_name = data.team_name.strip()
        if new_name != team.team_name:
            dup = TeamRepository.get_team_by_name(db, new_name)
            if dup and dup.id != team_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Another team named '{new_name}' already exists"
                )

        team.team_name = new_name
        team.description = (data.description or "").strip()

        # Update employee memberships if employee_ids was passed
        if data.employee_ids is not None:
            resolved_new_ids = set(TeamService._resolve_user_ids(db, data.employee_ids))

            # 1. Unassign users currently in this team who were removed
            current_members = db.query(User).filter(User.team_id == team_id).all()
            for u in current_members:
                if u.id not in resolved_new_ids:
                    u.team_id = None

            # 2. Assign newly selected employees to this team
            for u_id in resolved_new_ids:
                user = db.query(User).filter(User.id == u_id).first()
                if user:
                    user.team_id = team_id

        db.commit()
        db.refresh(team)

        _invalidate_caches()
        TeamService._log_activity(db, None, f"Updated Team: {team.team_name}", f"Team ID: {team_id}")
        return TeamService._format_team_response(team)

    @staticmethod
    def delete_team(db: Session, team_id: int) -> Dict[str, str]:
        team = TeamRepository.get_team_by_id(db, team_id)
        if not team:
            raise HTTPException(
                status_code=404,
                detail="Team not found"
            )

        team_name = team.team_name
        # Unassign any users currently assigned to this team
        db.query(User).filter(User.team_id == team_id).update({User.team_id: None}, synchronize_session=False)
        db.commit()

        TeamRepository.delete_team(db, team)
        _invalidate_caches()
        TeamService._log_activity(db, None, f"Deleted Team: {team_name}", f"Team ID: {team_id}")
        return {
            "message": "Team deleted successfully"
        }

    @staticmethod
    def get_team_employees(db: Session, team_id: int) -> List[Dict[str, Any]]:
        team = TeamRepository.get_team_by_id(db, team_id)
        if not team:
            raise HTTPException(
                status_code=404,
                detail="Team not found"
            )
        team_data = TeamService._format_team_response(team)
        return team_data.get("employees", [])

    @staticmethod
    def get_my_team(db: Session, user_id: Optional[int] = None, employee_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves the team information for a specific employee."""
        user = None
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        elif employee_id:
            user = db.query(User).filter(User.employee_id == employee_id.strip()).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        if not user.team_id:
            return {
                "user_id": user.id,
                "employee_id": user.employee_id,
                "full_name": user.full_name,
                "team_id": None,
                "team_name": "Not Assigned",
                "description": "",
                "employee_count": 0,
                "employees": []
            }

        team = TeamRepository.get_team_by_id(db, user.team_id)
        if not team:
            return {
                "user_id": user.id,
                "employee_id": user.employee_id,
                "full_name": user.full_name,
                "team_id": None,
                "team_name": "Not Assigned",
                "description": "",
                "employee_count": 0,
                "employees": []
            }

        formatted = TeamService._format_team_response(team)
        return {
            "user_id": user.id,
            "employee_id": user.employee_id,
            "full_name": user.full_name,
            "team_id": team.id,
            "team_name": formatted["team_name"],
            "description": formatted["description"],
            "employee_count": formatted["employee_count"],
            "employees": formatted["employees"]
        }

    @staticmethod
    def get_active_employees_for_assignment(db: Session) -> List[Dict[str, Any]]:
        """Returns all active users for the Team Assignment selector."""
        users = db.query(User).filter(User.is_active == True).order_by(User.full_name).all()
        result = []
        for u in users:
            role_title = u.role.role_name if u.role else "Employee"
            orig_email = (u.email_original or "").strip().lower()
            if not orig_email and u.email and "@" in u.email:
                orig_email = u.email.strip().lower()

            result.append({
                "id": u.id,
                "employee_id": u.employee_id or f"EMP-{u.id}",
                "full_name": u.full_name,
                "role_name": role_title,
                "designation": u.designation or "Team Member",
                "email": orig_email or u.email or "—",
                "team_id": u.team_id,
                "team_name": u.team.team_name if u.team else "Not Assigned",
                "is_active": u.is_active
            })
        return result