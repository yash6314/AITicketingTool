from sqlalchemy.orm import Session

from app.models.reply import Reply
from app.models.ticket import Ticket
from app.services.ai_service import generate_ticket_reply, rewrite_reply


def create_reply(
    db: Session,
    ticket: Ticket,
    draft_reply: str,
    reply_type: str = "acknowledgement",
) -> Reply:
    reply = Reply(
        ticket_id=ticket.id,
        reply_type=reply_type,
        draft_reply=draft_reply,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply


def create_generated_reply(
    db: Session,
    ticket: Ticket,
    reply_type: str,
    instruction: str | None = None,
) -> Reply:
    draft_reply = generate_ticket_reply(
        subject=ticket.title,
        description=ticket.description,
        reply_type=reply_type,
        instruction=instruction,
    )
    return create_reply(db, ticket, draft_reply, reply_type)


def get_reply(db: Session, reply_id: int) -> Reply | None:
    return db.query(Reply).filter(Reply.id == reply_id).first()


def latest_reply_text(reply: Reply) -> str:
    return reply.modified_reply or reply.draft_reply


def modify_reply_with_ai(db: Session, reply: Reply, instruction: str) -> Reply:
    reply.modified_reply = rewrite_reply(latest_reply_text(reply), instruction)
    reply.approved = False
    db.commit()
    db.refresh(reply)
    return reply


def edit_reply_manually(db: Session, reply: Reply, modified_reply: str) -> Reply:
    reply.modified_reply = modified_reply
    reply.approved = False
    db.commit()
    db.refresh(reply)
    return reply


def approve_reply(db: Session, reply: Reply) -> Reply:
    reply.approved = True
    db.commit()
    db.refresh(reply)
    return reply


def reject_reply(db: Session, reply: Reply) -> Reply:
    if reply.sent:
        raise ValueError("Sent replies cannot be rejected")
    reply.approved = False
    db.delete(reply)
    db.commit()
    return reply


def mark_sent(db: Session, reply: Reply) -> Reply:
    if not reply.approved:
        raise ValueError("Reply must be approved before sending")
    reply.sent = True
    db.commit()
    db.refresh(reply)
    return reply
