from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime
from app.db.database import Base
from sqlalchemy.orm import relationship

class Reply(Base):
    __tablename__ = "replies"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))

    reply_type = Column(String, default="acknowledgement")
    draft_reply = Column(Text)
    modified_reply = Column(Text, nullable=True)

    approved = Column(Boolean, default=False)
    sent = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 🔗 relationship
    ticket = relationship("Ticket", back_populates="replies")
