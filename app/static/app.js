const state = {
  view: "tickets",
  tickets: [],
  emails: [],
  approvals: [],
  selectedTicketId: null,
};

const titles = {
  tickets: ["Tickets", "Review tickets, drafts, approvals, and send states."],
  approvals: ["Pending Approvals", "Approve or refine reply drafts before sending."],
  emails: ["Review Queue", "Unclear emails that need an admin ticket decision."],
  ingest: ["Manual Email Test", "Push a sample email through the workflow before Outlook is connected."],
};

const el = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "No date";
  return new Date(value).toLocaleString();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.message || "Request failed");
  }
  return data;
}

function showNotice(message, isError = false) {
  const box = el("notice");
  box.textContent = message;
  box.className = `notice${isError ? " error" : ""}`;
  window.setTimeout(() => box.classList.add("hidden"), 4500);
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("active", section.id === `${view}View`);
  });
  el("pageTitle").textContent = titles[view][0];
  el("pageSubtitle").textContent = titles[view][1];
  refreshCurrentView();
}

async function refreshCurrentView() {
  try {
    if (state.view === "tickets") await loadTickets();
    if (state.view === "approvals") await loadApprovals();
    if (state.view === "emails") await loadEmails();
  } catch (error) {
    showNotice(error.message, true);
  }
}

async function loadTickets() {
  state.tickets = await api("/tickets");
  renderTickets();
  if (state.selectedTicketId) {
    await selectTicket(state.selectedTicketId, false);
  }
}

function renderTickets() {
  renderStats();
  const status = el("statusFilter").value;
  const tickets = state.tickets.filter((ticket) => !status || ticket.status === status);
  el("ticketList").innerHTML = tickets.length
    ? tickets.map(ticketItem).join("")
    : `<div class="item muted">No tickets found.</div>`;

  document.querySelectorAll("[data-ticket-id]").forEach((node) => {
    node.addEventListener("click", () => selectTicket(Number(node.dataset.ticketId)));
  });
}

function renderStats() {
  const counts = state.tickets.reduce((acc, ticket) => {
    acc.total += 1;
    acc[ticket.status] = (acc[ticket.status] || 0) + 1;
    return acc;
  }, { total: 0, open: 0, in_progress: 0, completed: 0 });

  el("statsGrid").innerHTML = `
    <button class="stat-card" data-stat-filter="">
      <span>Total</span>
      <strong>${counts.total}</strong>
    </button>
    <button class="stat-card" data-stat-filter="open">
      <span>Open</span>
      <strong>${counts.open}</strong>
    </button>
    <button class="stat-card" data-stat-filter="in_progress">
      <span>In Progress</span>
      <strong>${counts.in_progress}</strong>
    </button>
    <button class="stat-card" data-stat-filter="completed">
      <span>Completed</span>
      <strong>${counts.completed}</strong>
    </button>
  `;

  document.querySelectorAll("[data-stat-filter]").forEach((card) => {
    card.addEventListener("click", () => {
      el("statusFilter").value = card.dataset.statFilter;
      renderTickets();
    });
  });
}

function ticketItem(ticket) {
  return `
    <article class="item clickable ${state.selectedTicketId === ticket.id ? "selected" : ""}" data-ticket-id="${ticket.id}">
      <div class="item-head">
        <h3>${escapeHtml(ticket.title || "Untitled ticket")}</h3>
        <span class="badge">${escapeHtml(ticket.status)}</span>
      </div>
      <div class="meta-row">
        <span class="badge">${escapeHtml(ticket.category || "General")}</span>
        <span class="badge priority">${escapeHtml(ticket.priority || "Medium")}</span>
        <span class="badge">${ticket.reply_count} replies</span>
      </div>
      <p class="muted">${escapeHtml(ticket.conversation_id || "No conversation")}</p>
    </article>
  `;
}

async function selectTicket(ticketId, updateSelection = true) {
  const ticket = await api(`/tickets/${ticketId}`);
  if (updateSelection) state.selectedTicketId = ticketId;
  renderTickets();
  renderTicketDetail(ticket);
}

