from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.reply import Reply
from app.schemas.ticket_schema import ReplyEditRequest, ReplyModifyRequest, ReplyRejectRequest
from app.services.ai_service import AIServiceError
from app.services.reply_service import (
    approve_reply,
    edit_reply_manually,
    get_reply,
    latest_reply_text,
    mark_sent,
    modify_reply_with_ai,
    reject_reply,
)

router = APIRouter(prefix="/replies", tags=["replies"])


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
        "ticket": {
            "id": reply.ticket.id,
            "title": reply.ticket.title,
            "category": reply.ticket.category,
            "priority": reply.ticket.priority,
            "status": reply.ticket.status,
        } if reply.ticket else None,
    }


def _reply_or_404(db: Session, reply_id: int):
    reply = get_reply(db, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    return reply


@router.get("/pending")
def pending_approvals(db: Session = Depends(get_db)):
    replies = (
        db.query(Reply)
        .filter(Reply.approved == False, Reply.sent == False)
        .order_by(Reply.created_at.desc())
        .limit(100)
        .all()
    )
    return [_reply_to_dict(reply) for reply in replies]


@router.post("/{reply_id}/modify-ai")
def modify_reply(reply_id: int, payload: ReplyModifyRequest, db: Session = Depends(get_db)):
    reply = _reply_or_404(db, reply_id)
    try:
        updated_reply = modify_reply_with_ai(db, reply, payload.instruction)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "message": "Reply modified with AI",
        "reply_id": updated_reply.id,
        "final_reply": latest_reply_text(updated_reply),
        "approved": updated_reply.approved,
    }


@router.put("/{reply_id}/edit")
def edit_reply(reply_id: int, payload: ReplyEditRequest, db: Session = Depends(get_db)):
    reply = _reply_or_404(db, reply_id)
    updated_reply = edit_reply_manually(db, reply, payload.modified_reply)
    return {
        "message": "Reply edited",
        "reply_id": updated_reply.id,
        "final_reply": latest_reply_text(updated_reply),
        "approved": updated_reply.approved,
    }


@router.post("/{reply_id}/approve")
def approve(reply_id: int, db: Session = Depends(get_db)):
    reply = _reply_or_404(db, reply_id)
    approved_reply = approve_reply(db, reply)
    return {
        "message": "Reply approved",
        "reply_id": approved_reply.id,
        "final_reply": latest_reply_text(approved_reply),
        "approved": approved_reply.approved,
    }


@router.post("/{reply_id}/reject")
def reject(reply_id: int, payload: ReplyRejectRequest | None = None, db: Session = Depends(get_db)):
    reply = _reply_or_404(db, reply_id)
    try:
        reject_reply(db, reply)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "message": "Reply rejected and draft cleared",
        "reply_id": reply_id,
        "reason": payload.reason if payload else None,
    }


@router.post("/{reply_id}/send")
def send(reply_id: int, db: Session = Depends(get_db)):
    reply = _reply_or_404(db, reply_id)
    try:
        sent_reply = mark_sent(db, reply)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "message": "Reply marked as sent. Outlook sending integration is pending.",
        "reply_id": sent_reply.id,
        "sent": sent_reply.sent,
        "final_reply": latest_reply_text(sent_reply),
    }
