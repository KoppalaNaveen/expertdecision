from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.base import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)

    team_name = Column(
        String(100),
        unique=True,
        nullable=False
    )

    description = Column(
        String(255),
        nullable=True
    )
    
    users = relationship("User", back_populates="team")