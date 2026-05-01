from sqlalchemy.orm import Session

from app.models.email import Email
from app.models.ticket import Ticket
from app.schemas.ticket_schema import AIAnalysis


def get_ticket_by_conversation(db: Session, conversation_id: str) -> Ticket | None:
    return (
        db.query(Ticket)
        .filter(Ticket.conversation_id == conversation_id)
        .order_by(Ticket.created_at.desc())
        .first()
    )


def create_ticket_from_email(db: Session, email: Email, analysis: AIAnalysis) -> Ticket:
    ticket = Ticket(
        email_id=email.id,
        conversation_id=email.conversation_id,
        title=analysis.summary or email.subject,
        description=email.body,
        category=analysis.category or "General",
        priority=analysis.priority or "Medium",
        status="open",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket
