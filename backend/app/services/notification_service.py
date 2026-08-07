from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.user import User
from app.models.role import Role
from app.models.decision import Decision
from app.models.review import Review
from typing import List, Optional
from datetime import datetime, timezone

class NotificationService:

    @staticmethod
    def create_notification(db: Session, user_id: int, message: str, notification_type: str) -> Optional[Notification]:
        # Check system settings switches
        try:
            from app.models.system_setting import SystemSetting
            setting = db.query(SystemSetting).first()
            if setting:
                if not setting.enable_inapp_notifications:
                    print(f"[IN-APP NOTIF DISABLED VIA SETTINGS] Skipping for User #{user_id}")
                    return None
                
                # Check granular notification flags
                ntype_lower = notification_type.lower()
                if "decision" in ntype_lower or "status" in ntype_lower or "update" in ntype_lower:
                    if not setting.enable_decision_updates:
                        print(f"[DECISION UPDATES NOTIF DISABLED] Skipping type: {notification_type}")
                        return None
                elif "review" in ntype_lower or "approval" in ntype_lower:
                    if not setting.enable_approval_requests:
                        print(f"[APPROVAL REQUESTS NOTIF DISABLED] Skipping type: {notification_type}")
                        return None
                elif "discussion" in ntype_lower or "reply" in ntype_lower or "comment" in ntype_lower:
                    if not setting.enable_discussion_replies:
                        print(f"[DISCUSSION REPLIES NOTIF DISABLED] Skipping type: {notification_type}")
                        return None
                elif "repo" in ntype_lower or "document" in ntype_lower or "knowledge" in ntype_lower:
                    if not setting.enable_repo_updates:
                        print(f"[REPO UPDATES NOTIF DISABLED] Skipping type: {notification_type}")
                        return None
        except Exception as err:
            print(f"Notification setting check note: {err}")

        notif = Notification(
            user_id=user_id,
            message=message,
            notification_type=notification_type,
            is_read=False,
            created_at=datetime.now(timezone.utc)
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif

    @staticmethod
    def notify_decision_submission(db: Session, decision: Decision, created_by_id: int):
        creator = db.query(User).filter(User.id == created_by_id).first()
        creator_name = creator.full_name if creator else f"User #{created_by_id}"
        
        # 1. Employee / Creator Notification
        NotificationService.create_notification(
            db,
            user_id=created_by_id,
            message=f"Your decision 'DEC-{decision.id}: {decision.title}' has been created and submitted for review.",
            notification_type="Decision Submission"
        )
        
        # 2. Assigned Reviewers Notification (Sequential: Notify 1st assigned reviewer)
        reviews = db.query(Review).filter(Review.decision_id == decision.id).order_by(Review.id.asc()).all()
        reviewer_ids = {r.reviewer_id for r in reviews if r.reviewer_id != created_by_id}
        
        if reviews:
            # First reviewer in sequence
            first_review = reviews[0]
            if first_review.reviewer_id != created_by_id:
                NotificationService.create_notification(
                    db,
                    user_id=first_review.reviewer_id,
                    message=f"Pending review for decision 'DEC-{decision.id}: {decision.title}' submitted by {creator_name}.",
                    notification_type="Review Request"
                )
        
        # 3. Managers Notification (Users with Manager role who are not reviewers)
        manager_role = db.query(Role).filter(Role.role_name == "Manager").first()
        if manager_role:
            managers = db.query(User).filter(User.role_id == manager_role.id, User.id != created_by_id).all()
            for mgr in managers:
                if mgr.id not in reviewer_ids:
                    NotificationService.create_notification(
                        db,
                        user_id=mgr.id,
                        message=f"New team decision 'DEC-{decision.id}: {decision.title}' submitted by {creator_name}.",
                        notification_type="Decision Submission"
                    )

        # 4. Administrators Notification (Users with Admin / Administrator role)
        admin_roles = db.query(Role).filter(Role.role_name.in_(["Admin", "Administrator"])).all()
        admin_role_ids = [r.id for r in admin_roles]
        if admin_role_ids:
            admins = db.query(User).filter(User.role_id.in_(admin_role_ids), User.id != created_by_id).all()
            for admin in admins:
                if admin.id not in reviewer_ids:
                    NotificationService.create_notification(
                        db,
                        user_id=admin.id,
                        message=f"New platform decision 'DEC-{decision.id}: {decision.title}' registered by {creator_name}.",
                        notification_type="System Update"
                    )

    @staticmethod
    def notify_review_action(db: Session, decision_id: int, reviewer_id: int, status: str, comments: Optional[str] = None):
        decision = db.query(Decision).filter(Decision.id == decision_id).first()
        if not decision:
            return
        
        reviewer = db.query(User).filter(User.id == reviewer_id).first()
        reviewer_name = reviewer.full_name if reviewer else f"Reviewer #{reviewer_id}"
        
        status_text = status.capitalize()
        
        # 1. Creator Notification
        if decision.created_by != reviewer_id:
            NotificationService.create_notification(
                db,
                user_id=decision.created_by,
                message=f"Your decision 'DEC-{decision.id}: {decision.title}' was marked as {status_text} by {reviewer_name}.",
                notification_type="Decision Status"
            )
            
        # 2. Managers & Admins Notification
        manager_admin_roles = db.query(Role).filter(Role.role_name.in_(["Manager", "Admin", "Administrator"])).all()
        role_ids = [r.id for r in manager_admin_roles]
        if role_ids:
            supervisors = db.query(User).filter(User.role_id.in_(role_ids), User.id != reviewer_id, User.id != decision.created_by).all()
            for sup in supervisors:
                NotificationService.create_notification(
                    db,
                    user_id=sup.id,
                    message=f"Decision 'DEC-{decision.id}: {decision.title}' status updated to {status_text} by {reviewer_name}.",
                    notification_type="Review Update"
                )

    @staticmethod
    def notify_discussion(db: Session, decision_id: int, sender_id: int, content: str):
        decision = db.query(Decision).filter(Decision.id == decision_id).first()
        if not decision:
            return
        
        sender = db.query(User).filter(User.id == sender_id).first()
        sender_name = sender.full_name if sender else "A team member"
        snippet = (content[:50] + "...") if len(content) > 50 else content
        
        # Target users: creator + assigned reviewers
        reviews = db.query(Review).filter(Review.decision_id == decision_id).all()
        target_user_ids = {r.reviewer_id for r in reviews}
        target_user_ids.add(decision.created_by)
        target_user_ids.discard(sender_id)
        
        for uid in target_user_ids:
            NotificationService.create_notification(
                db,
                user_id=uid,
                message=f"New message on decision 'DEC-{decision_id}' from {sender_name}: \"{snippet}\"",
                notification_type="Discussion"
            )

    @staticmethod
    def notify_reminder(db: Session, decision_id: int, sender_id: int):
        decision = db.query(Decision).filter(Decision.id == decision_id).first()
        if not decision:
            return
        
        sender = db.query(User).filter(User.id == sender_id).first()
        sender_name = sender.full_name if sender else "The decision owner"
        
        pending_reviews = db.query(Review).filter(Review.decision_id == decision_id, Review.status == "Pending").all()
        for rev in pending_reviews:
            if rev.reviewer_id != sender_id:
                NotificationService.create_notification(
                    db,
                    user_id=rev.reviewer_id,
                    message=f"Reminder from {sender_name}: Please review pending decision 'DEC-{decision.id}: {decision.title}'.",
                    notification_type="Review Request"
                )
