from sqlalchemy.orm import Session
from app.models.decision import Decision
from app.models.alternative import Alternative
from app.models.review import Review
from app.schemas.decision import DecisionCreate, DecisionUpdate, DecisionFullCreate
from app.models.decision_version import DecisionVersion
from app.models.activity_log import ActivityLog

from app.core.security import generate_data_hash

from fastapi import HTTPException

class DecisionRepository:

    @staticmethod
    def create_decision(db: Session, decision: DecisionCreate):
        content_hash = generate_data_hash(decision.title, decision.description, decision.category_id, decision.created_by)
        new_decision = Decision(
            title=decision.title,
            description=decision.description,
            created_by=decision.created_by,
            category_id=decision.category_id,
            priority_level=decision.priority_level,
            department=decision.department,
            decision_date=decision.decision_date,
            tags=decision.tags,
            content_hash=content_hash
        )
        db.add(new_decision)
        db.commit()
        db.refresh(new_decision)
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
            status=full_decision.status or "Pending",
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
        # 1. Manual selection validation: allowed roles are Reviewer and Manager. Reject Employee, Admin, Owner, Inactive, Duplicates.
        # 2. Sequential queueing: Step 1 = Pending, Step 2+ = Queued.
        # 3. Auto-assign ONLY when no reviewers are selected: assigns EXACTLY 1 Reviewer + 1 Manager.
        from app.models.user import User
        assigned_reviewer_ids = set()
        valid_reviewers = []

        if full_decision.reviewers:
            for idx, rev in enumerate(full_decision.reviewers):
                if rev.reviewer_id == new_decision.created_by:
                    raise HTTPException(status_code=400, detail="Decision creator cannot be assigned as a reviewer or approver.")
                if rev.reviewer_id in assigned_reviewer_ids:
                    continue
                
                u = db.query(User).filter(User.id == rev.reviewer_id).first()
                if not u:
                    raise HTTPException(status_code=400, detail=f"Assigned reviewer ID {rev.reviewer_id} not found.")
                
                r_name = (u.role.role_name if u.role else "").lower()
                emp_id = (u.employee_id or "").upper()
                
                is_reviewer = "reviewer" in r_name or emp_id.startswith("RW")
                is_manager = "manager" in r_name or emp_id.startswith("MN")
                
                if not (is_reviewer or is_manager) or "employee" in r_name or "admin" in r_name:
                    raise HTTPException(status_code=400, detail=f"User '{u.full_name}' ({u.role.role_name if u.role else 'Employee'}) is not eligible as a reviewer. Only Reviewer and Manager roles are allowed.")

                assigned_reviewer_ids.add(rev.reviewer_id)
                valid_reviewers.append((rev, idx == 0))

            for rev, is_first in valid_reviewers:
                db.add(Review(
                    decision_id=new_decision.id,
                    reviewer_id=rev.reviewer_id,
                    status="Pending" if is_first else "Queued",
                    deadline=rev.deadline,
                    approval_type=rev.approval_type or "Sequential"
                ))
        else:
            # Auto-assignment: assign EXACTLY 1 Reviewer + 1 Manager
            eligible_users = db.query(User).filter(User.id != new_decision.created_by).all()
            
            auto_reviewer = None
            auto_manager = None
            
            for u in eligible_users:
                r_name = (u.role.role_name if u.role else "").lower()
                emp_id = (u.employee_id or "").upper()
                
                if not auto_reviewer and ("reviewer" in r_name or emp_id.startswith("RW")) and "admin" not in r_name and "employee" not in r_name:
                    auto_reviewer = u
                elif not auto_manager and ("manager" in r_name or emp_id.startswith("MN")) and "admin" not in r_name and "employee" not in r_name:
                    auto_manager = u
                    
            if not auto_reviewer or not auto_manager:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to automatically assign reviewers: An active Reviewer and an active Manager are both required for automatic workflow assignment."
                )

            # Step 1: Reviewer (Pending)
            db.add(Review(
                decision_id=new_decision.id,
                reviewer_id=auto_reviewer.id,
                status="Pending",
                approval_type="Sequential"
            ))
            # Step 2: Manager (Queued)
            db.add(Review(
                decision_id=new_decision.id,
                reviewer_id=auto_manager.id,
                status="Queued",
                approval_type="Sequential"
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
        
        was_rejected = (db_decision.status == "Rejected")
        # If decision was rejected, move it back to Pending (resubmit)
        if was_rejected:
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
            
        # 3. Update or rebuild reviews with strict rules (preserve existing comments history)
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
                    existing_rev = db.query(Review).filter(Review.decision_id == decision_id, Review.reviewer_id == u.id).first()
                    if existing_rev:
                        existing_rev.status = "Pending"
                    else:
                        db.add(Review(
                            decision_id=decision_id,
                            reviewer_id=u.id,
                            status="Pending",
                            approval_type="Sequential"
                        ))
        else:
            for rev in valid_reviewers:
                existing_rev = db.query(Review).filter(Review.decision_id == decision_id, Review.reviewer_id == rev.reviewer_id).first()
                if existing_rev:
                    existing_rev.status = "Pending"
                    if rev.deadline:
                        existing_rev.deadline = rev.deadline
                else:
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
        
        change_reason = full_decision.change_reason
        if not change_reason:
            change_reason = "Resubmitted decision after addressing review feedback" if was_rejected else "System Update"

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
            changed_by=full_decision.created_by,
            change_reason=change_reason
        )
        db.add(new_version)
                
        db.commit()
        db.refresh(db_decision)

        # Trigger live notifications for resubmission
        if was_rejected:
            try:
                from app.services.notification_service import NotificationService
                NotificationService.create_notification(
                    db,
                    user_id=db_decision.created_by,
                    message=f"Your decision 'DEC-{db_decision.id}: {db_decision.title}' has been resubmitted for review.",
                    notification_type="Decision Status"
                )
                for rev_id in assigned_reviewer_ids:
                    NotificationService.create_notification(
                        db,
                        user_id=rev_id,
                        message=f"The decision 'DEC-{db_decision.id}: {db_decision.title}' has been updated and resubmitted for your review.",
                        notification_type="Review Request"
                    )
            except Exception as e:
                print("Error generating resubmission notifications:", e)
        return db_decision

    @staticmethod
    def get_all_decisions(db: Session, user_id: int = None, role_name: str = None):
        from sqlalchemy.orm import joinedload
        from app.models.user import User
        from app.models.review import Review

        query = db.query(Decision).options(joinedload(Decision.creator), joinedload(Decision.category))

        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            target_uids = {user_id}
            if user:
                if user.email:
                    for (uid,) in db.query(User.id).filter((User.email == user.email) | (User.email_original == user.email)).all():
                        target_uids.add(uid)
                if getattr(user, 'email_original', None):
                    for (uid,) in db.query(User.id).filter((User.email == user.email_original) | (User.email_original == user.email_original)).all():
                        target_uids.add(uid)
                if user.full_name:
                    for (uid,) in db.query(User.id).filter(User.full_name == user.full_name).all():
                        target_uids.add(uid)

            current_role = role_name
            if user and user.role and not current_role:
                current_role = user.role.role_name

            role_lower = (current_role or "").strip().lower()

            if role_lower in ["employee", "emp"]:
                # Employee: ONLY own decisions
                query = query.filter(Decision.created_by.in_(list(target_uids)))
            elif role_lower in ["reviewer", "rw"]:
                # Reviewer: ONLY assigned reviews OR created by user
                assigned_decision_ids = db.query(Review.decision_id).filter(Review.reviewer_id.in_(list(target_uids))).subquery()
                query = query.filter((Decision.created_by.in_(list(target_uids))) | (Decision.id.in_(assigned_decision_ids)))
            elif role_lower in ["manager", "mn", "lead"]:
                # Manager: Created by user OR team members' decisions / pending reviews
                if user and user.team_id:
                    team_user_ids = db.query(User.id).filter(User.team_id == user.team_id).subquery()
                    query = query.filter((Decision.created_by.in_(list(target_uids))) | (Decision.created_by.in_(team_user_ids)))
                else:
                    query = query.filter((Decision.created_by.in_(list(target_uids))) | (Decision.status.in_(["Pending", "In Review", "Approved", "Rejected"])))
            elif role_lower in ["administrator", "admin", "ad"]:
                # Admin: All decisions
                pass
            else:
                # Default fallback for unlisted roles: only own decisions
                query = query.filter(Decision.created_by.in_(list(target_uids)))

        return query.order_by(Decision.id.desc()).all()

    @staticmethod
    def get_decision_by_id(db: Session, decision_id: int, user_id: int = None):
        from app.models.user import User
        from app.models.review import Review

        db_decision = db.query(Decision).filter(Decision.id == decision_id).first()
        if not db_decision:
            return None

        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            target_uids = {user_id}
            if user:
                if user.email:
                    for (uid,) in db.query(User.id).filter((User.email == user.email) | (User.email_original == user.email)).all():
                        target_uids.add(uid)
                if getattr(user, 'email_original', None):
                    for (uid,) in db.query(User.id).filter((User.email == user.email_original) | (User.email_original == user.email_original)).all():
                        target_uids.add(uid)
                if user.full_name:
                    for (uid,) in db.query(User.id).filter(User.full_name == user.full_name).all():
                        target_uids.add(uid)

            if user and user.role:
                role_lower = user.role.role_name.strip().lower()

                if role_lower in ["employee", "emp"]:
                    if db_decision.created_by not in target_uids:
                        return None  # Unauthorized for this employee
                elif role_lower in ["reviewer", "rw"]:
                    is_assigned = db.query(Review).filter(Review.decision_id == decision_id, Review.reviewer_id.in_(list(target_uids))).first()
                    if db_decision.created_by not in target_uids and not is_assigned:
                        return None  # Unauthorized for this reviewer
                elif role_lower in ["manager", "mn", "lead"]:
                    if db_decision.created_by not in target_uids and user.team_id:
                        creator = db.query(User).filter(User.id == db_decision.created_by).first()
                        if not creator or creator.team_id != user.team_id:
                            return None  # Unauthorized for this manager

            try:
                from app.models.activity_log import ActivityLog
                log_entry = ActivityLog(
                    user_id=user_id,
                    action=f"Accessed Decision DEC-{decision_id}",
                    details=f"User accessed and viewed decision details for DEC-{decision_id}"
                )
                db.add(log_entry)
                db.commit()
            except Exception:
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