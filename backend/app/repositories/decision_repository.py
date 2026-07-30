from sqlalchemy.orm import Session
from app.models.decision import Decision
from app.models.alternative import Alternative
from app.models.review import Review
from app.schemas.decision import DecisionCreate, DecisionUpdate, DecisionFullCreate
from app.models.decision_version import DecisionVersion
from app.models.activity_log import ActivityLog

from app.core.security import generate_data_hash

class DecisionRepository:

    @staticmethod
    def create_decision(db: Session, decision: DecisionCreate):
        content_hash = generate_data_hash(decision.title, decision.description, decision.category_id, decision.created_by)
        new_decision = Decision(
            title=decision.title,
            description=decision.description,
            created_by=decision.created_by,
            category_id=decision.category_id,
            status="Pending",
            content_hash=content_hash
        )
        db.add(new_decision)
        db.commit()
        db.refresh(new_decision)
        
        # Create first version
        new_version = DecisionVersion(
            decision_id=new_decision.id,
            version_number=1,
            title=new_decision.title,
            description=new_decision.description,
            category_id=new_decision.category_id,
            status=new_decision.status,
            changed_by=new_decision.created_by,
            change_reason="Initial Creation"
        )
        db.add(new_version)
        db.commit()
        
        return new_decision

    @staticmethod
    def create_decision_full(db: Session, full_decision: DecisionFullCreate):
        # We will wrap it all in one transaction
        content_hash = generate_data_hash(full_decision.title, full_decision.description, full_decision.category_id, full_decision.created_by)
        
        new_decision = Decision(
            title=full_decision.title,
            description=full_decision.description,
            created_by=full_decision.created_by,
            category_id=full_decision.category_id,
            priority_level=full_decision.priority_level,
            department=full_decision.department,
            decision_date=full_decision.decision_date,
            tags=full_decision.tags,
            status="Pending",
            content_hash=content_hash
        )
        db.add(new_decision)
        db.flush() # Flush to get new_decision.id
        
        for alt in full_decision.alternatives:
            new_alt = Alternative(
                decision_id=new_decision.id,
                title=alt.title,
                description=alt.description,
                pros=alt.pros,
                cons=alt.cons,
                cost=alt.cost,
                feasibility_score=alt.feasibility_score,
                risk_level=alt.risk_level
            )
            db.add(new_alt)
            
        # Process reviewers with strict rules:
        # 1. No duplicate reviewer assignments
        # 2. Decision owner (created_by) cannot be a reviewer
        # 3. Auto-assign eligible reviewers if none provided
        assigned_reviewer_ids = set()
        valid_reviewers = []
        if full_decision.reviewers:
            for rev in full_decision.reviewers:
                if rev.reviewer_id != new_decision.created_by and rev.reviewer_id not in assigned_reviewer_ids:
                    assigned_reviewer_ids.add(rev.reviewer_id)
                    valid_reviewers.append(rev)
        
        if not valid_reviewers:
            from app.models.user import User
            eligible_users = db.query(User).filter(User.id != new_decision.created_by).all()
            for u in eligible_users:
                if u.id not in assigned_reviewer_ids:
                    assigned_reviewer_ids.add(u.id)
                    db.add(Review(
                        decision_id=new_decision.id,
                        reviewer_id=u.id,
                        status="Pending",
                        approval_type="Sequential"
                    ))
        else:
            for rev in valid_reviewers:
                db.add(Review(
                    decision_id=new_decision.id,
                    reviewer_id=rev.reviewer_id,
                    status="Pending",
                    deadline=rev.deadline,
                    approval_type=rev.approval_type or "Sequential"
                ))
            
        if full_decision.temp_file_ids:
            from app.models.attachment import Attachment
            attachments = db.query(Attachment).filter(Attachment.id.in_(full_decision.temp_file_ids)).all()
            for att in attachments:
                att.decision_id = new_decision.id
                
        # Create first version
        new_version = DecisionVersion(
            decision_id=new_decision.id,
            version_number=1,
            title=new_decision.title,
            description=new_decision.description,
            category_id=new_decision.category_id,
            status=new_decision.status,
            priority_level=new_decision.priority_level,
            department=new_decision.department,
            decision_date=new_decision.decision_date,
            tags=new_decision.tags,
            changed_by=full_decision.created_by,
            change_reason=full_decision.change_reason or "Initial Creation"
        )
        db.add(new_version)
        
        act_log = ActivityLog(
            user_id=full_decision.created_by,
            action=f"Created decision: {new_decision.title}",
            details=f"Decision ID: DEC-{new_decision.id}"
        )
        db.add(act_log)
                
        db.commit()
        db.refresh(new_decision)
        
        # Trigger live notifications for creator, reviewers, manager, and administrator
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_decision_submission(db, new_decision, full_decision.created_by)
        except Exception as e:
            print("Error generating notifications:", e)
            
        return new_decision

    @staticmethod
    def update_decision_full(db: Session, decision_id: int, full_decision: DecisionFullCreate):
        db_decision = DecisionRepository.get_decision_by_id(db, decision_id)
        if not db_decision:
            return None
        
        # 1. Update basic fields
        db_decision.title = full_decision.title
        db_decision.description = full_decision.description
        db_decision.category_id = full_decision.category_id
        db_decision.priority_level = full_decision.priority_level
        db_decision.department = full_decision.department
        db_decision.decision_date = full_decision.decision_date
        db_decision.tags = full_decision.tags
        
        # If decision was rejected, move it back to Pending (resubmit)
        if db_decision.status == "Rejected":
            db_decision.status = "Pending"
            
        # Update content hash
        db_decision.content_hash = generate_data_hash(
            db_decision.title, db_decision.description, db_decision.category_id, db_decision.created_by
        )
        
        # 2. Clear and rebuild alternatives
        db.query(Alternative).filter(Alternative.decision_id == decision_id).delete()
        for alt in full_decision.alternatives:
            new_alt = Alternative(
                decision_id=decision_id,
                title=alt.title,
                description=alt.description,
                pros=alt.pros,
                cons=alt.cons,
                cost=alt.cost,
                feasibility_score=alt.feasibility_score,
                risk_level=alt.risk_level
            )
            db.add(new_alt)
            
        # 3. Clear and rebuild reviews with strict rules
        db.query(Review).filter(Review.decision_id == decision_id).delete()
        assigned_reviewer_ids = set()
        valid_reviewers = []
        if full_decision.reviewers:
            for rev in full_decision.reviewers:
                if rev.reviewer_id != db_decision.created_by and rev.reviewer_id not in assigned_reviewer_ids:
                    assigned_reviewer_ids.add(rev.reviewer_id)
                    valid_reviewers.append(rev)
                    
        if not valid_reviewers:
            from app.models.user import User
            eligible_users = db.query(User).filter(User.id != db_decision.created_by).all()
            for u in eligible_users:
                if u.id not in assigned_reviewer_ids:
                    assigned_reviewer_ids.add(u.id)
                    db.add(Review(
                        decision_id=decision_id,
                        reviewer_id=u.id,
                        status="Pending",
                        approval_type="Sequential"
                    ))
        else:
            for rev in valid_reviewers:
                db.add(Review(
                    decision_id=decision_id,
                    reviewer_id=rev.reviewer_id,
                    status="Pending",
                    deadline=rev.deadline,
                    approval_type=rev.approval_type or "Sequential"
                ))
            
        # 4. Attach new documents
        if full_decision.temp_file_ids:
            from app.models.attachment import Attachment
            attachments = db.query(Attachment).filter(Attachment.id.in_(full_decision.temp_file_ids)).all()
            for att in attachments:
                att.decision_id = decision_id
                
        # 5. Create new version
        latest_version = db.query(DecisionVersion).filter(DecisionVersion.decision_id == decision_id).order_by(DecisionVersion.version_number.desc()).first()
        next_version_num = (latest_version.version_number + 1) if latest_version else 1
        
        new_version = DecisionVersion(
            decision_id=db_decision.id,
            version_number=next_version_num,
            title=db_decision.title,
            description=db_decision.description,
            category_id=db_decision.category_id,
            status=db_decision.status,
            priority_level=db_decision.priority_level,
            department=db_decision.department,
            decision_date=db_decision.decision_date,
            tags=db_decision.tags,
            changed_by=full_decision.created_by, # Assuming creator is the one updating it here
            change_reason=full_decision.change_reason or "System Update"
        )
        db.add(new_version)
                
        db.commit()
        db.refresh(db_decision)
        return db_decision

    @staticmethod
    def get_all_decisions(db: Session):
        from sqlalchemy.orm import joinedload
        return db.query(Decision).options(joinedload(Decision.creator), joinedload(Decision.category)).all()

    @staticmethod
    def get_decision_by_id(db: Session, decision_id: int, user_id: int = None):
        db_decision = db.query(Decision).filter(Decision.id == decision_id).first()
        if db_decision and user_id:
            try:
                from app.models.activity_log import ActivityLog
                log_entry = ActivityLog(
                    user_id=user_id,
                    action=f"Accessed Decision DEC-{decision_id}",
                    details=f"User accessed and viewed decision details for DEC-{decision_id}"
                )
                db.add(log_entry)
                db.commit()
            except Exception as e:
                db.rollback()
        return db_decision

    @staticmethod
    def update_decision(db: Session, decision_id: int, decision: DecisionUpdate):
        db_decision = DecisionRepository.get_decision_by_id(db, decision_id)
        if db_decision:
            update_data = decision.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_decision, key, value)
            
            # Update hash
            db_decision.content_hash = generate_data_hash(
                db_decision.title, db_decision.description, db_decision.category_id, db_decision.created_by
            )
            
            # Create new version
            latest_version = db.query(DecisionVersion).filter(DecisionVersion.decision_id == decision_id).order_by(DecisionVersion.version_number.desc()).first()
            next_version_num = (latest_version.version_number + 1) if latest_version else 1
            
            new_version = DecisionVersion(
                decision_id=db_decision.id,
                version_number=next_version_num,
                title=db_decision.title,
                description=db_decision.description,
                category_id=db_decision.category_id,
                status=db_decision.status,
                priority_level=db_decision.priority_level,
                department=db_decision.department,
                decision_date=db_decision.decision_date,
                tags=db_decision.tags,
                change_reason=getattr(decision, "change_reason", None) or "System Update"
            )
            db.add(new_version)
            
            db.commit()
            db.refresh(db_decision)
        return db_decision

    @staticmethod
    def update_status(db: Session, decision_id: int, status: str, changed_by: int = None, change_reason: str = None):
        db_decision = DecisionRepository.get_decision_by_id(db, decision_id)
        if db_decision:
            db_decision.status = status
            
            # Record version snapshot on status change
            latest_version = db.query(DecisionVersion).filter(DecisionVersion.decision_id == decision_id).order_by(DecisionVersion.version_number.desc()).first()
            next_version_num = (latest_version.version_number + 1) if latest_version else 1
            
            new_version = DecisionVersion(
                decision_id=db_decision.id,
                version_number=next_version_num,
                title=db_decision.title,
                description=db_decision.description,
                category_id=db_decision.category_id,
                status=db_decision.status,
                priority_level=db_decision.priority_level,
                department=db_decision.department,
                decision_date=db_decision.decision_date,
                tags=db_decision.tags,
                changed_by=changed_by or db_decision.created_by,
                change_reason=change_reason or f"Status updated to {status}"
            )
            db.add(new_version)

            user_who_changed = changed_by or db_decision.created_by
            act_log = ActivityLog(
                user_id=user_who_changed,
                action=f"Updated status of DEC-{db_decision.id} to {status}",
                details=change_reason or f"Status updated to {status}"
            )
            db.add(act_log)

            db.commit()
            db.refresh(db_decision)
        return db_decision

    @staticmethod
    def get_decision_versions(db: Session, decision_id: int, user_id: int = None):
        from app.models.activity_log import ActivityLog
        from app.models.user import User
        from app.models.review import Review
        from datetime import datetime
        
        # 1. Fetch version snapshots
        versions = db.query(DecisionVersion).filter(DecisionVersion.decision_id == decision_id).all()
        
        # 2. Fetch activity logs related to this decision
        logs = db.query(ActivityLog).filter(
            (ActivityLog.action.like(f"%DEC-{decision_id}%")) | 
            (ActivityLog.details.like(f"%DEC-{decision_id}%"))
        ).all()

        # 3. Fetch reviews related to this decision
        reviews = db.query(Review).filter(
            Review.decision_id == decision_id,
            Review.status != "Pending"
        ).all()

        timeline = []
        
        # Map users
        user_ids = set(
            [v.changed_by for v in versions if v.changed_by] + 
            [l.user_id for l in logs if l.user_id] + 
            [r.reviewer_id for r in reviews if r.reviewer_id]
        )
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        user_map = {u.id: u for u in users}

        for v in versions:
            u = user_map.get(v.changed_by)
            timeline.append({
                "id": f"v_{v.id}",
                "decision_id": v.decision_id,
                "version_number": v.version_number,
                "title": v.title,
                "description": v.description,
                "category_id": v.category_id,
                "status": v.status,
                "priority_level": v.priority_level,
                "department": v.department,
                "decision_date": str(v.decision_date) if v.decision_date else None,
                "tags": v.tags,
                "changed_by": v.changed_by,
                "changed_by_name": u.full_name if u else (f"User #{v.changed_by}" if v.changed_by else "System"),
                "changed_by_initials": (u.full_name.split()[0][0] + (u.full_name.split()[-1][0] if len(u.full_name.split()) > 1 else "")).upper() if (u and u.full_name) else "U",
                "change_reason": v.change_reason or "Version Snapshot Updated",
                "event_type": "VERSION_UPDATE",
                "created_at": v.created_at.isoformat() if v.created_at else None
            })

        for l in logs:
            u = user_map.get(l.user_id)
            user_name = u.full_name if u else f"User #{l.user_id}"
            
            act_text = (l.action or "")
            det_text = (l.details or "")
            comb = (act_text + " " + det_text).lower()

            evt_type = "ACCESS_EVENT"
            badge_label = "Accessed / Viewed"
            badge_icon = "bi-eye-fill"
            badge_color = "info"

            if "document" in comb or "attachment" in comb or "file" in comb:
                evt_type = "DOC_ACCESS"
                badge_label = "Document Access"
                badge_icon = "bi-file-earmark-text-fill"
                badge_color = "warning"
            elif "discussion" in comb or "comment" in comb:
                evt_type = "DISCUSSION_EVENT"
                badge_label = "Discussion Added"
                badge_icon = "bi-chat-left-text-fill"
                badge_color = "primary"
            elif "note" in comb or "meeting" in comb:
                evt_type = "NOTE_EVENT"
                badge_label = "Meeting Note"
                badge_icon = "bi-journal-text"
                badge_color = "purple"
            elif "section" in comb or "tab" in comb:
                evt_type = "TAB_VIEW"
                badge_label = "Section Viewed"
                badge_icon = "bi-window-sidebar"
                badge_color = "secondary"

            timeline.append({
                "id": f"log_{l.id}",
                "decision_id": decision_id,
                "version_number": 0,
                "title": l.action,
                "description": l.details or l.action,
                "category_id": None,
                "status": "Logged",
                "priority_level": None,
                "department": None,
                "decision_date": None,
                "tags": None,
                "changed_by": l.user_id,
                "changed_by_name": user_name,
                "changed_by_initials": (u.full_name.split()[0][0] + (u.full_name.split()[-1][0] if len(u.full_name.split()) > 1 else "")).upper() if (u and u.full_name) else "U",
                "change_reason": l.details or l.action,
                "event_type": evt_type,
                "badge_label": badge_label,
                "badge_icon": badge_icon,
                "badge_color": badge_color,
                "created_at": l.created_at.isoformat() if l.created_at else None
            })

        for r in reviews:
            u = user_map.get(r.reviewer_id)
            timestamp = getattr(r, "reviewed_at", None)
            timeline.append({
                "id": f"rev_{r.id}",
                "decision_id": decision_id,
                "version_number": 0,
                "title": f"Review {r.status}",
                "description": r.comments or f"Review submitted as {r.status}",
                "category_id": None,
                "status": r.status,
                "priority_level": None,
                "department": None,
                "decision_date": None,
                "tags": None,
                "changed_by": r.reviewer_id,
                "changed_by_name": u.full_name if u else f"User #{r.reviewer_id}",
                "changed_by_initials": (u.full_name.split()[0][0] + (u.full_name.split()[-1][0] if len(u.full_name.split()) > 1 else "")).upper() if (u and u.full_name) else "U",
                "change_reason": f"Reviewer action: {r.status}. Comments: {r.comments or 'None'}",
                "event_type": "REVIEW_EVENT",
                "created_at": timestamp.isoformat() if timestamp else None
            })

        def parse_date(item):
            if not item.get("created_at"):
                return datetime.min
            try:
                return datetime.fromisoformat(item["created_at"])
            except Exception:
                return datetime.min

        timeline.sort(key=parse_date, reverse=True)
        return timeline

    @staticmethod
    def restore_decision_version(db: Session, decision_id: int, version_number: int, user_id: int = 1):
        db_decision = DecisionRepository.get_decision_by_id(db, decision_id)
        version_obj = db.query(DecisionVersion).filter(
            DecisionVersion.decision_id == decision_id,
            DecisionVersion.version_number == version_number
        ).first()

        if not db_decision or not version_obj:
            return None

        db_decision.title = version_obj.title
        db_decision.description = version_obj.description
        if version_obj.category_id:
            db_decision.category_id = version_obj.category_id
        if version_obj.priority_level:
            db_decision.priority_level = version_obj.priority_level
        if version_obj.department:
            db_decision.department = version_obj.department
        if version_obj.tags:
            db_decision.tags = version_obj.tags

        db_decision.content_hash = generate_data_hash(
            db_decision.title, db_decision.description, db_decision.category_id, db_decision.created_by
        )

        latest_version = db.query(DecisionVersion).filter(DecisionVersion.decision_id == decision_id).order_by(DecisionVersion.version_number.desc()).first()
        next_version_num = (latest_version.version_number + 1) if latest_version else 1

        restored_version = DecisionVersion(
            decision_id=db_decision.id,
            version_number=next_version_num,
            title=db_decision.title,
            description=db_decision.description,
            category_id=db_decision.category_id,
            status=db_decision.status,
            priority_level=db_decision.priority_level,
            department=db_decision.department,
            decision_date=db_decision.decision_date,
            tags=db_decision.tags,
            changed_by=user_id,
            change_reason=f"Restored from Version v{version_number}"
        )
        db.add(restored_version)
        db.commit()
        db.refresh(db_decision)
        return db_decision

    @staticmethod
    def delete_decision(db: Session, decision_id: int, user_id: int = None, role_name: str = None):
        from fastapi import HTTPException
        from app.models.user import User
        from app.models.role import Role

        db_decision = DecisionRepository.get_decision_by_id(db, decision_id)
        if not db_decision:
            return False

        # Determine if user is Administrator
        is_admin = False
        if role_name and "admin" in role_name.lower():
            is_admin = True
        elif user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.role_id:
                r = db.query(Role).filter(Role.id == user.role_id).first()
                if r and "admin" in (r.role_name or "").lower():
                    is_admin = True

        if db_decision.status in ("Approved", "Rejected") and not is_admin:
            raise HTTPException(
                status_code=403,
                detail=f"Decisions with status '{db_decision.status}' can only be deleted by an Administrator."
            )

        if user_id:
            act_log = ActivityLog(
                user_id=user_id,
                action=f"Deleted decision DEC-{decision_id} ({db_decision.title})",
                details=f"Decision ID: DEC-{decision_id}"
            )
            db.add(act_log)

        db.delete(db_decision)
        db.commit()
        return True

    @staticmethod
    def verify_decision_integrity(db: Session, decision_id: int) -> bool:
        db_decision = DecisionRepository.get_decision_by_id(db, decision_id)
        if not db_decision:
            return False
            
        calculated_hash = generate_data_hash(
            db_decision.title, db_decision.description, db_decision.category_id, db_decision.created_by
        )
        return db_decision.content_hash == calculated_hash