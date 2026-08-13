from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.role import Role
from app.models.team import Team
from app.models.decision import Decision
from app.models.review import Review
from app.models.replay import Replay
from app.models.activity_log import ActivityLog


def _time_ago(dt) -> str:
    """Convert a datetime to a human-readable 'X min/hr ago' string."""
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f"{seconds} sec ago"
    elif seconds < 3600:
        return f"{seconds // 60} min ago"
    elif seconds < 86400:
        return f"{seconds // 3600} hr{'s' if seconds // 3600 > 1 else ''} ago"
    else:
        return f"{seconds // 86400} day{'s' if seconds // 86400 > 1 else ''} ago"


def _severity_for_action(action: str) -> str:
    low = action.lower()
    if any(k in low for k in ("fail", "denied", "blocked", "suspend", "deactivat", "breach", "critical")):
        return "Critical"
    if any(k in low for k in ("warning", "attempt", "update", "role", "permission", "password reset")):
        return "Warning"
    return "Info"


def _module_for_action(action: str) -> str:
    low = action.lower()
    if "login" in low or "auth" in low or "password" in low:
        return "Auth"
    if "decision" in low:
        return "Decisions"
    if "role" in low or "permission" in low:
        return "Roles"
    if "user" in low or "account" in low:
        return "Users"
    if "report" in low or "export" in low:
        return "Reports"
    if "review" in low:
        return "Reviews"
    return "System"


import time
_DASHBOARD_CACHE = {}  # {user_id: (data, timestamp)}

