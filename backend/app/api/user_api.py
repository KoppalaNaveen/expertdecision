from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.connection import get_db
from app.schemas.user import (
    UserRegister,
    AdminUserCreate,
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
    return UserService.admin_approval_action(db, action.user_id, "approve", action.actor_name or "Administrator")

@router.post("/reject")
def reject_user(action: AdminApprovalAction, db: Session = Depends(get_db)):
    return UserService.admin_approval_action(db, action.user_id, "reject", action.actor_name or "Administrator")

# -------------------------------
# Register User (Legacy)
# -------------------------------
@router.get(
    "/",
    response_model=List[UserResponse],
    status_code=200
)
def get_all_users(db: Session = Depends(get_db)):
    import hashlib
    users = UserService.get_all_users(db)
    result = []
    for u in users:
        # Resolve human-readable email
        orig_email = (u.email_original or "").strip().lower()
        if not orig_email and u.email and "@" in u.email:
            orig_email = u.email.strip().lower()

        hash_val = u.email_hash or (u.email if u.email and len(u.email) == 64 else "")
        if not hash_val and orig_email:
            hash_val = hashlib.sha256(orig_email.encode('utf-8')).hexdigest()

        if orig_email and u.email_original != orig_email:
            u.email_original = orig_email
            try:
                db.commit()
            except Exception:
                db.rollback()

        result.append(UserResponse(
            id=u.id,
            full_name=u.full_name,
            email=orig_email or "—",
            email_hash=hash_val,
            display_email=orig_email or "—",
            email_original=orig_email or "—",
            employee_id=u.employee_id,
            role_id=u.role_id,
            role_name=u.role.role_name if u.role else "User",
            team_id=u.team_id,
            designation=u.designation,
            phone=u.phone,
            is_active=u.is_active,
            email_verified=u.email_verified,
            approved=u.approved,
            status=u.status,
            approved_by=u.approved_by,
            approved_at=u.approved_at,
            rejected_by=u.rejected_by,
            rejected_at=u.rejected_at,
            created_at=u.created_at,
        ))
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


class UpdateUserRoleRequest(BaseModel):
    role_id: int

class UpdateUserStatusRequest(BaseModel):
    is_active: bool

# -------------------------------
# Update User Role
# -------------------------------
@router.put("/{user_id}/role", response_model=SuccessResponse)
def update_user_role(user_id: int, req: UpdateUserRoleRequest, db: Session = Depends(get_db)):
    from app.models.user import User
    from app.models.role import Role
    from app.services.email_service import send_role_changed_email
    from app.services.notification_service import NotificationService
    import threading

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_role_obj = db.query(Role).filter(Role.id == req.role_id).first()
    if not new_role_obj:
        raise HTTPException(status_code=404, detail="Role not found")

    prev_role_name = user.role.role_name if user.role else "Employee"
    new_role_name = new_role_obj.role_name

    user.role_id = req.role_id
    db.commit()
    db.refresh(user)

    # 1. In-App Notification (Independent)
    try:
        NotificationService.create_notification(
            db,
            user_id=user.id,
            message=f"Your user role was updated from {prev_role_name} to {new_role_name}.",
            notification_type="Role Update"
        )
    except Exception as notif_err:
        print(f"Role change notification error: {notif_err}")

    # 2. Automated Security/Account Email via Original Gmail (Async post-commit)
    if user.email:
        threading.Thread(
            target=send_role_changed_email,
            args=(user.email, user.full_name, prev_role_name, new_role_name),
            daemon=True
        ).start()

    return {"message": f"User role updated to {new_role_name} successfully"}


# -------------------------------
# Update User Activation Status
# -------------------------------
@router.put("/{user_id}/status", response_model=SuccessResponse)
def update_user_status(user_id: int, req: UpdateUserStatusRequest, db: Session = Depends(get_db)):
    from app.models.user import User
    from app.services.email_service import send_account_status_email
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
    if user.email:
        threading.Thread(
            target=send_account_status_email,
            args=(user.email, user.full_name, user.is_active),
            daemon=True
        ).start()

    return {"message": f"User account has been {status_str} successfully"}
