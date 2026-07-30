from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)

    decision_id = Column(
        Integer,
        ForeignKey("decisions.id"),
        nullable=False
    )

    reviewer_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    status = Column(
        String(50),
        nullable=False
    )

    comments = Column(Text)
    deadline = Column(DateTime(timezone=True), nullable=True)
    approval_type = Column(String(50), nullable=True)

    reviewed_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    decision = relationship("Decision")
    reviewer = relationship("User")

    @property
    def reviewer_name(self):
        return self.reviewer.full_name if self.reviewer else None

    @property
    def reviewer_role(self):
        if not self.reviewer:
            return None
        return self.reviewer.role.name if getattr(self.reviewer, 'role', None) else getattr(self.reviewer, 'role_name', None)

    @property
    def employee_id(self):
        return self.reviewer.employee_id if self.reviewer else None

    @property
    def reviewer_initials(self):
        if not self.reviewer or not self.reviewer.full_name:
            return "U"
        parts = self.reviewer.full_name.split()
        return "".join([p[0].upper() for p in parts])[:2]