function renderTicketDetail(ticket) {
  const draftReplies = ticket.replies.filter((reply) => !reply.sent);
  const sentReplies = ticket.replies.filter((reply) => reply.sent);
  el("ticketDetail").classList.remove("empty");
  el("ticketDetail").innerHTML = `
    <div class="detail-grid">
      <div class="section">
        <div class="item-head">
          <div>
            <h2>${escapeHtml(ticket.title || "Untitled ticket")}</h2>
            <p class="muted">From ${escapeHtml(ticket.email?.sender_email || "unknown sender")}</p>
          </div>
          <span class="badge">${escapeHtml(ticket.status)}</span>
        </div>
        <div class="meta-row">
          <span class="badge">${escapeHtml(ticket.category || "General")}</span>
          <span class="badge priority">${escapeHtml(ticket.priority || "Medium")}</span>
          <span class="badge">${escapeHtml(ticket.conversation_id || "No conversation")}</span>
        </div>
        <div class="status-board">
          ${statusButton(ticket, "open", "Open")}
          ${statusButton(ticket, "in_progress", "In Progress")}
          ${statusButton(ticket, "completed", "Completed")}
        </div>
      </div>

      <div class="section">
        <h2>Mail Thread</h2>
        <div class="thread">
          ${threadMessage({
            direction: "inbound",
            title: ticket.email?.subject || ticket.title || "Original email",
            actor: ticket.email?.sender_email || "Customer",
            createdAt: ticket.created_at,
            body: ticket.email?.body || ticket.description || "",
          })}
          ${sentReplies.length ? sentReplies.map((reply) => threadMessage({
            direction: "outbound",
            title: reply.reply_type || "reply",
            actor: "Support team",
            createdAt: reply.created_at,
            body: reply.final_reply,
            approved: reply.approved,
            sent: reply.sent,
          })).join("") : `<p class="muted thread-empty">No replies have been sent yet.</p>`}
        </div>
      </div>

      <form id="newReplyForm" class="section">
        <h2>Create Reply Draft</h2>
        <div class="form-grid">
          <label>
            Type
            <select name="reply_type">
              <option value="update">Update</option>
              <option value="completion">Completion</option>
              <option value="acknowledgement">Acknowledgement</option>
              <option value="custom">Custom</option>
            </select>
          </label>
          <label>
            Instruction
            <input name="instruction" placeholder="Tell the user the task is complete">
          </label>
        </div>
        <div class="actions">
          <button class="primary" type="submit">Generate Draft</button>
        </div>
      </form>

      <div class="section">
        <h2>Reply Drafts</h2>
        ${draftReplies.length ? draftReplies.map(replyCard).join("") : `<p class="muted">No active drafts. Sent replies are shown in the mail thread.</p>`}
      </div>
    </div>
  `;

  el("newReplyForm").addEventListener("submit", (event) => createReplyDraft(event, ticket.id));
  document.querySelectorAll("[data-status-target]").forEach((button) => {
    button.addEventListener("click", () => updateTicketStatus(ticket.id, button.dataset.statusTarget));
  });
  bindReplyActions();
}

function statusButton(ticket, status, label) {
  const active = ticket.status === status ? "active" : "";
  return `
    <button type="button" class="status-step ${active}" data-status-target="${status}">
      <span>${escapeHtml(label)}</span>
    </button>
  `;
}

async function updateTicketStatus(ticketId, status) {
  try {
    await api(`/tickets/${ticketId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    showNotice("Ticket status updated.");
    await loadTickets();
    await selectTicket(ticketId, false);
  } catch (error) {
    showNotice(error.message, true);
  }
}

function threadMessage(message) {
  const status = message.direction === "outbound"
    ? `<div class="meta-row">
        ${message.approved ? `<span class="badge approved">Approved</span>` : `<span class="badge">Draft</span>`}
        ${message.sent ? `<span class="badge sent">Sent</span>` : ""}
      </div>`
    : "";

  return `
    <article class="thread-message ${message.direction}">
      <div class="thread-avatar">${message.direction === "inbound" ? "IN" : "OUT"}</div>
      <div class="thread-bubble">
        <div class="item-head">
          <div>
            <h3>${escapeHtml(message.title)}</h3>
            <p class="muted">${escapeHtml(message.actor)} · ${formatDate(message.createdAt)}</p>
          </div>
          ${status}
        </div>
        <div class="thread-body">${escapeHtml(message.body)}</div>
      </div>
    </article>
  `;
}

function replyCard(reply) {
  return `
    <article class="reply-card" data-reply-card="${reply.id}">
      <div class="item-head">
        <h3>${escapeHtml(reply.reply_type || "reply")}</h3>
        <div class="meta-row">
          ${reply.approved ? `<span class="badge approved">Approved</span>` : `<span class="badge">Draft</span>`}
          ${reply.sent ? `<span class="badge sent">Sent</span>` : ""}
        </div>
      </div>
      <div class="reply-box">${escapeHtml(reply.final_reply)}</div>
      <textarea rows="5" data-edit-reply="${reply.id}">${escapeHtml(reply.final_reply)}</textarea>
      <div class="actions">
        <button type="button" data-action="edit" data-reply-id="${reply.id}">Save Edit</button>
        <button type="button" data-action="polite" data-reply-id="${reply.id}">More Polite</button>
        <button type="button" data-action="shorten" data-reply-id="${reply.id}">Shorten</button>
        <button type="button" class="primary" data-action="approve" data-reply-id="${reply.id}">Approve</button>
        <button type="button" data-action="send" data-reply-id="${reply.id}">Send</button>
        <button type="button" class="danger" data-action="reject" data-reply-id="${reply.id}">Reject</button>
      </div>
    </article>
  `;
}

async function createReplyDraft(event, ticketId) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api(`/tickets/${ticketId}/replies`, {
    method: "POST",
    body: JSON.stringify({
      reply_type: form.get("reply_type"),
      instruction: form.get("instruction") || null,
    }),
  });
  showNotice("Reply draft created.");
  await selectTicket(ticketId, false);
}

function bindReplyActions() {
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => handleReplyAction(button));
  });
}

async function handleReplyAction(button) {
  const replyId = Number(button.dataset.replyId);
  const action = button.dataset.action;
  try {
    if (action === "edit") {
      const text = document.querySelector(`[data-edit-reply="${replyId}"]`).value;
      await api(`/replies/${replyId}/edit`, {
        method: "PUT",
        body: JSON.stringify({ modified_reply: text }),
      });
      showNotice("Reply edit saved.");
    }
    if (action === "polite" || action === "shorten") {
      const instruction = action === "polite" ? "Make it more polite and professional." : "Shorten the reply while keeping the meaning.";
      await api(`/replies/${replyId}/modify-ai`, {
        method: "POST",
        body: JSON.stringify({ instruction }),
      });
      showNotice("Reply updated with AI.");
    }
    if (action === "approve") {
      await api(`/replies/${replyId}/approve`, { method: "POST" });
      showNotice("Reply approved.");
    }
    if (action === "send") {
      await api(`/replies/${replyId}/send`, { method: "POST" });
      showNotice("Reply marked as sent.");
    }
    if (action === "reject") {
      await api(`/replies/${replyId}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason: "Rejected from dashboard" }),
      });
      showNotice("Reply rejected.");
    }
    await refreshCurrentView();
  } catch (error) {
    showNotice(error.message, true);
  }
}

