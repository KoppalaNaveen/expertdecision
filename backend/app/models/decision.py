from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(200), nullable=False)

    description = Column(Text, nullable=False)
    
    priority_level = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True)
    decision_date = Column(DateTime(timezone=True), nullable=True)
    tags = Column(String(200), nullable=True)
    
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="decisions")

    status = Column(
        String(50),
        default="Pending"
    )

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    creator = relationship("User", foreign_keys=[created_by])
    alternatives = relationship("Alternative", back_populates="decision", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="decision", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="decision", cascade="all, delete-orphan")
    threads = relationship("DiscussionThread", back_populates="decision", cascade="all, delete-orphan")
    meeting_notes = relationship("MeetingNote", back_populates="decision", cascade="all, delete-orphan")
    versions = relationship("DecisionVersion", backref="decision", cascade="all, delete-orphan", order_by="desc(DecisionVersion.version_number)")

    content_hash = Column(String(64), nullable=True)

    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_user = relationship("User", foreign_keys=[approved_by_id])
    approved_at = Column(DateTime(timezone=True), nullable=True)

    rationale_why = Column(Text, nullable=True)
    rationale_justification = Column(Text, nullable=True)
    rationale_benefits = Column(Text, nullable=True)
    rationale_risks = Column(Text, nullable=True)
    rationale_assumptions = Column(Text, nullable=True)
    rationale_updated_at = Column(DateTime(timezone=True), nullable=True)
    rationale_updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rationale_updater = relationship("User", foreign_keys=[rationale_updated_by])

    @property
    def creator_name(self):
        return self.creator.full_name if self.creator else None

    @property
    def creator_initials(self):
        if not self.creator or not self.creator.full_name:
            return "U"
        parts = self.creator.full_name.split()
        return "".join([p[0].upper() for p in parts])[:2]

    @property
    def category_name(self):
        return self.category.name if self.category else None

    def _resolve_approver(self):
        # 1. Direct approved_by_user relationship
        try:
            if self.approved_by_user:
                r_name = getattr(self.approved_by_user.role, 'role_name', '') if getattr(self.approved_by_user, 'role', None) else ''
                if 'admin' in r_name.lower() or getattr(self.approved_by_user, 'role_id', None) == 1 or (self.approved_by_user.employee_id and self.approved_by_user.employee_id.startswith('AD')):
                    return self.approved_by_user
        except Exception:
            pass

        # 2. Check reviews for an Administrator who approved this decision
        try:
            if self.reviews:
                for rev in self.reviews:
                    if rev.status in ["Approved", "Accepted"] and rev.reviewer:
                        u = rev.reviewer
                        r_name = getattr(u.role, 'role_name', '') if getattr(u, 'role', None) else ''
                        if 'admin' in r_name.lower() or getattr(u, 'role_id', None) == 1 or (u.employee_id and u.employee_id.startswith('AD')):
                            return u
        except Exception:
            pass

        # 3. Check version snapshots for an Administrator who recorded the Approved status
        if self.status == "Approved" and self.versions:
            for v in self.versions:
                if v.status == "Approved":
                    try:
                        u = getattr(v, 'changed_by_user', None)
                        if u:
                            r_name = getattr(u.role, 'role_name', '') if getattr(u, 'role', None) else ''
                            if 'admin' in r_name.lower() or getattr(u, 'role_id', None) == 1 or (u.employee_id and u.employee_id.startswith('AD')):
                                return u
                    except Exception:
                        pass

        return None

    @property
    def approved_by_name(self):
        try:
            u = self._resolve_approver()
            if u and u.full_name:
                return u.full_name
        except Exception:
            pass
        return None

    @property
    def approved_by_employee_id(self):
        try:
            u = self._resolve_approver()
            if u and u.employee_id:
                return u.employee_id
        except Exception:
            pass
        return None

    @property
    def approved_by_role(self):
        try:
            u = self._resolve_approver()
            if u:
                return u.role.role_name if getattr(u, 'role', None) else "Administrator"
        except Exception:
            pass
        return None

    @property
    def approved_at_str(self):
        try:
            if self.approved_at:
                return self.approved_at.strftime("%b %d, %Y")
            if self.status == "Approved" and self.versions:
                for v in self.versions:
                    if v.status == "Approved" and v.created_at:
                        return v.created_at.strftime("%b %d, %Y")
        except Exception:
            pass
        return "Approved" if self.status == "Approved" else None