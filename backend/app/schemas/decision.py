from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DecisionCreate(BaseModel):
    title: str
    description: str
    created_by: int
    category_id: Optional[int] = None
    priority_level: Optional[str] = None
    department: Optional[str] = None
    decision_date: Optional[datetime] = None
    tags: Optional[str] = None

class DecisionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    change_reason: Optional[str] = None

class DecisionStatusUpdate(BaseModel):
    status: str

class DecisionResponse(BaseModel):
    id: int
    title: str
    description: str
    status: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    created_by: int
    creator_name: Optional[str] = None
    creator_initials: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class AlternativeCreateForDecision(BaseModel):
    title: str
    description: Optional[str] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    cost: Optional[float] = None
    feasibility_score: Optional[int] = None
    risk_level: Optional[str] = None

class ReviewerCreateForDecision(BaseModel):
    reviewer_id: int
    deadline: Optional[datetime] = None
    approval_type: Optional[str] = None

class DecisionFullCreate(BaseModel):
    title: str
    description: str
    created_by: int
    category_id: Optional[int] = None
    priority_level: Optional[str] = None
    department: Optional[str] = None
    decision_date: Optional[datetime] = None
    tags: Optional[str] = None
    status: Optional[str] = "Pending"
    alternatives: List[AlternativeCreateForDecision] = []
    reviewers: List[ReviewerCreateForDecision] = []
    temp_file_ids: List[int] = []
    change_reason: Optional[str] = None

class DecisionVersionResponse(BaseModel):
    id: int
    decision_id: int
    version_number: int
    title: str
    description: str
    category_id: Optional[int] = None
    status: str
    priority_level: Optional[str] = None
    department: Optional[str] = None
    decision_date: Optional[datetime] = None
    tags: Optional[str] = None
    changed_by: Optional[int] = None
    change_reason: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class AttachmentResponse(BaseModel):
    id: int
    filename: str
    file_size: int
    uploaded_at: datetime
    uploaded_by: int

    model_config = {
        "from_attributes": True
    }

class CommentCreate(BaseModel):
    content: str
    user_id: int
    reply_to_id: Optional[int] = None

class CommentResponse(BaseModel):
    id: int
    content: str
    user_id: int
    reply_to_id: Optional[int] = None
    is_edited: Optional[bool] = False
    is_deleted: Optional[bool] = False
    is_pinned: Optional[bool] = False
    reactions: Optional[str] = None
    read_receipts: Optional[str] = None
    edit_history: Optional[str] = None
    created_at: datetime
    author_name: Optional[str] = None
    author_role: Optional[str] = None

    model_config = {
        "from_attributes": True
    }

class DiscussionThreadCreate(BaseModel):
    topic: str
    created_by: int

class DiscussionThreadResponse(BaseModel):
    id: int
    topic: str
    status: str
    is_pinned: Optional[bool] = False
    created_by: int
    created_at: datetime
    comments: List[CommentResponse] = []

    model_config = {
        "from_attributes": True
    }

class MeetingNoteCreate(BaseModel):
    title: str
    notes: str
    meeting_date: Optional[datetime] = None
    participants: Optional[str] = None
    agenda: Optional[str] = None
    action_items: Optional[str] = None
    next_meeting_date: Optional[datetime] = None
    meeting_link: Optional[str] = None
    created_by: int

class MeetingNoteResponse(BaseModel):
    id: int
    title: str
    notes: str
    meeting_date: Optional[datetime] = None
    participants: Optional[str] = None
    agenda: Optional[str] = None
    action_items: Optional[str] = None
    next_meeting_date: Optional[datetime] = None
    meeting_link: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    author_name: Optional[str] = None
    status: Optional[str] = None

    model_config = {
        "from_attributes": True
    }

class DecisionRationaleResponse(BaseModel):
    decision_id: int
    why_required: Optional[str] = None
    business_justification: Optional[str] = None
    expected_benefits: Optional[str] = None
    risks: Optional[str] = None
    assumptions: Optional[str] = None
    created_by: int
    created_at: Optional[datetime] = None
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    updater_name: Optional[str] = None

class DecisionRationaleUpdate(BaseModel):
    why_required: Optional[str] = None
    business_justification: Optional[str] = None
    expected_benefits: Optional[str] = None
    risks: Optional[str] = None
    assumptions: Optional[str] = None
    user_id: int

from app.schemas.review import ReviewResponse

class DecisionFullResponse(DecisionResponse):
    alternatives: List[BaseModel] = []
    reviews: List[ReviewResponse] = []
    attachments: List[AttachmentResponse] = []
    threads: List[DiscussionThreadResponse] = []
    meeting_notes: List[MeetingNoteResponse] = []
    versions: List[DecisionVersionResponse] = []
