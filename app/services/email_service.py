from sqlalchemy.orm import Session

from app.models.email import Email
from app.schemas.ticket_schema import AIAnalysis, EmailCreate


def get_email_by_message_id(db: Session, message_id: str) -> Email | None:
    return db.query(Email).filter(Email.message_id == message_id).first()


def create_email(
    db: Session,
    payload: EmailCreate,
    analysis: AIAnalysis | None = None,
    review_status: str | None = None,
) -> Email:
    email = Email(
        message_id=payload.message_id,
        conversation_id=payload.conversation_id,
        sender_email=payload.sender_email,
        subject=payload.subject,
        body=payload.body,
        ai_decision=analysis.decision if analysis else None,
        review_status=review_status,
    )
    db.add(email)
    db.commit()
    db.refresh(email)
    return email


def list_review_emails(db: Session) -> list[Email]:
    return (
        db.query(Email)
        .filter(Email.ai_decision == "review", Email.review_status == "pending")
        .order_by(Email.received_at.desc())
        .limit(100)
        .all()
    )


def approve_review_email(db: Session, email: Email) -> Email:
    email.review_status = "approved"
    db.commit()
    db.refresh(email)
    return email


def reject_review_email(db: Session, email: Email) -> Email:
    email.review_status = "rejected"
    email.processed = True
    db.commit()
    db.refresh(email)
    return email


def mark_processed(db: Session, email: Email) -> Email:
    email.processed = True
    db.commit()
    db.refresh(email)
    return email