async function loadApprovals() {
  state.approvals = await api("/replies/pending");
  el("approvalList").innerHTML = state.approvals.length
    ? state.approvals.map((reply) => `
      <article class="item">
        <div class="item-head">
          <div>
            <h3>${escapeHtml(reply.ticket?.title || `Reply ${reply.id}`)}</h3>
            <p class="muted">${escapeHtml(reply.reply_type || "reply")} draft</p>
          </div>
          <span class="badge priority">${escapeHtml(reply.ticket?.priority || "Medium")}</span>
        </div>
        <div class="reply-box">${escapeHtml(reply.final_reply)}</div>
        <div class="actions">
          <button class="primary" type="button" data-action="approve" data-reply-id="${reply.id}">Approve</button>
          <button type="button" data-action="send" data-reply-id="${reply.id}">Send</button>
          <button class="danger" type="button" data-action="reject" data-reply-id="${reply.id}">Reject</button>
        </div>
      </article>
    `).join("")
    : `<div class="item muted">No replies waiting for approval.</div>`;
  bindReplyActions();
}

async function loadEmails() {
  state.emails = await api("/emails/review");
  el("emailList").innerHTML = state.emails.length
    ? state.emails.map((email) => `
      <article class="item">
        <div class="item-head">
          <div>
            <h3>${escapeHtml(email.subject || "No subject")}</h3>
            <p class="muted">${escapeHtml(email.sender_email)} · ${formatDate(email.received_at)}</p>
          </div>
          <span class="badge priority">Review</span>
        </div>
        <div class="meta-row">
          <span class="badge">${escapeHtml(email.message_id)}</span>
          <span class="badge">${escapeHtml(email.conversation_id)}</span>
        </div>
        <p class="muted">${escapeHtml(email.body).slice(0, 180)}</p>
        <div class="actions">
          <button class="primary" type="button" data-email-action="approve" data-email-id="${email.id}">Create Ticket</button>
          <button class="danger" type="button" data-email-action="reject" data-email-id="${email.id}">Reject</button>
        </div>
      </article>
    `).join("")
    : `<div class="item muted">No emails waiting for review.</div>`;

  document.querySelectorAll("[data-email-action]").forEach((button) => {
    button.addEventListener("click", () => handleReviewAction(button));
  });
}

async function handleReviewAction(button) {
  const emailId = Number(button.dataset.emailId);
  const action = button.dataset.emailAction;
  try {
    if (action === "approve") {
      const result = await api(`/emails/${emailId}/approve-ticket`, { method: "POST" });
      showNotice(result.message || "Ticket created.");
      state.selectedTicketId = result.ticket_id || state.selectedTicketId;
    }
    if (action === "reject") {
      await api(`/emails/${emailId}/reject`, { method: "POST" });
      showNotice("Email rejected.");
    }
    await loadEmails();
  } catch (error) {
    showNotice(error.message, true);
  }
}

async function ingestEmail(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  try {
    const result = await api("/emails/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showNotice(result.message || "Email ingested.");
    event.currentTarget.reset();
    state.selectedTicketId = result.ticket_id || state.selectedTicketId;
  } catch (error) {
    showNotice(error.message, true);
  }
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

el("refreshBtn").addEventListener("click", refreshCurrentView);
el("statusFilter").addEventListener("change", renderTickets);
el("ingestForm").addEventListener("submit", ingestEmail);

setView("tickets");
