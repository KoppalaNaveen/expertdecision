from pydantic import BaseModel
from typing import List, Optional


class RecentDecision(BaseModel):
    id: int
    title: str
    status: str
    department: Optional[str] = None
    approver_name: Optional[str] = None
    created_at_str: Optional[str] = None
    priority: Optional[str] = "Medium"

    class Config:
        from_attributes = True


class RecentReview(BaseModel):
    id: int
    decision_id: int
    decision_title: Optional[str] = None
    status: str
    comments: str | None = None
    time_ago: Optional[str] = None
    task_type: Optional[str] = None
    is_owner: Optional[bool] = None

    class Config:
        from_attributes = True


class RecentReplay(BaseModel):
    id: int
    decision_id: int
    action: str

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
    severity: Optional[str] = "Info"

    class Config:
        from_attributes = True


class ApprovalFlowStat(BaseModel):
    stage: str
    count: int
    pct: int
    color: str

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    user: str
    role: str
    team: str

    # Core stats
    total_decisions: int
    pending_reviews: int
    total_replays: int
    unread_notifications_count: Optional[int] = 0

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