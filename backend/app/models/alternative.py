from sqlalchemy import Column, Integer, String, Text, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.database.base import Base

class Alternative(Base):
    __tablename__ = "alternatives"

    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=False)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    pros = Column(Text, nullable=True)
    cons = Column(Text, nullable=True)
    
    cost = Column(Numeric(10, 2), nullable=True)
    feasibility_score = Column(Integer, nullable=True)
    risk_level = Column(String(50), nullable=True)
    
    decision = relationship("Decision", back_populates="alternatives")
    
    content_hash = Column(String(64), nullable=True)
