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