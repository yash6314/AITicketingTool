from pydantic import BaseModel, Field


class EmailCreate(BaseModel):
    message_id: str
    conversation_id: str
    sender_email: str
    subject: str
    body: str


class EmailIngestResponse(BaseModel):
    message: str
    email_id: int | None = None
    ticket_id: int | None = None
    reply_id: int | None = None
    duplicate: bool = False
    create_ticket: bool | None = None
    decision: str | None = None


class AIAnalysis(BaseModel):
    create_ticket: bool
    decision: str = "ticket"
    category: str = ""
    priority: str = "Medium"
    summary: str = ""
    draft_reply: str = ""
    reason: str = ""


class ReplyModifyRequest(BaseModel):
    instruction: str = Field(..., examples=["Make it more polite"])


class TicketReplyCreateRequest(BaseModel):
    reply_type: str = Field(
        default="update",
        examples=["acknowledgement", "update", "completion", "custom"],
    )
    instruction: str | None = Field(
        default=None,
        examples=["Tell the user the ID card issue has been resolved."],
    )


class TicketStatusUpdateRequest(BaseModel):
    status: str = Field(..., examples=["open", "in_progress", "completed"])


class ReplyEditRequest(BaseModel):
    modified_reply: str


class ReplyRejectRequest(BaseModel):
    reason: str | None = None


class TicketCreateResponse(BaseModel):
    message: str
    ticket_id: int | None = None
