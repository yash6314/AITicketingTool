from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from datetime import datetime
from app.db.database import Base
from sqlalchemy.orm import relationship

class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True)
    conversation_id = Column(String)
    sender_email = Column(String)
    subject = Column(String)
    body = Column(Text)
    received_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    ai_decision = Column(String, default="ticket")
    review_status = Column(String, nullable=True)

    # 🔗 relationship
    tickets = relationship("Ticket", back_populates="email")
