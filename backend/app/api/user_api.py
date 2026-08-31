# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.connection import get_db
from app.schemas.user import (
    UserRegister,
    AdminUserCreate,
    AdminUserUpdateCredentials,
    UserResponse,
    UserLogin,
    Token,
    SendCodeRequest,
    VerifyCodeRequest,
    ResetPasswordRequest,
    RegisterStep1,
    CheckEmployeeIDRequest,
    SaveEmployeeIDRequest,
    AdminApprovalAction
)

from app.models.user import User
from app.models.role import Role
from app.models.team import Team
from app.services.user_service import UserService

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


from typing import List

# -------------------------------
# Step 1: Register (Initiate Email Verification)
# -------------------------------
@router.post("/register/step1")
def register_step1(user: RegisterStep1, db: Session = Depends(get_db)):
    # Converts RegisterStep1 to UserRegister for sending code
    reg_obj = UserRegister(
        full_name=user.full_name,
        email=user.email,
        password=user.password,
        role_id=user.role_id,
        team_id=user.team_id or 1,
        designation=user.designation,
        phone=user.phone,
        verification_code="000000"
    )
    return UserService.step1_register(db, reg_obj)

# -------------------------------
# Step 3: Check Employee ID Uniqueness
# -------------------------------
@router.post("/check-employee-id")
def check_employee_id(req: CheckEmployeeIDRequest, db: Session = Depends(get_db)):
    return UserService.check_employee_id(db, req.role_id, req.employee_id)

# -------------------------------
# Step 3: Save Employee ID & Complete Registration
# -------------------------------
@router.post("/save-employee-id")
def save_employee_id(req: SaveEmployeeIDRequest, db: Session = Depends(get_db)):
    return UserService.save_employee_id(db, req)

# -------------------------------
# Step 4: Admin Get Pending Users
# -------------------------------
@router.get("/pending")
def get_pending_users(db: Session = Depends(get_db)):
    return UserService.get_pending_users(db)

# -------------------------------
# Step 4: Admin Approve / Reject User
# -------------------------------
@router.post("/approve")
def approve_user(action: AdminApprovalAction, db: Session = Depends(get_db)):
    return UserService.admin_approval_action(db, action.user_id, "approve", action.actor_name or "Administrator", action.team_id, action.designation)

@router.post("/reject")
def reject_user(action: AdminApprovalAction, db: Session = Depends(get_db)):
    return UserService.admin_approval_action(db, action.user_id, "reject", action.actor_name or "Administrator")

@router.post("/pending-approvals/action")
@router.post("/approval-action")
def pending_approval_action(action: AdminApprovalAction, db: Session = Depends(get_db)):
    return UserService.admin_approval_action(db, action.user_id, action.action, action.actor_name or "Administrator", action.team_id, action.designation)

# -------------------------------
# Register User (Legacy)
# -------------------------------
@router.get(
    "",
    response_model=List[UserResponse],
    status_code=200
)
@router.get(
    "/",
    response_model=List[UserResponse],
    status_code=200
)
def get_all_users(db: Session = Depends(get_db)):
    import hashlib
    from sqlalchemy.orm import joinedload
    users = db.query(User).options(joinedload(User.role), joinedload(User.team)).order_by(User.id.asc()).all()
    result = []
    seen_ids = set()
    needs_commit = False

    role_fallback = {1: "Administrator", 2: "Manager", 3: "Employee", 4: "Reviewer"}

    for u in users:
        if not u or u.id in seen_ids:
            continue
        seen_ids.add(u.id)

        # Resolve human-readable email
        orig_email = (u.email_original or "").strip().lower()
        if not orig_email and u.email and "@" in u.email:
            orig_email = u.email.strip().lower()

        hash_val = u.email_hash or (u.email if u.email and len(u.email) == 64 else "")
        if not hash_val and orig_email:
            hash_val = hashlib.sha256(orig_email.encode('utf-8')).hexdigest()

        if orig_email and u.email_original != orig_email:
            u.email_original = orig_email
            needs_commit = True

        r_name = u.role.role_name if u.role else role_fallback.get(u.role_id, "User")
        t_name = u.team.team_name if u.team else "Not Assigned"
        created_val = str(u.created_at) if u.created_at is not None else None

        result.append(UserResponse(
            id=u.id,
            full_name=u.full_name or f"User #{u.id}",
            email=orig_email or u.email or "—",
            email_hash=hash_val,
            display_email=orig_email or u.email or "—",
            email_original=orig_email or u.email or "—",
            employee_id=u.employee_id,
            role_id=u.role_id,
            role_name=r_name,
            team_id=u.team_id,
            team_name=t_name,
            designation=u.designation,
            phone=u.phone,
            is_active=bool(u.is_active) if u.is_active is not None else True,
            email_verified=bool(u.email_verified) if u.email_verified is not None else False,
            approved=bool(u.approved) if u.approved is not None else False,
            status=u.status or "Active",
            approved_by=u.approved_by,
            approved_at=u.approved_at,
            rejected_by=u.rejected_by,
            rejected_at=u.rejected_at,
            created_at=created_val,
        ))

    if needs_commit:
        try:
            db.commit()
        except Exception:
            db.rollback()

    return result

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201
)
def register_user(
    user: UserRegister,
    db: Session = Depends(get_db)
):
    return UserService.register_user(db, user)


