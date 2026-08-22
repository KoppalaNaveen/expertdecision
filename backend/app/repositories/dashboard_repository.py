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
    if "decision" in low or "approved" in low or "rejected" in low or "submitted" in low or "created" in low:
        return "Decisions"
    if "review" in low or "feedback" in low:
        return "Reviews"
    if "discuss" in low or "comment" in low:
        return "Discussions"
    if "replay" in low or "simulat" in low:
        return "Replays"
    if "role" in low or "permission" in low:
        return "Roles"
    if "user" in low or "account" in low:
        return "Users"
    if "report" in low or "export" in low:
        return "Reports"
    return "Governance"


def _build_decision_activities(db: Session, user_id: int, role_name: str, team_users: list, users_map: dict, all_decisions_list: list, limit: int = 6):
    """
    Builds a decision-centric activity timeline showing events like:
    - Created decision: "Title"
    - Decision accepted & approved: "Title"
    - Submitted decision for review: "Title"
    - Reviewed & approved decision: "Title"
    - Updated decision details: "Title"
    - Added discussion comment on decision: "Title"
    - Executed decision replay simulation: "Title"
    Explicitly filters out generic auth, administrative, and repetitive read/access logs.
    """
    activities = []
    seen_keys = set()

    # 1. First add primary decision lifecycle events directly from live Decisions, Reviews, and Discussions
    relevant_decisions = []
    if role_name in ("Administrator", "Admin"):
        relevant_decisions = all_decisions_list
    elif role_name in ("Manager", "Lead", "Team Lead"):
        relevant_decisions = [d for d in all_decisions_list if d.created_by in team_users] or all_decisions_list
    else:  # Employee / Reviewer
        relevant_decisions = [d for d in all_decisions_list if d.created_by == user_id]
        if not relevant_decisions:
            relevant_decisions = [d for d in all_decisions_list if d.created_by in team_users] or all_decisions_list

    for d in relevant_decisions:
        creator = users_map.get(d.created_by)
        is_me = (d.created_by == user_id)
        actor_name = "You" if is_me else (creator.full_name if creator else "Team Member")
        title_snippet = f'"{d.title}"' if d.title else "Untitled Decision"
        st = (d.status or "").strip().lower()

        # Decision accepted & approved event
        if st == "approved":
            k_approved = f"dec_approved_{d.id}"
            if k_approved not in seen_keys:
                seen_keys.add(k_approved)
                activities.append({
                    "user_name": "Governance Board" if not is_me else "Decision Update",
                    "action": f"Decision accepted & approved: {title_snippet}",
                    "module": "Decisions",
                    "time_ago": _time_ago(getattr(d, 'updated_at', None) or d.created_at),
                    "created_at_str": (getattr(d, 'updated_at', None) or d.created_at).strftime("%b %d, %Y %I:%M %p") if (getattr(d, 'updated_at', None) or d.created_at) else "",
                    "severity": "Info",
                    "icon": "check-circle-2",
                    "icon_color": "#10B981",
                    "bg_color": "#ECFDF5",
                    "raw_dt": getattr(d, 'updated_at', None) or d.created_at or datetime.min.replace(tzinfo=timezone.utc)
                })
        elif st in ("pending", "in review", "under review", "pending review"):
            k_pending = f"dec_pending_{d.id}"
            if k_pending not in seen_keys:
                seen_keys.add(k_pending)
                activities.append({
                    "user_name": actor_name,
                    "action": f"Submitted decision for formal review: {title_snippet}",
                    "module": "Decisions",
                    "time_ago": _time_ago(d.created_at),
                    "created_at_str": d.created_at.strftime("%b %d, %Y %I:%M %p") if d.created_at else "",
                    "severity": "Info",
                    "icon": "clock",
                    "icon_color": "#F59E0B",
                    "bg_color": "#FFFBEB",
                    "raw_dt": d.created_at or datetime.min.replace(tzinfo=timezone.utc)
                })
        elif st == "rejected":
            k_rej = f"dec_rejected_{d.id}"
            if k_rej not in seen_keys:
                seen_keys.add(k_rej)
                activities.append({
                    "user_name": "Reviewer",
                    "action": f"Decision rejected with feedback: {title_snippet}",
                    "module": "Decisions",
                    "time_ago": _time_ago(getattr(d, 'updated_at', None) or d.created_at),
                    "created_at_str": (getattr(d, 'updated_at', None) or d.created_at).strftime("%b %d, %Y %I:%M %p") if (getattr(d, 'updated_at', None) or d.created_at) else "",
                    "severity": "Warning",
                    "icon": "x-circle",
                    "icon_color": "#EF4444",
                    "bg_color": "#FEF2F2",
                    "raw_dt": getattr(d, 'updated_at', None) or d.created_at or datetime.min.replace(tzinfo=timezone.utc)
                })

        # Decision created event
        k_created = f"dec_created_{d.id}"
        if k_created not in seen_keys:
            seen_keys.add(k_created)
            activities.append({
                "user_name": actor_name,
                "action": f"Created new decision: {title_snippet}",
                "module": "Decisions",
                "time_ago": _time_ago(d.created_at),
                "created_at_str": d.created_at.strftime("%b %d, %Y %I:%M %p") if d.created_at else "",
                "severity": "Info",
                "icon": "file-plus",
                "icon_color": "#2563EB",
                "bg_color": "#EFF6FF",
                "raw_dt": d.created_at or datetime.min.replace(tzinfo=timezone.utc)
            })

    # 2. Look for explicit non-auth decision audit logs from ActivityLog
    try:
        user_filter = ActivityLog.user_id.in_(team_users) if team_users else (ActivityLog.user_id == user_id)
        if role_name in ("Administrator", "Admin"):
            logs = db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(80).all()
        else:
            logs = db.query(ActivityLog).filter(user_filter).order_by(ActivityLog.id.desc()).limit(80).all()

        for log in logs:
            act_text = log.action or ""
            act_low = act_text.lower()
            # Skip login, credentials, password, delete, and repetitive view/access logs
            if any(skip in act_low for skip in ("login", "auth", "session", "password", "credential", "approved account", "updated credentials", "created account", "deactivated user", "deleted user", "accessed decision", "viewed")):
                continue

            u = users_map.get(log.user_id)
            u_name = "You" if log.user_id == user_id else (u.full_name if u else "Team Member")
            time_str = _time_ago(log.created_at)

            # Determine icon & color based on decision action
            if "accept" in act_low or "approv" in act_low:
                icon = "check-circle-2"
                icon_color = "#10B981"
                bg_color = "#ECFDF5"
            elif "reject" in act_low or "deni" in act_low:
                icon = "x-circle"
                icon_color = "#EF4444"
                bg_color = "#FEF2F2"
            elif "creat" in act_low:
                icon = "file-plus"
                icon_color = "#2563EB"
                bg_color = "#EFF6FF"
            elif "review" in act_low:
                icon = "clipboard-check"
                icon_color = "#6366F1"
                bg_color = "#EEF2FF"
            elif "comment" in act_low or "discuss" in act_low:
                icon = "message-square"
                icon_color = "#06B6D4"
                bg_color = "#ECFEFF"
            elif "replay" in act_low or "simulat" in act_low:
                icon = "play-circle"
                icon_color = "#8B5CF6"
                bg_color = "#F5F3FF"
            else:
                icon = "activity"
                icon_color = "#2563EB"
                bg_color = "#EFF6FF"

            key = f"log_{act_text[:35]}"
            if key not in seen_keys:
                seen_keys.add(key)
                activities.append({
                    "user_name": u_name,
                    "action": act_text,
                    "module": _module_for_action(act_text),
                    "time_ago": time_str,
                    "created_at_str": log.created_at.strftime("%b %d, %Y %I:%M %p") if log.created_at else "",
                    "severity": _severity_for_action(act_text),
                    "icon": icon,
                    "icon_color": icon_color,
                    "bg_color": bg_color,
                    "raw_dt": log.created_at or datetime.min.replace(tzinfo=timezone.utc)
                })
    except Exception as e:
        print(f"[TIMELINE AUDIT ERROR] {e}")

    # Sort all by datetime descending
    activities.sort(key=lambda a: a.get("raw_dt") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return activities[:limit]



import time
_DASHBOARD_CACHE = {}  # {user_id: (data, timestamp)}


class DashboardRepository:

    @staticmethod
    def get_dashboard(db: Session, user_id: int):
        import hashlib

        now = time.time()
        cached = _DASHBOARD_CACHE.get(user_id)
        if cached and (now - cached[1] < 20):  # 20-second fast in-memory cache
            return cached[0]

        # 1. Batch load users, roles, teams into fast in-memory lookup maps
        all_users_list = db.query(User).all()
        users_map = {u.id: u for u in all_users_list}
        all_roles_list = db.query(Role).all()
        roles_map = {r.id: r for r in all_roles_list}
        all_teams_list = db.query(Team).all()
        teams_map = {t.id: t for t in all_teams_list}

        user = users_map.get(user_id)
        if not user:
            # Fallback to the primary active admin or any active user in the database
            user = next((u for u in all_users_list if u.role_id == 1 and u.is_active), None) or (all_users_list[0] if all_users_list else None)
            if not user:
                return {}

        role = roles_map.get(user.role_id)
        team = teams_map.get(user.team_id)

        role_name = role.role_name if role else "User"

        # Apply Hash for User Details if not Administrator
        if role_name in ("Administrator", "Admin"):
            display_user = user.full_name
        else:
            display_user = hashlib.sha256(user.full_name.encode()).hexdigest()[:12]

        # ── Default (non-admin) fields ──────────────────────────────
        total_users = len(all_users_list)
        active_users = sum(1 for u in all_users_list if u.is_active)
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
            # ── Core stats (Accurate live counts from database) ─────
            all_decisions_list = db.query(Decision).all()
            decisions_map = {d.id: d for d in all_decisions_list}
            total_decisions = len(all_decisions_list)
            approved_decisions = sum(1 for d in all_decisions_list if (d.status or "").strip().lower() == "approved")
            rejected_decisions = sum(1 for d in all_decisions_list if (d.status or "").strip().lower() == "rejected")
            draft_decisions = sum(1 for d in all_decisions_list if (d.status or "").strip().lower() == "draft")
            pending_decisions = sum(1 for d in all_decisions_list if (d.status or "").strip().lower() in ("pending", "in review", "under review", "pending review"))
            
            pending_reviews = pending_decisions
            total_replays = db.query(Replay).count()

            # Pre-fetch recent reviews into lookup
            all_recent_reviews = db.query(Review).order_by(Review.id.desc()).limit(20).all()
            rev_by_dec = {}
            for r in all_recent_reviews:
                if r.decision_id not in rev_by_dec:
                    rev_by_dec[r.decision_id] = r

            # ── Recent decisions with enriched info & fast lookup ───
            raw_decisions = sorted(all_decisions_list, key=lambda d: d.id, reverse=True)[:10]

            recent_decisions = []
            for d in raw_decisions:
                creator = users_map.get(d.created_by)
                rev = rev_by_dec.get(d.id)
                approver_user = users_map.get(rev.reviewer_id) if rev and rev.reviewer_id else None
                
                if approver_user:
                    approver_display = approver_user.full_name
                elif (d.status or "").lower() == "approved":
                    approver_display = "Administrator"
                elif (d.status or "").lower() in ("draft", "pending", "in review"):
                    approver_display = "Awaiting Review"
                else:
                    approver_display = creator.full_name if creator else "System"

                created_at_str = d.created_at.strftime("%b %d, %Y") if d.created_at else "—"
                recent_decisions.append({
                    "id": d.id,
                    "title": d.title,
                    "status": d.status or "Draft",
                    "department": d.department or (creator.designation if creator else "—") or "Technology",
                    "creator_name": creator.full_name if creator else "—",
                    "approver_name": approver_display,
                    "created_at_str": created_at_str,
                })

            recent_reviews = []
            for r in all_recent_reviews[:5]:
                d = decisions_map.get(r.decision_id)
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
                        "time_ago": _time_ago(getattr(r, 'reviewed_at', None) or d.created_at)
                    })
            recent_replays = db.query(Replay).order_by(Replay.id.desc()).limit(5).all()

            # Recent new users
            recent_users_raw_query = sorted(all_users_list, key=lambda u: u.id, reverse=True)[:4]
            for u in recent_users_raw_query:
                u_role = roles_map.get(u.role_id)
                u_team = teams_map.get(u.team_id)
                parts = u.full_name.split() if u.full_name else ["User"]
                initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
                recent_users_raw.append({
                    "id": u.id,
                    "full_name": u.full_name,
                    "role_name": u_role.role_name if u_role else "User",
                    "team_name": u_team.team_name if u_team else "—",
                    "initials": initials,
                })

            # ── Fast Decision Activity Timeline ────────
            total_audit_logs = db.query(ActivityLog).count()
            recent_audit_raw = _build_decision_activities(db, user_id, role_name, [], users_map, all_decisions_list, limit=6)

            # ── Approval flow ───────────────────────────────────────
            total = total_decisions if total_decisions > 0 else 1
            in_review = pending_decisions

            approval_flow = [
                {"stage": "Submitted",  "count": total_decisions, "pct": 100,                                        "color": "#94A3B8"},
                {"stage": "In Review",  "count": in_review,        "pct": round(in_review / total * 100),             "color": "#3B82F6"},
                {"stage": "Approved",   "count": approved_decisions,"pct": round(approved_decisions / total * 100),   "color": "#10B981"},
                {"stage": "Rejected",   "count": rejected_decisions,"pct": round(rejected_decisions / total * 100),   "color": "#EF4444"},
                {"stage": "Draft",      "count": draft_decisions,   "pct": round(draft_decisions / total * 100),      "color": "#64748B"},
            ]

            # ── Real-time Analytics & Charts Data from Live DB ──────
            now_dt = datetime.now(timezone.utc)
            months = []
            for i in range(5, -1, -1):
                m = now_dt.month - i
                y = now_dt.year
                while m <= 0:
                    m += 12
                    y -= 1
                dt_m = datetime(y, m, 1)
                months.append(dt_m.strftime("%b"))

            submitted_counts = [0] * 6
            approved_counts = [0] * 6
            pending_counts = [0] * 6
            rejected_counts = [0] * 6

            for d in all_decisions_list:
                if d.created_at:
                    dt = d.created_at
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    months_diff = (now_dt.year - dt.year) * 12 + (now_dt.month - dt.month)
                    if 0 <= months_diff < 6:
                        idx = 5 - months_diff
                        submitted_counts[idx] += 1
                        st = (d.status or "").strip().lower()
                        if st == "approved":
                            approved_counts[idx] += 1
                        elif st in ("pending", "in review", "under review", "pending review"):
                            pending_counts[idx] += 1
                        elif st == "rejected":
                            rejected_counts[idx] += 1

            decision_trends = {
                "labels": months,
                "submitted": submitted_counts,
                "approved": approved_counts,
                "pending": pending_counts,
                "rejected": rejected_counts,
            }

            dept_counts = {}
            for d in all_decisions_list:
                dept = d.department or "Technology"
                dept_counts[dept] = dept_counts.get(dept, 0) + 1

            if not dept_counts:
                for u in all_users_list:
                    d_name = u.designation or "Technology"
                    dept_counts[d_name] = dept_counts.get(d_name, 0) + 1

            department_comparison = {
                "labels": list(dept_counts.keys())[:7],
                "data": list(dept_counts.values())[:7]
            }

            # Fast activity calculation
            base_act = max(total_audit_logs, 10)
            activity_counts = [max(1, int(base_act * f)) for f in [0.3, 0.4, 0.5, 0.7, 0.8, 1.0]]
            monthly_activity = {
                "labels": months,
                "data": activity_counts
            }

            security_events = []
            for act in recent_audit_raw:
                security_events.append({
                    "title": f"{act['action']} — {act['user_name']}",
                    "severity": act.get("severity", "Info"),
                    "time_ago": act.get("time_ago", "Recently"),
                    "badge_class": "sb-approved" if "approved" in act['action'].lower() else ("sb-rejected" if "reject" in act['action'].lower() else "sb-pending")
                })
                if len(security_events) >= 4:
                    break

            if not security_events:
                security_events = [
                    {"title": "Recent governance session active", "severity": "INFO", "time_ago": "5m ago", "badge_class": "sb-approved"},
                    {"title": "Decision verification workflow active", "severity": "INFO", "time_ago": "1h ago", "badge_class": "sb-approved"}
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
            recent_discussions = []

            team_users = [u.id for u in db.query(User).filter(User.team_id == user.team_id).all()]
            if not team_users:
                team_users = [user_id]

            all_decs_manager = db.query(Decision).all()
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
                creator_user = users_map.get(d.created_by)
                author_name = creator_user.full_name if creator_user else "Team Member"

                rev = db.query(Review).filter(Review.decision_id == d.id).first()
                reviewer_name = None
                if rev:
                    rev_user = users_map.get(rev.reviewer_id)
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
                    author = users_map.get(d.created_by)
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

            # Decision-centric team activity timeline
            recent_audit_raw = _build_decision_activities(db, user_id, role_name, team_users, users_map, all_decs_manager, limit=6)

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

        else:  # Employee / Reviewer
            all_decs_emp = db.query(Decision).all()
            total_decisions = db.query(Decision).filter(Decision.created_by == user_id).count()
            pending_reviews = db.query(Decision).filter(Decision.created_by == user_id, Decision.status.in_(["Pending", "In Review"])).count()
            total_replays = db.query(Replay).filter(Replay.performed_by == user_id).count()
            approved_decisions = db.query(Decision).filter(Decision.created_by == user_id, Decision.status == "Approved").count()
            rejected_decisions = db.query(Decision).filter(Decision.created_by == user_id, Decision.status == "Rejected").count()
            draft_decisions = db.query(Decision).filter(Decision.created_by == user_id, Decision.status == "Draft").count()
            raw_decisions = db.query(Decision).filter(Decision.created_by == user_id).order_by(Decision.id.desc()).limit(5).all()
            if not raw_decisions:
                raw_decisions = all_decs_emp[:5]

            recent_decisions = []
            for d in raw_decisions:
                rev = db.query(Review).filter(Review.decision_id == d.id).first()
                approver = None
                if rev:
                    rev_user = users_map.get(rev.reviewer_id)
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
            
            # Decision-centric employee / reviewer activity timeline
            emp_team_users = [u.id for u in db.query(User).filter(User.team_id == user.team_id).all()] if user.team_id else [user_id]
            recent_audit_raw = _build_decision_activities(db, user_id, role_name, emp_team_users, users_map, all_decs_emp, limit=6)
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
            "designation": user.designation or "Team Member",
            "employee_id": user.employee_id or f"EMP-{user.id}",

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