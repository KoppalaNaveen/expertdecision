from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database.base import Base

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    decisions = relationship("Decision", back_populates="category")
