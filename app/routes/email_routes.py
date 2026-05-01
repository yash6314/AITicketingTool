from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.email import Email
from app.schemas.ticket_schema import EmailCreate
from app.services.ai_service import AIServiceError, analyze_email
from app.services.email_service import (
    approve_review_email,
    create_email,
    get_email_by_message_id,
    list_review_emails,
    mark_processed,
    reject_review_email,
)
from app.services.reply_service import create_reply
from app.services.ticket_service import create_ticket_from_email, get_ticket_by_conversation

router = APIRouter()


def _email_to_dict(email: Email):
    return {
        "id": email.id,
        "message_id": email.message_id,
        "conversation_id": email.conversation_id,
        "sender_email": email.sender_email,
        "subject": email.subject,
        "body": email.body,
        "received_at": email.received_at.isoformat() if email.received_at else None,
        "processed": email.processed,
        "ai_decision": email.ai_decision,
        "review_status": email.review_status,
    }


@router.get("/emails")
def list_emails(db: Session = Depends(get_db)):
    emails = db.query(Email).order_by(Email.received_at.desc()).limit(100).all()
    return [_email_to_dict(email) for email in emails]


@router.get("/emails/review")
def review_queue(db: Session = Depends(get_db)):
    return [_email_to_dict(email) for email in list_review_emails(db)]


@router.post("/emails/ingest")
def ingest_email(payload: EmailCreate, db: Session = Depends(get_db)):
    existing_email = get_email_by_message_id(db, payload.message_id)
    if existing_email:
        return {
            "message": "Duplicate email ignored",
            "email_id": existing_email.id,
            "duplicate": True,
        }

    try:
        analysis = analyze_email(payload.subject, payload.body, payload.sender_email)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if analysis.decision == "ignore":
        return {
            "message": "Email ignored by AI decision",
            "duplicate": False,
            "create_ticket": False,
            "decision": "ignore",
        }

    email = create_email(
        db,
        payload,
        analysis=analysis,
        review_status="pending" if analysis.decision == "review" else None,
    )

    if analysis.decision == "review":
        return {
            "message": "Email stored for admin review",
            "email_id": email.id,
            "duplicate": False,
            "create_ticket": False,
            "decision": "review",
        }

    existing_ticket = get_ticket_by_conversation(db, email.conversation_id)

    if existing_ticket:
        reply = create_reply(db, existing_ticket, analysis.draft_reply)
        mark_processed(db, email)
        return {
            "message": "Email attached to existing conversation ticket",
            "email_id": email.id,
            "ticket_id": existing_ticket.id,
            "reply_id": reply.id,
            "duplicate": False,
            "create_ticket": True,
            "decision": "ticket",
        }

    ticket = create_ticket_from_email(db, email, analysis)
    reply = create_reply(db, ticket, analysis.draft_reply)
    mark_processed(db, email)
    return {
        "message": "Email stored, ticket created, draft reply generated",
        "email_id": email.id,
        "ticket_id": ticket.id,
        "reply_id": reply.id,
        "duplicate": False,
        "create_ticket": True,
        "decision": "ticket",
    }


@router.post("/emails/{email_id}/approve-ticket")
def approve_email_as_ticket(email_id: int, db: Session = Depends(get_db)):
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    if email.review_status != "pending":
        raise HTTPException(status_code=400, detail="Email is not pending review")

    try:
        analysis = analyze_email(email.subject, email.body, email.sender_email)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    analysis.decision = "ticket"
    analysis.create_ticket = True

    existing_ticket = get_ticket_by_conversation(db, email.conversation_id)
    ticket = existing_ticket or create_ticket_from_email(db, email, analysis)
    reply = create_reply(db, ticket, analysis.draft_reply)
    approve_review_email(db, email)
    mark_processed(db, email)

    return {
        "message": "Review email approved as ticket",
        "email_id": email.id,
        "ticket_id": ticket.id,
        "reply_id": reply.id,
    }


@router.post("/emails/{email_id}/reject")
def reject_review(email_id: int, db: Session = Depends(get_db)):
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    if email.review_status != "pending":
        raise HTTPException(status_code=400, detail="Email is not pending review")
    reject_review_email(db, email)
    return {"message": "Review email rejected", "email_id": email.id}


@router.post("/add-email")
def add_email(db: Session = Depends(get_db)):
    new_email = Email(
        message_id="test_001",
        conversation_id="conv_001",
        sender_email="user@test.com",
        subject="Test Issue",
        body="My ID card is not working"
    )

    db.add(new_email)
    db.commit()
    db.refresh(new_email)

    return {"message": "Email inserted", "id": new_email.id}
