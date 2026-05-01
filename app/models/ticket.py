from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from app.db.database import Base
from sqlalchemy.orm import relationship

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"))
    conversation_id = Column(String, index=True)

    title = Column(String)
    description = Column(Text)

    category = Column(String)
    priority = Column(String)
    status = Column(String, default="open")

    created_at = Column(DateTime, default=datetime.utcnow)

    # 🔗 relationships
    email = relationship("Email", back_populates="tickets")
    replies = relationship("Reply", back_populates="ticket")
