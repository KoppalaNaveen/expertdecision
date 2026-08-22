from pydantic import BaseModel
from typing import List, Optional, Any


class RecentDecision(BaseModel):
    id: int
    title: str
    status: str
    department: Optional[str] = None
    approver_name: Optional[str] = None
    creator_name: Optional[str] = None
    requester_name: Optional[str] = None
    reviewer_name: Optional[str] = None
    category_name: Optional[str] = None
    created_at_str: Optional[str] = None
    updated_at_str: Optional[str] = None
    time_ago: Optional[str] = None
    priority: Optional[str] = "Medium"

    class Config:
        from_attributes = True


class RecentReview(BaseModel):
    id: int
    decision_id: int
    decision_title: Optional[str] = None
    status: str
    comments: Optional[str] = None
    time_ago: Optional[str] = None
    task_type: Optional[str] = None
    is_owner: Optional[bool] = None
    author_name: Optional[str] = None
    author_initials: Optional[str] = None
    department: Optional[str] = None
    priority: Optional[str] = None

    class Config:
        from_attributes = True


class RecentReplay(BaseModel):
    id: int
    decision_id: int
    action: Optional[str] = None

    class Config:
        from_attributes = True


class RecentUser(BaseModel):
    id: int
    full_name: str
    role_name: Optional[str] = None
    team_name: Optional[str] = None
    initials: Optional[str] = None

    class Config:
        from_attributes = True


class AuditLogEntry(BaseModel):
    user_name: Optional[str] = None
    action: str
    module: Optional[str] = None
    time_ago: Optional[str] = None
    created_at_str: Optional[str] = None
    severity: Optional[str] = "Info"
    icon: Optional[str] = "activity"
    icon_color: Optional[str] = "#2563EB"
    bg_color: Optional[str] = "#EFF6FF"

    class Config:
        from_attributes = True


class ApprovalFlowStat(BaseModel):
    stage: Optional[str] = "General"
    label: Optional[str] = None
    count: Optional[int] = 0
    pct: Optional[int] = 0
    percentage: Optional[int] = 0
    color: Optional[str] = "#3B82F6"

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    user: str
    role: str
    team: str
    designation: Optional[str] = "Team Member"
    employee_id: Optional[str] = None

    # Core stats
    total_decisions: int
    pending_reviews: int
    total_replays: int
    unread_notifications_count: Optional[int] = 0
    recent_notifications: Optional[List[dict]] = []

    # Admin-specific stats
    total_users: Optional[int] = 0
    active_users: Optional[int] = 0
    total_audit_logs: Optional[int] = 0
    approved_decisions: Optional[int] = 0
    rejected_decisions: Optional[int] = 0
    draft_decisions: Optional[int] = 0
    system_health: Optional[str] = "99%"

    # Recent items
    recent_decisions: List[RecentDecision] = []
    recent_reviews: List[RecentReview] = []
    recent_replays: List[RecentReplay] = []
    recent_discussions: Optional[List[dict]] = []

    # Admin extras
    recent_users: Optional[List[RecentUser]] = []
    recent_audit_logs: Optional[List[AuditLogEntry]] = []
    approval_flow: Optional[List[ApprovalFlowStat]] = []

    # Real-time analytics & chart data
    decision_trends: Optional[dict] = None
    department_comparison: Optional[dict] = None
    monthly_activity: Optional[dict] = None
    security_events: Optional[List[dict]] = []
    admin_tasks: Optional[List[dict]] = []

    class Config:
        from_attributes = True