import json
import urllib.error
import urllib.request

from app.core.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_MODEL,
    OPENROUTER_SITE_URL,
)
from app.schemas.ticket_schema import AIAnalysis


class AIServiceError(Exception):
    pass


def _extract_json(content: str) -> dict:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI response did not contain JSON")
    return json.loads(content[start : end + 1])


def _openrouter_error_message(exc: Exception, context: str) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        body = exc.read().decode("utf-8", errors="replace")
        return f"{context}: OpenRouter returned HTTP {exc.code} {exc.reason}. {body[:500]}"
    return f"{context}: {exc}"


def analyze_email(subject: str, body: str, sender_email: str) -> AIAnalysis:
    if not OPENROUTER_API_KEY:
        raise AIServiceError("OPENROUTER_API_KEY is missing")

    prompt = f"""
Analyze this support email and return only valid JSON with these keys:
create_ticket boolean, decision string, category string, priority string, summary string, draft_reply string, reason string.

Decision rules:
- decision must be one of: ticket, ignore, review.
- use ticket when the email clearly contains a task, request, issue, complaint, or action needed.
- use ignore when the email is clearly informational, newsletter-like, spam, or needs no action.
- use review when it is unclear whether the email should become a ticket.
- create_ticket must be true only when decision is ticket.
- draft_reply must be polite, context-aware, and specific to the sender's actual issue.
- Do not use generic placeholder replies.
- Mention the user's issue/request naturally without inventing facts or promising resolution.

Sender: {sender_email}
Subject: {subject}
Body: {body}
"""
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You classify emails for a ticket system."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_APP_NAME,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        analysis = AIAnalysis(**_extract_json(content))
        if analysis.decision not in {"ticket", "ignore", "review"}:
            analysis.decision = "review"
        analysis.create_ticket = analysis.decision == "ticket"
        return analysis
    except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise AIServiceError(_openrouter_error_message(exc, "OpenRouter email analysis failed")) from exc


def rewrite_reply(current_reply: str, instruction: str) -> str:
    if not OPENROUTER_API_KEY:
        raise AIServiceError("OPENROUTER_API_KEY is missing")

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Rewrite support email replies. Return only the rewritten reply text.",
            },
            {
                "role": "user",
                "content": f"Instruction: {instruction}\n\nReply:\n{current_reply}",
            },
        ],
        "temperature": 0.3,
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_APP_NAME,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise AIServiceError(_openrouter_error_message(exc, "OpenRouter reply rewrite failed")) from exc


def generate_ticket_reply(
    subject: str,
    description: str,
    reply_type: str,
    instruction: str | None = None,
) -> str:
    if not OPENROUTER_API_KEY:
        raise AIServiceError("OPENROUTER_API_KEY is missing")

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Generate support ticket replies. Return only the reply text. "
                    "Follow the admin instruction closely. Do not invent facts. "
                    "Keep it polite, specific, and suitable to send to the email sender."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Reply type: {reply_type}\n"
                    f"Instruction: {instruction or 'No extra instruction'}\n"
                    f"Ticket title: {subject}\n"
                    f"Ticket description: {description}"
                ),
            },
        ],
        "temperature": 0.3,
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_APP_NAME,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise AIServiceError(_openrouter_error_message(exc, "OpenRouter ticket reply generation failed")) from exc
