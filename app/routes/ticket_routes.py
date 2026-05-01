from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.ticket import Ticket
from app.models.email import Email
from app.models.reply import Reply
from app.schemas.ticket_schema import TicketReplyCreateRequest, TicketStatusUpdateRequest
from app.services.ai_service import AIServiceError, analyze_email
from app.services.reply_service import create_generated_reply, latest_reply_text
from app.services.ticket_service import create_ticket_from_email

router = APIRouter()


def _reply_to_dict(reply: Reply):
    return {
        "id": reply.id,
        "ticket_id": reply.ticket_id,
        "reply_type": reply.reply_type,
        "draft_reply": reply.draft_reply,
        "modified_reply": reply.modified_reply,
        "final_reply": latest_reply_text(reply),
        "approved": reply.approved,
        "sent": reply.sent,
        "created_at": reply.created_at.isoformat() if reply.created_at else None,
    }


def _ticket_to_dict(ticket: Ticket, include_details: bool = False):
    data = {
        "id": ticket.id,
        "email_id": ticket.email_id,
        "conversation_id": ticket.conversation_id,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "reply_count": len(ticket.replies),
    }
    if include_details:
        data["email"] = {
            "id": ticket.email.id,
            "sender_email": ticket.email.sender_email,
            "subject": ticket.email.subject,
            "body": ticket.email.body,
            "message_id": ticket.email.message_id,
            "conversation_id": ticket.email.conversation_id,
        } if ticket.email else None
        data["replies"] = [_reply_to_dict(reply) for reply in ticket.replies]
    return data


@router.get("/tickets")
def list_tickets(db: Session = Depends(get_db)):
    tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(100).all()
    return [_ticket_to_dict(ticket) for ticket in tickets]


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_to_dict(ticket, include_details=True)


@router.patch("/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    allowed_statuses = {"open", "in_progress", "completed"}
    if payload.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="status must be open, in_progress, or completed",
        )

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = payload.status
    db.commit()
    db.refresh(ticket)
    return {
        "message": "Ticket status updated",
        "ticket_id": ticket.id,
        "status": ticket.status,
    }

@router.post("/create-ticket")
def create_ticket(db: Session = Depends(get_db)):

    email = db.query(Email).first()

    if not email:
        return {"error": "No email found"}

    try:
        analysis = analyze_email(email.subject, email.body, email.sender_email)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    analysis.decision = "ticket"
    analysis.create_ticket = True
    ticket = create_ticket_from_email(db, email, analysis)

    return {"message": "Ticket created", "ticket_id": ticket.id}


@router.post("/tickets/{ticket_id}/replies")
def create_ticket_reply(
    ticket_id: int,
    payload: TicketReplyCreateRequest,
    db: Session = Depends(get_db),
):
    allowed_types = {"acknowledgement", "update", "completion", "custom"}
    if payload.reply_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="reply_type must be acknowledgement, update, completion, or custom",
        )

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    try:
        reply = create_generated_reply(
            db=db,
            ticket=ticket,
            reply_type=payload.reply_type,
            instruction=payload.instruction,
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "message": f"{payload.reply_type} reply draft created",
        "ticket_id": ticket.id,
        "reply_id": reply.id,
        "reply_type": reply.reply_type,
        "final_reply": latest_reply_text(reply),
        "approved": reply.approved,
        "sent": reply.sent,
    }