# -------------------------------
# Login User
# -------------------------------
@router.post(
    "/login",
    response_model=Token
)
def login_user(
    user: UserLogin,
    db: Session = Depends(get_db)
):
    return UserService.login_user(db, user)


class SuccessResponse(BaseModel):
    message: str

# -------------------------------
# Send Verification Code
# -------------------------------
@router.post(
    "/send-verification-code",
    response_model=SuccessResponse
)
def send_verification_code(
    request: SendCodeRequest,
    db: Session = Depends(get_db)
):
    return UserService.send_verification_code(db, request.email, request.purpose, request.is_resend)


# -------------------------------
# Check Verification Code
# -------------------------------
@router.post(
    "/check-verification-code",
    response_model=SuccessResponse
)
def check_verification_code(
    request: VerifyCodeRequest,
    db: Session = Depends(get_db)
):
    return UserService.check_code(db, request.email, request.code, request.purpose)


# -------------------------------
# Reset Password
# -------------------------------
@router.post(
    "/reset-password",
    response_model=SuccessResponse
)
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    return UserService.reset_password(db, request.email, request.code, request.new_password)


# -------------------------------
# Admin Create User (Direct)
# -------------------------------
@router.post(
    "/admin_create",
    response_model=UserResponse,
    status_code=201
)
def admin_create_user(
    user: AdminUserCreate,
    db: Session = Depends(get_db)
):
    return UserService.admin_create_user(db, user)


# -------------------------------
# Delete User (Permanent)
# -------------------------------
@router.delete(
    "/{user_id}",
    response_model=SuccessResponse,
    status_code=200
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    return UserService.delete_user(db, user_id)


# -------------------------------
# Admin Update User Credentials & Profile
# -------------------------------
@router.post("/admin_update_credentials")
@router.put("/admin_update_credentials")
@router.put("/{user_id}/credentials")
def admin_update_credentials(
    req: AdminUserUpdateCredentials,
    db: Session = Depends(get_db)
):
    return UserService.admin_update_user_credentials(db, req)



class UpdateUserRoleRequest(BaseModel):
    role_id: int
    actor_role: str = "Administrator"
    actor_name: str = "Administrator"

class PromoteUserResponse(BaseModel):
    message: str
    user_id: int
    full_name: str
    prev_role: str
    new_role: str
    prev_employee_id: str
    new_employee_id: str

class UpdateUserStatusRequest(BaseModel):
    is_active: bool

# -------------------------------
# Promote User / Update Role (Admin Only)
# -------------------------------
@router.put("/{user_id}/role")
@router.post("/{user_id}/promote")
def promote_user_role(user_id: int, req: UpdateUserRoleRequest, db: Session = Depends(get_db)):
    return UserService.promote_user(
        db=db,
        user_id=user_id,
        new_role_id=req.role_id,
        actor_role=req.actor_role or "Administrator",
        actor_name=req.actor_name or "Administrator"
    )


# -------------------------------
# Update User Activation Status
# -------------------------------
@router.put("/{user_id}/status", response_model=SuccessResponse)
def update_user_status(user_id: int, req: UpdateUserStatusRequest, db: Session = Depends(get_db)):
    from app.models.user import User
    from app.services.email_service import send_account_status_email, get_recipient_email
    from app.services.notification_service import NotificationService
    import threading

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = req.is_active
    user.status = "Active" if req.is_active else "Inactive"
    db.commit()
    db.refresh(user)

    status_str = "activated" if user.is_active else "deactivated"

    # 1. In-App Notification (Independent)
    try:
        NotificationService.create_notification(
            db,
            user_id=user.id,
            message=f"Your EDRP account has been {status_str}.",
            notification_type="Account Status"
        )
    except Exception as notif_err:
        print(f"Status update notification error: {notif_err}")

    # 2. Automated Account Email via Original Gmail (Async post-commit)
    target_email = get_recipient_email(user)
    if target_email:
        threading.Thread(
            target=send_account_status_email,
            args=(target_email, user.full_name, user.is_active),
            daemon=True
        ).start()

    return {"message": f"User account has been {status_str} successfully"}



# -------------------------------
# Get User's Assigned Team
# -------------------------------
@router.get("/{user_id}/team")
def get_user_team(user_id: int, db: Session = Depends(get_db)):
    from app.services.team_service import TeamService
    return TeamService.get_my_team(db, user_id=user_id)


class UserHeartbeatReq(BaseModel):
    user_id: int

@router.post("/heartbeat")
def user_presence_heartbeat(req: UserHeartbeatReq):
    from app.services.presence_service import PresenceService
    PresenceService.heartbeat(req.user_id)
    return {"status": "ok", "online_count": len(PresenceService.get_online_user_ids())}

@router.post("/logout-presence")
def user_logout_presence(req: UserHeartbeatReq):
    from app.services.presence_service import PresenceService
    PresenceService.set_offline(req.user_id)
    return {"status": "offline"}


