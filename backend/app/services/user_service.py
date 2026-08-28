from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from fastapi import HTTPException, status
import random
import time
import hashlib
import threading

from app.schemas.user import UserRegister, UserLogin, AdminUserCreate, AdminUserUpdateCredentials
from app.repositories.user_repository import UserRepository
from app.core.security import hash_password, verify_password
from app.core.auth import create_access_token
from app.models.user import VerificationCode, User
from app.services.email_service import (
    send_otp_email,
    send_id_email,
    send_account_approved_email,
    send_account_rejected_email,
    send_password_reset_confirmation_email,
    send_new_login_email,
    send_account_deleted_email,
    send_role_changed_email,
    send_account_status_email,
    send_credentials_updated_email,
    get_recipient_email
)
from app.services.notification_service import NotificationService


class UserService:

    @staticmethod
    def _log_activity(db: Session, user_id: int, action: str, details: str = ""):
        from app.services.audit_service import AuditService
        AuditService.log_event(db, user_id=user_id, action=action, details=details)

    @staticmethod
    def _get_role_prefix(db: Session, role_id: int) -> str:
        from app.models.role import Role
        role_obj = db.query(Role).filter(Role.id == role_id).first()
        role_name = (role_obj.role_name if role_obj else "").strip().lower()

        if "admin" in role_name:
            return "AD"
        elif "manager" in role_name or "lead" in role_name:
            return "MN"
        elif "reviewer" in role_name:
            return "RW"
        elif "employee" in role_name:
            return "EMP"
        
        fallback = {1: "AD", 2: "MN", 3: "EMP", 4: "RW"}
        return fallback.get(role_id, "EMP")

    @staticmethod
    def _find_user_by_email(db: Session, raw_email: str):
        clean_email = (raw_email or "").strip().lower()
        hashed_email = hashlib.sha256(clean_email.encode('utf-8')).hexdigest() if '@' in clean_email else clean_email
        user = db.query(User).filter((User.email == clean_email) | (User.email == hashed_email) | (User.email_hash == clean_email) | (User.email_hash == hashed_email)).first()
        return user

    @staticmethod
    def step1_register(db: Session, user: UserRegister):
        clean_email = user.email.strip().lower()
        existing_user = UserService._find_user_by_email(db, clean_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email is already registered."
            )
        
        # Send 6-digit OTP code
        return UserService.send_verification_code(db, clean_email, "register")

    @staticmethod
    def check_employee_id(db: Session, role_id: int, employee_id_num: str):
        prefix = UserService._get_role_prefix(db, role_id)
        raw_num = employee_id_num.strip()
        
        if not raw_num.isdigit() or len(raw_num) != 6:
            raise HTTPException(
                status_code=400,
                detail="Employee ID must consist of exactly 6 digits."
            )

        full_id = f"{prefix}{raw_num}"
        existing = UserRepository.get_user_by_employee_id(db, full_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="This Employee ID already exists."
            )

        return {
            "available": True,
            "employee_id": full_id,
            "prefix": prefix
        }

    @staticmethod
    def save_employee_id(db: Session, req):
        clean_email = req.email.strip().lower()
        
        # Check email duplicate
        if UserService._find_user_by_email(db, clean_email):
            raise HTTPException(
                status_code=400,
                detail="This email is already registered."
            )

        # Check Employee ID duplicate
        full_emp_id = req.employee_id.strip()
        if UserRepository.get_user_by_employee_id(db, full_emp_id):
            raise HTTPException(
                status_code=400,
                detail="This Employee ID already exists."
            )

        hashed_pwd = hash_password(req.password)

        new_user = UserRepository.create_pending_user(
            db=db,
            email=clean_email,
            full_name=req.full_name,
            hashed_password=hashed_pwd,
            employee_id=full_emp_id,
            role_id=req.role_id,
            team_id=req.team_id or 1,
            designation=req.designation,
            phone=req.phone
        )

        # Notify all Admin users about the new registration awaiting approval
        try:
            from app.models.notification import Notification
            from app.models.role import Role
            admin_roles = db.query(Role).filter(Role.role_name.in_(["Admin", "Administrator"])).all()
            admin_role_ids = [r.id for r in admin_roles] or [1]
            admin_users = db.query(User).filter(User.role_id.in_(admin_role_ids)).all()
            for admin in admin_users:
                notif = Notification(
                    user_id=admin.id,
                    message=f"New user {new_user.full_name} ({new_user.employee_id}) created an account awaiting administrator approval.",
                    notification_type="User Approval Request",
                    is_read=False
                )
                db.add(notif)
            db.commit()
        except Exception as notif_err:
            print(f"Notification creation note: {notif_err}")

        UserService._log_activity(db, new_user.id, f"Employee ID created: {full_emp_id} for user {new_user.full_name}", f"Role ID: {req.role_id}")

        return {
            "message": "Your account has been created successfully.",
            "sub_message": "Your account is waiting for administrator approval. You can login only after your account is approved.",
            "user_id": new_user.id,
            "employee_id": new_user.employee_id
        }

    @staticmethod
    def _generate_unique_employee_id(db: Session, role_id: int) -> str:
        import random
        prefix_map = {1: "AD", 2: "MN", 3: "EMP", 4: "RW"}
        prefix = prefix_map.get(role_id, "EMP")
        for _ in range(100):
            emp_id = f"{prefix}{random.randint(1000, 9999)}"
            if not UserRepository.get_user_by_employee_id(db, emp_id):
                return emp_id
        return f"{prefix}{random.randint(10000, 99999)}"

    @staticmethod
    def get_all_users(db: Session):
        return UserRepository.get_all_users(db)

    @staticmethod
    def login_user(db: Session, user: UserLogin):
        identifier = user.employee_id.strip()
        
        # Look up user by employee_id or email
        db_user = UserRepository.get_user_by_employee_id(db, identifier)
        if not db_user:
            db_user = UserRepository.get_user_by_email(db, identifier)

        # Case 1: Account not found
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Employee ID / Email or Password."
            )

        # Case 2: Wrong password
        if not verify_password(user.password, db_user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Employee ID or Password."
            )

        # Upgrade legacy hash to modern SHA-256 if needed
        expected_sha = hash_password(user.password)
        if db_user.password != expected_sha:
            try:
                db_user.password = expected_sha
                db.commit()
                db.refresh(db_user)
            except Exception:
                db.rollback()

        # Case 3: Email not verified
        if db_user.email_verified is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please verify your email before logging in."
            )

        # Case 5: Rejected
        if db_user.status == "Rejected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account has been rejected by the administrator."
            )

        # Case 4: Pending approval
        if db_user.status == "Pending Approval" or db_user.approved is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account is awaiting administrator approval."
            )

        # Case 6: Approved -> generate JWT
        access_token = create_access_token({"sub": db_user.employee_id})

        # Automated Security Email: New Login Notification via Original Gmail (Async)
        target_email = get_recipient_email(db_user)
        if target_email:
            def _async_login_email(email_addr, name):
                try:
                    from datetime import datetime, timezone
                    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    send_new_login_email(email_addr, name, login_time=now_str, device_info="Web Browser Session")
                except Exception as log_err:
                    print(f"New login email dispatch note: {log_err}")

            threading.Thread(target=_async_login_email, args=(target_email, db_user.full_name), daemon=True).start()

        UserService._log_activity(db, db_user.id, f"User login successful: {db_user.full_name} ({db_user.employee_id})", f"Role: {db_user.role.role_name if db_user.role else 'User'}")

        try:
            from app.services.presence_service import PresenceService
            PresenceService.heartbeat(db_user.id)
        except Exception:
            pass

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": db_user.id,
            "role_name": db_user.role.role_name if db_user.role else "User",
            "full_name": db_user.full_name,
            "team_id": db_user.team_id,
            "team_name": db_user.team.team_name if db_user.team else "Not Assigned",
            "designation": db_user.designation or "Team Member",
            "employee_id": db_user.employee_id or f"EMP-{db_user.id}"
        }

    @staticmethod
    def get_pending_users(db: Session):
        users = UserRepository.get_pending_users(db)
        res = []
        for u in users:
            email_value = u.email or u.email_hash or ""
            res.append({
                "id": u.id,
                "full_name": u.full_name,
                "email": email_value,
                "email_hash": email_value,
                "display_email": f"{email_value[:16]}..." if email_value else u.email,
                "employee_id": u.employee_id,
                "role_id": u.role_id,
                "role_name": u.role.role_name if u.role else "User",
                "status": u.status,
                "created_at": u.created_at or "N/A"
            })
        return res

    @staticmethod
    def admin_approval_action(db: Session, user_id: int, action: str, actor_name: str = "Administrator", team_id: int = None, designation: str = None):
        updated_user = UserRepository.update_user_approval(db, user_id, action, actor_name, team_id, designation)
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found.")

        # 1. In-App Notification (Independent)
        try:
            status_msg = (
                f"Your account has been verified and approved by {actor_name}. You can now login with Employee ID {updated_user.employee_id}."
                if action == "approve"
                else "Your account registration application was not approved."
            )
            NotificationService.create_notification(
                db,
                user_id=updated_user.id,
                message=status_msg,
                notification_type="Account Status"
            )
        except Exception as notif_err:
            print(f"Approval status notification note: {notif_err}")

        # 2. In-App Mail (Internal Email Service Inbox)
        if action == "approve":
            try:
                from app.models.internal_email import InternalEmail
                from datetime import datetime, timezone

                admin_user = db.query(User).filter(User.role_id == 1).first()
                sender_id = admin_user.id if admin_user else user_id
                user_role_str = updated_user.role.role_name if (updated_user.role and updated_user.role.role_name) else "Employee"
                user_team_str = updated_user.team.team_name if (updated_user.team and updated_user.team.team_name) else "Not Assigned"
                user_desig_str = updated_user.designation or user_role_str

                in_app_mail = InternalEmail(
                    sender_id=sender_id,
                    recipient_type=user_role_str,
                    recipient_names=f"{updated_user.full_name} ({updated_user.employee_id})",
                    subject="Your Account is Verified and Approved by Administrator",
                    priority="High",
                    message=(
                        f"Hello {updated_user.full_name},\n\n"
                        f"Your account on the Expert Decision Replay Platform (EDRP) has been verified and approved by {actor_name}.\n\n"
                        f"You can now access your dashboard and all platform features using your assigned corporate credentials:\n"
                        f"• Employee ID / Login ID: {updated_user.employee_id}\n"
                        f"• Role: {user_role_str}\n"
                        f"• Team: {user_team_str}\n"
                        f"• Designation: {user_desig_str}\n"
                        f"• Approved By: {actor_name}\n"
                        f"• Status: Verified & Active\n\n"
                        f"If you have any questions or need help, please reach out to the Support team.\n\n"
                        f"Best regards,\n"
                        f"EDRP Administration Team"
                    ),
                    status="Delivered",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(in_app_mail)
                db.commit()
                print(f"[IN-APP MAIL CREATED] Approval in-app mail created for {updated_user.full_name} ({updated_user.employee_id})")
            except Exception as in_app_err:
                db.rollback()
                print(f"In-app approval email dispatch note: {in_app_err}")

        # 3. Automated External Email via Gmail SMTP (Async post-commit)
        user_email = get_recipient_email(updated_user) or (updated_user.email_original if (updated_user.email_original and "@" in updated_user.email_original) else (updated_user.email if (updated_user.email and "@" in updated_user.email) else None))
        if user_email:
            role_n = updated_user.role.role_name if updated_user.role else "Employee"
            team_n = updated_user.team.team_name if updated_user.team else "Not Assigned"
            desig_n = updated_user.designation or role_n

            def _async_status_email(target_email, emp_id, name, act, r_name, t_name, d_name, approver):
                try:
                    if act == "approve":
                        send_account_approved_email(
                            to_email=target_email,
                            employee_id=emp_id,
                            full_name=name,
                            role_name=r_name,
                            team_name=t_name,
                            designation=d_name,
                            approved_by=approver
                        )
                    else:
                        send_account_rejected_email(target_email, name, "Administrative review")
                except Exception as e:
                    print(f"Approval/rejection email dispatch exception: {e}")

            threading.Thread(
                target=_async_status_email,
                args=(user_email, updated_user.employee_id, updated_user.full_name, action, role_n, team_n, desig_n, actor_name),
                daemon=True
            ).start()
        else:
            print(f"[ACCOUNT APPROVAL NOTE] No valid email found for user ID {updated_user.id} ({updated_user.employee_id})")

        UserService._log_activity(db, user_id, f"Administrator {action}d account for {updated_user.full_name} ({updated_user.employee_id})", f"By: {actor_name}")

        msg = "Account approved successfully." if action == "approve" else "Account rejected successfully."
        return {"message": msg, "user_id": updated_user.id, "status": updated_user.status}

    @staticmethod
    def send_verification_code(db: Session, email: str, purpose: str, is_resend: bool = False):
        # Check if email is already registered based on purpose
        clean_email = (email or "").strip().lower()
        existing_user = UserRepository.get_user_by_email(db, clean_email)
        
        if purpose == "register" and existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        elif purpose == "reset_password" and not existing_user:
            raise HTTPException(status_code=404, detail="Email not registered")
            
        # Generate 6-digit code
        code = str(random.randint(100000, 999999))
        
        # Set expiry: 2 minutes (120 seconds)
        expiry_seconds = 120
        expires_at = int(time.time()) + expiry_seconds

        # Delete previous codes for this email and purpose
        clean_email = (email or "").strip().lower()

        db.query(VerificationCode).filter(
            VerificationCode.email == clean_email,
            VerificationCode.purpose == purpose
        ).delete(synchronize_session=False)
        
        vc = VerificationCode(
            email=clean_email,
            code=code,
            expires_at=expires_at,
            purpose=purpose
        )
        db.add(vc)
        db.commit()

        # Send email in background thread to prevent HTTP timeouts
        def _async_send(target_email, otp_code):
            try:
                send_otp_email(target_email, otp_code)
            except Exception as e:
                print(f"Async OTP send note: {e}")

        threading.Thread(target=_async_send, args=(clean_email, code), daemon=True).start()
            
        return {"message": "Verification code sent successfully"}
        
    @staticmethod
    def check_code(db: Session, email: str, code: str, purpose: str):
        clean_email = (email or "").strip().lower()
        vc = db.query(VerificationCode).filter(
            VerificationCode.email == clean_email,
            VerificationCode.code == code,
            VerificationCode.purpose == purpose
        ).first()
        
        if not vc:
            raise HTTPException(status_code=400, detail="Invalid verification code")
            
        if vc.expires_at < int(time.time()):
            db.delete(vc)
            db.commit()
            raise HTTPException(status_code=400, detail="Verification code expired")
            
        return {"message": "Code is valid"}

    @staticmethod
    def _verify_code(db: Session, email: str, code: str, purpose: str):
        clean_email = (email or "").strip().lower()
        vc = db.query(VerificationCode).filter(
            VerificationCode.email == clean_email,
            VerificationCode.code == code,
            VerificationCode.purpose == purpose
        ).first()
        
        if not vc:
            raise HTTPException(status_code=400, detail="Invalid verification code")
            
        if vc.expires_at < int(time.time()):
            db.delete(vc)
            db.commit()
            raise HTTPException(status_code=400, detail="Verification code expired")
            
        # Delete code after successful verification
        db.delete(vc)
        db.commit()
        return True

    @staticmethod
    def reset_password(db: Session, email: str, code: str, new_password: str):
        # Verify code first
        UserService._verify_code(db, email, code, "reset_password")
        
        # Find user
        clean_email = (email or "").strip().lower()
        user = UserRepository.get_user_by_email(db, clean_email)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Update password
        user.password = hash_password(new_password)
        db.commit()

        # 1. In-App Notification (Independent)
        try:
            NotificationService.create_notification(
                db,
                user_id=user.id,
                message="Your account password was successfully reset.",
                notification_type="Security Alert"
            )
        except Exception as notif_err:
            print(f"Password reset notification note: {notif_err}")

        # 2. Automated Security Email via Original Gmail (Async post-commit)
        user_email = get_recipient_email(user) or (clean_email if "@" in clean_email else None)
        if user_email:
            def _async_reset_email(target_email, name):
                try:
                    send_password_reset_confirmation_email(target_email, name)
                except Exception as mail_err:
                    print(f"Password reset email dispatch exception: {mail_err}")

            threading.Thread(target=_async_reset_email, args=(user_email, user.full_name), daemon=True).start()
        
        return {"message": "Password reset successfully"}

    @staticmethod
    def admin_create_user(db: Session, user: AdminUserCreate):
        # 1. Preserve the original email value
        plaintext_email = (user.email or "").strip().lower()

        # 2. Check if email already exists
        existing_user = UserRepository.get_user_by_email(db, plaintext_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # 3. Generate or check Employee ID uniqueness
        if user.employee_id and user.employee_id.strip():
            new_employee_id = user.employee_id.strip()
            if UserRepository.get_user_by_employee_id(db, new_employee_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Employee ID '{new_employee_id}' is already assigned to another user"
                )
        else:
            new_employee_id = UserService._generate_unique_employee_id(db, user.role_id)

        # 4. Hash password
        hashed_password = hash_password(user.password)

        # 5. Create user register object
        user_reg = UserRegister(
            full_name=user.full_name,
            email=user.email,
            password=user.password,
            role_id=user.role_id,
            team_id=user.team_id or 1,
            employee_id=new_employee_id,
            designation=user.designation,
            phone=user.phone,
            verification_code="000000"
        )
        user_reg.email = plaintext_email.strip().lower()

        created_user = UserRepository.create_user(db, user_reg, hashed_password)

        # Send welcome/ID email in background thread to avoid blocking HTTP response
        def _async_mail(target_email, emp_id):
            try:
                send_id_email(target_email, emp_id)
            except Exception as e:
                print(f"Async email error: {e}")

        threading.Thread(target=_async_mail, args=(plaintext_email, new_employee_id), daemon=True).start()

        UserService._log_activity(db, created_user.id, f"Administrator created user: {created_user.full_name} ({created_user.employee_id})", f"Role ID: {created_user.role_id}")

        return created_user

    @staticmethod
    def admin_update_user_credentials(db: Session, req: AdminUserUpdateCredentials):
        user = UserRepository.get_user_by_id(db, req.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        old_email = (getattr(user, 'email_original', None) or user.email or "").strip().lower()
        if '@' not in old_email:
            # If old_email was stored as a raw hash without original, keep fallback
            orig = getattr(user, 'email_original', '')
            if orig and '@' in orig:
                old_email = orig.strip().lower()
        old_full_name = user.full_name
        employee_id = user.employee_id or f"EMP-{user.id}"

        email_changed = False
        new_email = old_email
        if req.email:
            candidate_email = req.email.strip().lower()
            if candidate_email != old_email:
                existing = UserService._find_user_by_email(db, candidate_email)
                if existing and existing.id != user.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This email address is already in use by another account."
                    )
                new_email = candidate_email
                candidate_hash = hashlib.sha256(candidate_email.encode('utf-8')).hexdigest()
                user.email = candidate_hash
                user.email_original = candidate_email
                user.email_hash = candidate_hash
                email_changed = True


        password_changed = False
        if req.password:
            raw_pwd = req.password.strip()
            if len(raw_pwd) < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password must be at least 6 characters long."
                )
            user.password = hash_password(raw_pwd)
            password_changed = True

        if req.full_name:
            user.full_name = req.full_name.strip()
        if req.role_id:
            user.role_id = req.role_id
        if req.team_id is not None:
            user.team_id = req.team_id if req.team_id > 0 else None
        if req.designation is not None:
            user.designation = req.designation.strip()
        if req.phone is not None:
            user.phone = req.phone.strip()

        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user.updated_at = now_str
        db.commit()
        db.refresh(user)

        # Activity logging
        changes_desc = []
        if email_changed: changes_desc.append(f"Email: {old_email} -> {new_email}")
        if password_changed: changes_desc.append("Password reset")
        if req.full_name and req.full_name != old_full_name: changes_desc.append(f"Name updated")
        if req.role_id: changes_desc.append(f"Role ID: {req.role_id}")
        if req.team_id is not None: changes_desc.append(f"Team ID: {req.team_id}")

        UserService._log_activity(
            db,
            user.id,
            f"Administrator updated credentials for {user.full_name} ({employee_id})",
            ", ".join(changes_desc) if changes_desc else "Profile updated"
        )

        # Invalidate dashboard caches
        try:
            from app.repositories.dashboard_repository import _DASHBOARD_CACHE
            _DASHBOARD_CACHE.clear()
        except Exception:
            pass

        # Dispatches emails to OLD email and NEW email
        if (email_changed or password_changed) and req.notify_user:
            plain_new_pwd = req.password.strip() if req.password else ""
            def _async_send_credential_updates(to_old, to_new, name, emp_id, em_chg, pwd_chg, new_pwd):
                try:
                    # 1. Send to old email
                    if to_old:
                        send_credentials_updated_email(
                            to_email=to_old,
                            full_name=name,
                            employee_id=emp_id,
                            email_changed=em_chg,
                            old_email=to_old,
                            new_email=to_new,
                            password_changed=pwd_chg,
                            new_password=new_pwd,
                            is_old_inbox=(to_old != to_new)
                        )
                    # 2. Send to new email if different from old
                    if to_new and to_new != to_old:
                        send_credentials_updated_email(
                            to_email=to_new,
                            full_name=name,
                            employee_id=emp_id,
                            email_changed=em_chg,
                            old_email=to_old,
                            new_email=to_new,
                            password_changed=pwd_chg,
                            new_password=new_pwd,
                            is_old_inbox=False
                        )
                except Exception as mail_err:
                    print(f"Async credential email notification error: {mail_err}")

            threading.Thread(
                target=_async_send_credential_updates,
                args=(old_email, new_email, user.full_name, employee_id, email_changed, password_changed, plain_new_pwd),
                daemon=True
            ).start()


        return {
            "message": "User account and credentials updated successfully",
            "user_id": user.id,
            "employee_id": employee_id,
            "full_name": user.full_name,
            "email": user.email,
            "email_changed": email_changed,
            "password_changed": password_changed,
            "old_email": old_email,
            "new_email": new_email
        }


    @staticmethod
    def delete_user(db: Session, user_id: int):
        user = UserRepository.get_user_by_id(db, user_id)
        target_email = get_recipient_email(user)
        target_name = user.full_name if user else "User"

        UserService._log_activity(db, 1, f"Administrator deleted user account ID: {user_id}", "")
        success, err_msg = UserRepository.delete_user(db, user_id)
        if not success:
            if err_msg == "User not found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err_msg or "Failed to delete user")

        # Send account deletion email after successful database deletion
        if target_email:
            def _async_del_email(em, nm):
                try:
                    send_account_deleted_email(em, nm)
                except Exception as mail_err:
                    print(f"Account deletion email dispatch exception: {mail_err}")

            threading.Thread(target=_async_del_email, args=(target_email, target_name), daemon=True).start()

        return {"message": "User deleted successfully"}

    @staticmethod
    def _transform_employee_id(current_emp_id: str, new_role_prefix: str, db: Session, target_user_id: int) -> str:
        """
        Transforms the user's Employee ID by updating the prefix to the new role's prefix
        while strictly preserving the numeric identifier (e.g., EMP123456 -> RW123456).
        """
        import re
        raw_id = (current_emp_id or "").strip()
        digits_match = re.search(r'\d+', raw_id)
        if digits_match:
            digits = digits_match.group()
        else:
            digits = f"{random.randint(100000, 999999)}"

        new_candidate = f"{new_role_prefix}{digits}"
        
        # Check uniqueness against other users
        existing = db.query(User).filter(User.employee_id == new_candidate, User.id != target_user_id).first()
        if not existing:
            return new_candidate

        # Fallback if collision occurs
        for _ in range(50):
            new_digits = f"{random.randint(100000, 999999)}"
            cand = f"{new_role_prefix}{new_digits}"
            if not db.query(User).filter(User.employee_id == cand).first():
                return cand
        return f"{new_role_prefix}{int(time.time()) % 1000000:06d}"

    @staticmethod
    def promote_user(db: Session, user_id: int, new_role_id: int, actor_role: str = "Administrator", actor_name: str = "Administrator"):
        """
        Administrator-Only User Promotion / Role Change.
        Updates user's role, transforms Employee ID (e.g. EMP123456 -> RW123456),
        dispatches an email to the user's Gmail with the new login ID, and records audit logs.
        """
        from app.models.role import Role

        # 1. Authorization check: Only Administrators can promote users
        actor_clean = (actor_role or "").strip().lower()
        if not any(adm in actor_clean for adm in ["admin", "administrator", "system administrator"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Only Administrators can promote or change user roles."
            )

        # 2. Fetch target user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        # 3. Fetch target role
        new_role_obj = db.query(Role).filter(Role.id == new_role_id).first()
        if not new_role_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target role not found.")

        prev_role_name = user.role.role_name if user.role else "Employee"
        if user.role_id == 1 or prev_role_name.strip().lower() in ["administrator", "admin", "system administrator"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an Administrator (the highest role) and cannot be promoted."
            )

        if user.role_id == new_role_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User already has the role '{new_role_obj.role_name}'."
            )

        new_role_name = new_role_obj.role_name

        prev_emp_id = user.employee_id or f"EMP{random.randint(100000, 999999)}"
        new_prefix = UserService._get_role_prefix(db, new_role_id)
        new_emp_id = UserService._transform_employee_id(prev_emp_id, new_prefix, db, user.id)

        # 4. Update user record
        from datetime import datetime, timezone
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        user.role_id = new_role_id
        user.employee_id = new_emp_id
        user.updated_at = now_str
        db.commit()
        db.refresh(user)

        # 5. In-App Notification
        try:
            NotificationService.create_notification(
                db,
                user_id=user.id,
                message=f"Your role was updated from {prev_role_name} to {new_role_name}. Your new Login Employee ID is {new_emp_id}.",
                notification_type="Role Update"
            )
        except Exception as notif_err:
            print(f"Role promotion notification note: {notif_err}")

        # 6. Automated Email via Gmail to user's real email address
        target_email = get_recipient_email(user)
        if target_email:
            def _async_promote_email():
                try:
                    send_role_changed_email(
                        to_email=target_email,
                        recipient_name=user.full_name,
                        prev_role=prev_role_name,
                        new_role=new_role_name,
                        prev_emp_id=prev_emp_id,
                        new_emp_id=new_emp_id,
                        change_time=now_str
                    )
                except Exception as mail_err:
                    print(f"Role change email dispatch exception: {mail_err}")

            threading.Thread(target=_async_promote_email, daemon=True).start()

        # 7. Audit Log
        UserService._log_activity(
            db,
            user.id,
            f"Promoted user {user.full_name}: {prev_role_name} ({prev_emp_id}) -> {new_role_name} ({new_emp_id})",
            f"By {actor_name} ({actor_role})"
        )

        return {
            "message": f"User successfully promoted from {prev_role_name} to {new_role_name}. New Employee ID: {new_emp_id}",
            "user_id": user.id,
            "full_name": user.full_name,
            "prev_role": prev_role_name,
            "new_role": new_role_name,
            "prev_employee_id": prev_emp_id,
            "new_employee_id": new_emp_id
        }