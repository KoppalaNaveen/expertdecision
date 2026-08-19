from sqlalchemy.orm import Session

from app.models.review import Review
from app.schemas.review import ReviewCreate


class ReviewRepository:

    @staticmethod
    def create_review(
        db: Session,
        review: ReviewCreate
    ):
        from app.models.decision import Decision
        from fastapi import HTTPException

        if review.status == "Rejected" and not (review.comments and review.comments.strip()):
            raise HTTPException(
                status_code=400,
                detail="Rejection comment is mandatory. Please provide a clear explanation for the rejection before submitting."
            )

        dec = db.query(Decision).filter(Decision.id == review.decision_id).first()
        if dec and dec.created_by == review.reviewer_id:
            raise HTTPException(
                status_code=400,
                detail="Decision owner cannot approve or reject their own decision. Only assigned reviewers and managers can take approval actions."
            )

        existing_review = db.query(Review).filter(
            Review.decision_id == review.decision_id,
            Review.reviewer_id == review.reviewer_id
        ).first()

        if existing_review:
            existing_review.status = review.status
            existing_review.comments = review.comments
            db.commit()
            db.refresh(existing_review)
            target_review = existing_review
        else:
            new_review = Review(
                decision_id=review.decision_id,
                reviewer_id=review.reviewer_id,
                status=review.status,
                comments=review.comments
            )
            db.add(new_review)
            db.commit()
            db.refresh(new_review)
            target_review = new_review
        from app.models.activity_log import ActivityLog
        act_log = ActivityLog(
            user_id=review.reviewer_id,
            action=f"Reviewed DEC-{review.decision_id}: marked as {review.status}",
            details=f"Comments: {review.comments or 'None'}"
        )
        db.add(act_log)

        # Also update decision overall status and handle sequential notifications
        from app.models.decision import Decision
        from app.services.notification_service import NotificationService
        
        dec = db.query(Decision).filter(Decision.id == review.decision_id).first()
        if dec and review.status in ["Approved", "Rejected"]:
            if review.status == "Rejected":
                dec.status = "Rejected"
                db.commit()
                # Notify creator about rejection
                try:
                    NotificationService.create_notification(
                        db,
                        user_id=dec.created_by,
                        message=f"Your decision 'DEC-{dec.id}: {dec.title}' was rejected. Please review feedback comments and resubmit.",
                        notification_type="Decision Status"
                    )
                except Exception as e:
                    print("Notification error:", e)
            elif review.status == "Approved":
                all_revs = db.query(Review).filter(Review.decision_id == review.decision_id).order_by(Review.id.asc()).all()
                all_approved = all(r.status == "Approved" for r in all_revs)
                
                if all_approved:
                    dec.status = "Approved"
                    db.commit()
                    # Notify creator about overall approval
                    try:
                        NotificationService.create_notification(
                            db,
                            user_id=dec.created_by,
                            message=f"Your decision 'DEC-{dec.id}: {dec.title}' was fully approved by all assigned reviewers and managers!",
                            notification_type="Decision Status"
                        )
                    except Exception as e:
                        print("Notification error:", e)
                else:
                    # Promote next queued reviewer in sequence (e.g. Manager) to Pending
                    next_rev = next((r for r in all_revs if r.status == "Queued"), None)
                    if next_rev:
                        next_rev.status = "Pending"
                        db.commit()
                        db.refresh(next_rev)
                        try:
                            NotificationService.create_notification(
                                db,
                                user_id=next_rev.reviewer_id,
                                message=f"Review step approved by reviewer. Decision 'DEC-{dec.id}: {dec.title}' is now awaiting your Manager approval.",
                                notification_type="Review Request"
                            )
                        except Exception as e:
                            print("Notification error:", e)
                    else:
                        pending_rev = next((r for r in all_revs if r.status == "Pending"), None)
                        if pending_rev:
                            try:
                                NotificationService.create_notification(
                                    db,
                                    user_id=pending_rev.reviewer_id,
                                    message=f"Pending review for decision 'DEC-{dec.id}: {dec.title}' approved by previous reviewer and awaiting your decision.",
                                    notification_type="Review Request"
                                )
                            except Exception as e:
                                print("Notification error:", e)

        # Trigger live notifications for action
        try:
            NotificationService.notify_review_action(db, review.decision_id, review.reviewer_id, review.status, review.comments)
        except Exception as e:
            print("Error triggering review notification:", e)

        return target_review

    @staticmethod
    def get_all_reviews(db: Session, user_id: int = None):
        from app.models.decision import Decision
        from app.models.user import User
        query = db.query(Review)
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                is_admin = user.role and "admin" in user.role.role_name.lower()
                if not is_admin:
                    target_uids = [user.id]
                    if user.email:
                        linked_emails = db.query(User.id).filter(User.email == user.email).all()
                        target_uids.extend([l[0] for l in linked_emails])
                    if user.full_name:
                        linked_names = db.query(User.id).filter(User.full_name == user.full_name).all()
                        target_uids.extend([l[0] for l in linked_names])
                    target_uids = list(set(target_uids))
                    query = query.filter(Review.reviewer_id.in_(target_uids))
            else:
                query = query.filter(Review.reviewer_id == user_id)
        return query.order_by(Review.id.desc()).all()

    @staticmethod
    def get_reviews_by_decision(
        db: Session,
        decision_id: int
    ):
        return db.query(Review).filter(
            Review.decision_id == decision_id
        ).all()