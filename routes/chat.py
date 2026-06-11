"""Direct messaging between connected users, with NLP abuse detection."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user

from models import db, User, Message, Report
from services.nlp_service import predict_abuse
from services.abuse_service import apply_abuse_consequences

chat_bp = Blueprint("chat", __name__)


def _assert_connected(other: User):
    """Abort 403 if current_user is not connected with other."""
    if not current_user.is_connected_with(other):
        abort(403)


@chat_bp.route("/")
@login_required
def inbox():
    """List all conversations (unique partners) for the current user."""
    # Collect unique conversation partners
    partners_ids = set()
    for msg in Message.query.filter(
        (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
    ).all():
        pid = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        partners_ids.add(pid)

    conversations = []
    for pid in partners_ids:
        partner = User.query.get(pid)
        if not partner:
            continue
        last_msg = Message.query.filter(
            ((Message.sender_id == current_user.id)   & (Message.receiver_id == pid)) |
            ((Message.sender_id == pid) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.desc()).first()
        unread = Message.query.filter_by(
            sender_id=pid, receiver_id=current_user.id, is_read=False
        ).count()
        conversations.append({"partner": partner, "last_msg": last_msg, "unread": unread})

    # Sort by most recent message
    conversations.sort(key=lambda c: c["last_msg"].created_at, reverse=True)
    return render_template("chat/inbox.html", conversations=conversations)


@chat_bp.route("/<username>", methods=["GET", "POST"])
@login_required
def thread(username: str):
    """View and send messages in a conversation thread."""
    partner = User.query.filter_by(username=username).first_or_404()
    _assert_connected(partner)

    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        if not content:
            flash("Message cannot be empty.", "warning")
            return redirect(url_for("chat.thread", username=username))
        if len(content) > 1000:
            flash("Message too long (max 1000 characters).", "warning")
            return redirect(url_for("chat.thread", username=username))

        # ── NLP prediction ────────────────────────────────────────────────
        result = predict_abuse(content)

        msg = Message(
            sender_id        = current_user.id,
            receiver_id      = partner.id,
            content          = content,
            prediction       = result["label"],
            confidence_score = result["confidence"],
        )
        db.session.add(msg)
        db.session.commit()

        # Apply abuse consequences (same rules as tweets)
        notice = apply_abuse_consequences(current_user, result["label"] == "abusive")
        if notice:
            flash(notice, "warning")

        return redirect(url_for("chat.thread", username=username))

    # Mark incoming messages as read
    Message.query.filter_by(
        sender_id=partner.id, receiver_id=current_user.id, is_read=False
    ).update({"is_read": True})
    db.session.commit()

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id)    & (Message.receiver_id == partner.id)) |
        ((Message.sender_id == partner.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()

    return render_template("chat/thread.html", partner=partner, messages=messages)


@chat_bp.route("/report/<int:message_id>", methods=["POST"])
@login_required
def report_message(message_id: int):
    """Report a message to admins."""
    msg = Message.query.get_or_404(message_id)

    # Only the receiver of the message can report it
    if msg.receiver_id != current_user.id:
        abort(403)

    # Prevent duplicate reports from the same user
    already = Report.query.filter_by(reporter_id=current_user.id, message_id=message_id).first()
    if already:
        flash("You have already reported this message.", "info")
        return redirect(url_for("chat.thread", username=msg.sender.username))

    reason = (request.form.get("reason") or "").strip()[:300]
    report = Report(reporter_id=current_user.id, message_id=message_id, reason=reason or None)
    db.session.add(report)
    db.session.commit()
    flash("Message reported. Our team will review it.", "success")
    return redirect(url_for("chat.thread", username=msg.sender.username))