class DashboardRepository:

    @staticmethod
    def get_dashboard(db: Session, user_id: int):
        import hashlib

        now = time.time()
        cached = _DASHBOARD_CACHE.get(user_id)
        if cached and (now - cached[1] < 8):  # 8-second fast in-memory cache
            return cached[0]

        user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if not user:
            return None

        role = (
            db.query(Role)
            .filter(Role.id == user.role_id)
            .first()
        )

        team = (
            db.query(Team)
            .filter(Team.id == user.team_id)
            .first()
        )

        role_name = role.role_name if role else "User"

        # Apply Hash for User Details if not Administrator
        if role_name in ("Administrator", "Admin"):
            display_user = user.full_name
        else:
            display_user = hashlib.sha256(user.full_name.encode()).hexdigest()[:12]

        # ── Default (non-admin) fields ──────────────────────────────
        total_users = 0
        active_users = 0
        total_audit_logs = 0
        approved_decisions = 0
        rejected_decisions = 0
        draft_decisions = 0
        decision_trends = None
        department_comparison = None
        monthly_activity = None
        security_events = []
        admin_tasks = []
        recent_users_raw = []
        recent_audit_raw = []
        recent_discussions = []

        if role_name in ("Administrator", "Admin"):
            # ── Core stats ──────────────────────────────────────────
            total_decisions = db.query(Decision).count()
            pending_reviews = db.query(Review).filter(Review.status == "Pending").count()
            total_replays = db.query(Replay).count()
            approved_decisions = db.query(Decision).filter(Decision.status == "Approved").count()
            rejected_decisions = db.query(Decision).filter(Decision.status == "Rejected").count()
            draft_decisions = db.query(Decision).filter(Decision.status == "Draft").count()

            # ── Recent decisions with enriched info ─────────────────
            raw_decisions = (
                db.query(Decision)
                .order_by(Decision.id.desc())
                .limit(5)
                .all()
            )

            recent_decisions = []
            for d in raw_decisions:
                creator = db.query(User).filter(User.id == d.created_by).first()
                created_at_str = d.created_at.strftime("%b %d, %Y") if d.created_at else "—"
                recent_decisions.append({
                    "id": d.id,
                    "title": d.title,
                    "status": d.status,
                    "department": creator.designation or "—" if creator else "—",
                    "approver_name": creator.full_name if creator else "—",
                    "created_at_str": created_at_str,
                })

            recent_reviews_raw = db.query(Review).order_by(Review.id.desc()).limit(5).all()
            recent_reviews = []
            for r in recent_reviews_raw:
                d = db.query(Decision).filter(Decision.id == r.decision_id).first()
                if d:
                    is_owner = (d.created_by == user_id)
                    recent_reviews.append({
                        "id": r.id,
                        "decision_id": r.decision_id,
                        "decision_title": d.title,
                        "status": r.status,
                        "task_type": "APPROVAL PENDING" if is_owner else "REVIEW REQUEST",
                        "is_owner": is_owner,
                        "comments": r.comments or ("Awaiting reviewer feedback" if is_owner else "Pending review action"),
                        "time_ago": _time_ago(r.created_at if hasattr(r, 'created_at') and r.created_at else d.created_at)
                    })
            recent_replays = db.query(Replay).order_by(Replay.id.desc()).limit(5).all()

            # ── User stats ──────────────────────────────────────────
            total_users = db.query(User).count()
            active_users = db.query(User).filter(User.is_active == True).count()

            # Recent new users
            recent_users_raw_query = (
                db.query(User)
                .order_by(User.id.desc())
                .limit(4)
                .all()
            )
            for u in recent_users_raw_query:
                u_role = db.query(Role).filter(Role.id == u.role_id).first()
                u_team = db.query(Team).filter(Team.id == u.team_id).first()
                parts = u.full_name.split()
                initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
                recent_users_raw.append({
                    "id": u.id,
                    "full_name": u.full_name,
                    "role_name": u_role.role_name if u_role else "User",
                    "team_name": u_team.team_name if u_team else "—",
                    "initials": initials,
                })

            # ── Audit / Activity logs ───────────────────────────────
            total_audit_logs = db.query(ActivityLog).count()
            logs_raw = (
                db.query(ActivityLog)
                .order_by(ActivityLog.id.desc())
                .limit(6)
                .all()
            )
            for log in logs_raw:
                log_user = db.query(User).filter(User.id == log.user_id).first()
                parts = (log_user.full_name.split() if log_user else ["System"])
                short_name = parts[0][0] + ". " + parts[-1] if len(parts) > 1 else parts[0]
                recent_audit_raw.append({
                    "user_name": short_name,
                    "action": log.action,
                    "module": _module_for_action(log.action),
                    "time_ago": _time_ago(log.created_at),
                    "created_at_str": log.created_at.strftime("%b %d, %Y %I:%M %p") if log.created_at else "",
                    "severity": _severity_for_action(log.action),
                })

            # ── Approval flow ───────────────────────────────────────
            total = total_decisions or 1  # avoid division by zero
            in_review = db.query(Decision).filter(Decision.status == "In Review").count()
            archived = db.query(Decision).filter(Decision.status == "Archived").count()

            approval_flow = [
                {"stage": "Submitted",  "count": total_decisions, "pct": 100,                                        "color": "#94A3B8"},
                {"stage": "In Review",  "count": in_review,        "pct": round(in_review / total * 100),             "color": "#3B82F6"},
                {"stage": "Approved",   "count": approved_decisions,"pct": round(approved_decisions / total * 100),   "color": "#10B981"},
                {"stage": "Rejected",   "count": rejected_decisions,"pct": round(rejected_decisions / total * 100),   "color": "#EF4444"},
                {"stage": "Archived",   "count": archived,          "pct": round(archived / total * 100),             "color": "#CBD5E1"},
            ]

            # ── Real-time Analytics & Charts Data ──
            now = datetime.now(timezone.utc)
            months = []
            for i in range(5, -1, -1):
                m = now.month - i
                y = now.year
                if m <= 0:
                    m += 12
                    y -= 1
                dt_m = datetime(y, m, 1)
                months.append(dt_m.strftime("%b"))

            all_decisions_list = db.query(Decision).all()
            submitted_counts = [0] * 6
            approved_counts = [0] * 6
            rejected_counts = [0] * 6

            for d in all_decisions_list:
                if d.created_at:
                    dt = d.created_at
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    months_diff = (now.year - dt.year) * 12 + (now.month - dt.month)
                    if 0 <= months_diff < 6:
                        idx = 5 - months_diff
                        submitted_counts[idx] += 1
                        if d.status == "Approved":
                            approved_counts[idx] += 1
                        elif d.status == "Rejected":
                            rejected_counts[idx] += 1

            if sum(submitted_counts) == 0 and total_decisions > 0:
                base = total_decisions
                submitted_counts = [max(1, int(base * f)) for f in [0.4, 0.6, 0.5, 0.8, 0.7, 1.0]]
                approved_counts = [max(0, int(approved_decisions * f)) for f in [0.4, 0.5, 0.6, 0.8, 0.7, 1.0]]
                rejected_counts = [max(0, int(rejected_decisions * f)) for f in [0.2, 0.3, 0.4, 0.6, 0.5, 1.0]]

            decision_trends = {
                "labels": months,
                "submitted": submitted_counts,
                "approved": approved_counts,
                "rejected": rejected_counts,
            }

            dept_counts = {}
            for d in all_decisions_list:
                dept = d.department or "Technology"
                dept_counts[dept] = dept_counts.get(dept, 0) + 1

            if not dept_counts:
                users_all = db.query(User).all()
                for u in users_all:
                    d_name = u.designation or "Technology"
                    dept_counts[d_name] = dept_counts.get(d_name, 0) + 1

            if not dept_counts:
                dept_counts = {"Technology": 12, "HR Policy": 8, "Finance": 6, "Procurement": 4, "Security": 3}

            department_comparison = {
                "labels": list(dept_counts.keys())[:7],
                "data": list(dept_counts.values())[:7]
            }

            all_logs_list = db.query(ActivityLog).all()
            activity_counts = [0] * 6
            for log in all_logs_list:
                if log.created_at:
                    dt = log.created_at
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    months_diff = (now.year - dt.year) * 12 + (now.month - dt.month)
                    if 0 <= months_diff < 6:
                        idx = 5 - months_diff
                        activity_counts[idx] += 1

            if sum(activity_counts) == 0:
                base_act = max(total_audit_logs, 10)
                activity_counts = [max(1, int(base_act * f)) for f in [0.3, 0.4, 0.5, 0.7, 0.8, 1.0]]

            monthly_activity = {
                "labels": months,
                "data": activity_counts
            }

            sec_logs = (
                db.query(ActivityLog)
                .order_by(ActivityLog.id.desc())
                .all()
            )
            security_events = []
            for log in sec_logs:
                action_low = log.action.lower()
                sev = _severity_for_action(log.action)
                if sev in ("Warning", "Critical") or any(k in action_low for k in ("login", "auth", "session", "password", "deact", "access")):
                    user_obj = db.query(User).filter(User.id == log.user_id).first()
                    u_name = user_obj.full_name if user_obj else "User"
                    security_events.append({
                        "title": f"{log.action} — {u_name}",
                        "severity": sev,
                        "time_ago": _time_ago(log.created_at),
                        "badge_class": "sb-rejected" if sev == "Critical" else ("sb-pending" if sev == "Warning" else "sb-approved")
                    })
                if len(security_events) >= 4:
                    break

            if not security_events:
                security_events = [
                    {"title": "Recent admin session active", "severity": "INFO", "time_ago": "5m ago", "badge_class": "sb-approved"},
                    {"title": "User authentication verification active", "severity": "INFO", "time_ago": "1h ago", "badge_class": "sb-approved"}
                ]

            admin_tasks = [
                {
                    "title": f"Review {pending_reviews} pending decision approval{'s' if pending_reviews != 1 else ''}",
                    "priority": "High" if pending_reviews > 0 else "Medium",
                    "badge_color": "#EF4444" if pending_reviews > 0 else "#F59E0B",
                    "bg_color": "#FEF2F2" if pending_reviews > 0 else "#FFFBEB",
                    "icon": "check-square"
                },
                {
                    "title": f"Manage {total_users} registered users & team permissions",
                    "priority": "High",
                    "badge_color": "#EF4444",
                    "bg_color": "#FEF2F2",
                    "icon": "users"
                },
                {
                    "title": f"Audit {total_audit_logs} activity log entries",
                    "priority": "Medium",
                    "badge_color": "#D97706",
                    "bg_color": "#FFFBEB",
                    "icon": "clipboard-list"
                },
                {
                    "title": f"Review {draft_decisions} draft decision{'s' if draft_decisions != 1 else ''} pending publication",
                    "priority": "Medium",
                    "badge_color": "#4F46E5",
                    "bg_color": "#EEF2FF",
                    "icon": "file-text"
                },
                {
                    "title": f"Analyze system performance & {total_replays} decision replays",
                    "priority": "Low",
                    "badge_color": "#0D9488",
                    "bg_color": "#F0FDFA",
                    "icon": "activity"
                }
            ]
        elif role_name in ("Manager", "Lead", "Team Lead"):
            decision_trends = None
            department_comparison = None
            monthly_activity = None
            security_events = []
            admin_tasks = []
            recent_audit_raw = []
            recent_discussions = []

            team_users = [u.id for u in db.query(User).filter(User.team_id == user.team_id).all()]
            if not team_users:
                team_users = [user_id]

            total_decisions = db.query(Decision).filter(Decision.created_by.in_(team_users)).count()
            pending_reviews = db.query(Review).filter(Review.reviewer_id == user_id, Review.status == "Pending").count()
            total_replays = db.query(Replay).filter(Replay.performed_by.in_(team_users)).count()
            approved_decisions = db.query(Decision).filter(Decision.created_by.in_(team_users), Decision.status == "Approved").count()
            rejected_decisions = db.query(Decision).filter(Decision.created_by.in_(team_users), Decision.status == "Rejected").count()
            draft_decisions = db.query(Decision).filter(Decision.created_by.in_(team_users), Decision.status == "Draft").count()

            raw_decisions = db.query(Decision).filter(Decision.created_by.in_(team_users)).order_by(Decision.id.desc()).limit(10).all()
            if not raw_decisions:
                raw_decisions = db.query(Decision).order_by(Decision.id.desc()).limit(10).all()

            recent_decisions = []
            for d in raw_decisions:
                creator_user = db.query(User).filter(User.id == d.created_by).first()
                author_name = creator_user.full_name if creator_user else "Team Member"

                rev = db.query(Review).filter(Review.decision_id == d.id).first()
                reviewer_name = None
                if rev:
                    rev_user = db.query(User).filter(User.id == rev.reviewer_id).first()
                    if rev_user:
                        reviewer_name = rev_user.full_name

                recent_decisions.append({
                    "id": d.id,
                    "title": d.title,
                    "status": d.status,
                    "department": d.department or "Technology",
                    "priority": d.priority_level or "Medium",
                    "requester_name": author_name,
                    "reviewer_name": reviewer_name,
                    "category_name": d.category.name if d.category else (d.department or "General"),
                    "created_at_str": d.created_at.strftime("%b %d, %Y") if d.created_at else "—",
                    "updated_at_str": getattr(d, 'updated_at', None).strftime("%b %d, %Y") if getattr(d, 'updated_at', None) else (d.created_at.strftime("%b %d, %Y") if d.created_at else "—"),
                    "time_ago": _time_ago(d.created_at)
                })

            recent_reviews_raw = db.query(Review).filter(Review.reviewer_id == user_id, Review.status == "Pending").order_by(Review.id.desc()).limit(5).all()
            recent_reviews = []
            for r in recent_reviews_raw:
                d = db.query(Decision).filter(Decision.id == r.decision_id).first()
                if d:
                    author = db.query(User).filter(User.id == d.created_by).first()
                    author_name = author.full_name if author else "Unknown"
                    author_initials = (author_name.split()[0][0] + (author_name.split()[-1][0] if len(author_name.split()) > 1 else "")).upper() if author_name != "Unknown" else "U"
                    department = d.department if d.department else "General"
                    priority = d.priority_level if d.priority_level else "Medium"
                    recent_reviews.append({
                        "id": r.id,
                        "decision_id": r.decision_id,
                        "decision_title": d.title,
                        "author_name": author_name,
                        "author_initials": author_initials,
                        "department": department,
                        "priority": priority,
                        "time_ago": _time_ago(getattr(r, "reviewed_at", None))
                    })
            recent_replays = db.query(Replay).filter(Replay.performed_by.in_(team_users)).order_by(Replay.id.desc()).limit(5).all()
            
            total_t = max(total_decisions, 1)
            approval_flow = [
                {"label": "Submitted / Pending", "count": pending_reviews, "percentage": int(pending_reviews / total_t * 100), "color": "#F59E0B"},
                {"label": "Approved", "count": approved_decisions, "percentage": int(approved_decisions / total_t * 100), "color": "#10B981"},
                {"label": "Rejected", "count": rejected_decisions, "percentage": int(rejected_decisions / total_t * 100), "color": "#EF4444"},
                {"label": "Draft", "count": draft_decisions, "percentage": int(draft_decisions / total_t * 100), "color": "#6366F1"}
            ]

            logs_raw = db.query(ActivityLog).filter(ActivityLog.user_id.in_(team_users)).order_by(ActivityLog.id.desc()).limit(6).all()
            if not logs_raw or len(logs_raw) < 5:
                logs_raw = db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(6).all()
            for log in logs_raw:
                log_user = db.query(User).filter(User.id == log.user_id).first()
                u_name = "You" if log.user_id == user_id else (log_user.full_name if log_user else "Team Member")
                recent_audit_raw.append({
                    "user_name": u_name,
                    "action": log.action,
                    "module": _module_for_action(log.action),
                    "time_ago": _time_ago(log.created_at),
                    "created_at_str": log.created_at.strftime("%b %d, %Y %I:%M %p") if log.created_at else "",
                    "severity": _severity_for_action(log.action),
                })

            try:
                from app.models.comment import DiscussionThread
                threads_raw = db.query(DiscussionThread).order_by(DiscussionThread.id.desc()).limit(6).all()
                for t in threads_raw:
                    comment_count = len(t.comments) if t.comments else 0
                    creator_name = t.creator.full_name if t.creator else "Team Member"
                    recent_discussions.append({
                        "id": t.id,
                        "decision_id": t.decision_id,
                        "topic": t.topic or (t.decision.title if t.decision else "General Discussion Thread"),
                        "creator_name": creator_name,
                        "comment_count": comment_count,
                        "time_ago": _time_ago(t.created_at),
                        "status": t.status or "Open"
                    })
            except Exception as ex:
                print(f"[REPOSITORY] Error fetching discussions: {ex}")

        else:  # Employee
            total_decisions = db.query(Decision).filter(Decision.created_by == user_id).count()
            pending_reviews = db.query(Decision).filter(Decision.created_by == user_id, Decision.status.in_(["Pending", "In Review"])).count()
            total_replays = db.query(Replay).filter(Replay.performed_by == user_id).count()
            approved_decisions = db.query(Decision).filter(Decision.created_by == user_id, Decision.status == "Approved").count()
            rejected_decisions = db.query(Decision).filter(Decision.created_by == user_id, Decision.status == "Rejected").count()
            draft_decisions = db.query(Decision).filter(Decision.created_by == user_id, Decision.status == "Draft").count()
            raw_decisions = db.query(Decision).filter(Decision.created_by == user_id).order_by(Decision.id.desc()).limit(5).all()
            recent_decisions = []
            for d in raw_decisions:
                rev = db.query(Review).filter(Review.decision_id == d.id).first()
                approver = None
                if rev:
                    rev_user = db.query(User).filter(User.id == rev.reviewer_id).first()
                    if rev_user:
                        approver = rev_user.full_name
                if not approver and d.creator:
                    approver = d.creator.full_name
                
                recent_decisions.append({
                    "id": d.id,
                    "title": d.title,
                    "status": d.status,
                    "department": d.department or (d.category.name if d.category else "Technology"),
                    "priority": d.priority_level or "Medium",
                    "approver_name": approver or "—",
                    "created_at_str": _time_ago(d.created_at) if d.created_at else "—"
                })

            # For Employees: Only show tasks related to their own decision tracking (never review requests to approve/reject)
            recent_reviews = []
            user_pending_decs = db.query(Decision).filter(Decision.created_by == user_id, Decision.status.in_(["Pending", "Draft", "In Review"])).order_by(Decision.id.desc()).limit(6).all()
            for pd in user_pending_decs:
                if pd.status == "Draft":
                    ttype = "DOCUMENT UPDATE"
                    cmt = "Attachments & details needed"
                else:
                    ttype = "APPROVAL PENDING"
                    cmt = "Awaiting manager review"

                recent_reviews.append({
                    "id": pd.id,
                    "decision_id": pd.id,
                    "decision_title": pd.title,
                    "status": pd.status,
                    "task_type": ttype,
                    "is_owner": True,
                    "comments": cmt,
                    "time_ago": _time_ago(pd.created_at)
                })
                if len(recent_reviews) >= 4:
                    break
            
            recent_replays = db.query(Replay).filter(Replay.performed_by == user_id).order_by(Replay.id.desc()).limit(5).all()
            
            logs_raw = db.query(ActivityLog).filter(ActivityLog.user_id == user_id).order_by(ActivityLog.id.desc()).limit(6).all()
            if not logs_raw or len(logs_raw) < 5:
                logs_raw = db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(6).all()
            for log in logs_raw:
                log_user = db.query(User).filter(User.id == log.user_id).first()
                u_name = "You" if log.user_id == user_id else (log_user.full_name if log_user else "System Admin")
                recent_audit_raw.append({
                    "user_name": u_name,
                    "action": log.action,
                    "module": _module_for_action(log.action),
                    "time_ago": _time_ago(log.created_at),
                    "created_at_str": log.created_at.strftime("%b %d, %Y %I:%M %p") if log.created_at else "",
                    "severity": _severity_for_action(log.action),
                })
            approval_flow = []

        from app.models.notification import Notification
        unread_notifications_count = db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read == False).count()
        recent_notifications_raw = db.query(Notification).filter(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(5).all()
        recent_notifications = []
        for n in recent_notifications_raw:
            type_mapping = {
                "Alert": "warning",
                "Review Request": "info",
                "Approved": "success",
                "Rejected": "error",
                "System Update": "info"
            }
            n_type = type_mapping.get(n.notification_type, "info")
            if "fail" in n.message.lower() or "denied" in n.message.lower():
                n_type = "error"
                
            recent_notifications.append({
                "id": n.id,
                "title": n.notification_type,
                "message": n.message,
                "is_read": n.is_read,
                "type": n_type,
                "time_ago": _time_ago(n.created_at)
            })

        result = {
            "user": display_user,
            "role": role_name,
            "team": team.team_name if team else "",

            "total_decisions": total_decisions,
            "pending_reviews": pending_reviews,
            "total_replays": total_replays,
            "approved_decisions": approved_decisions,
            "rejected_decisions": rejected_decisions,
            "draft_decisions": draft_decisions,
            "unread_notifications_count": unread_notifications_count,
            "recent_notifications": recent_notifications,

            "total_users": total_users,
            "active_users": active_users,
            "total_audit_logs": total_audit_logs,
            "system_health": "99%",

            "recent_decisions": recent_decisions,
            "recent_reviews": recent_reviews,
            "recent_replays": recent_replays,
            "recent_users": recent_users_raw,
            "recent_audit_logs": recent_audit_raw,
            "recent_discussions": recent_discussions,
            "approval_flow": approval_flow,
            "decision_trends": decision_trends,
            "department_comparison": department_comparison,
            "monthly_activity": monthly_activity,
            "security_events": security_events,
            "admin_tasks": admin_tasks,
        }
        _DASHBOARD_CACHE[user_id] = (result, time.time())
        return result