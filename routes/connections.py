"""Connection requests: send, accept, reject, list."""
from flask import Blueprint, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from models import db, User, Connection, CONN_PENDING, CONN_ACCEPTED, CONN_REJECTED

connections_bp = Blueprint("connections", __name__)


@connections_bp.route("/request/<int:user_id>", methods=["POST"])
@login_required
def send_request(user_id: int):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash("You cannot connect with yourself.", "warning")
        return redirect(url_for("tweets.profile", username=target.username))

    # Already connected or pending
    existing = Connection.query.filter(
        ((Connection.requester_id == current_user.id) & (Connection.receiver_id == target.id)) |
        ((Connection.requester_id == target.id)       & (Connection.receiver_id == current_user.id))
    ).first()

    if existing:
        flash("Connection request already exists.", "info")
    else:
        conn = Connection(requester_id=current_user.id, receiver_id=target.id)
        db.session.add(conn)
        db.session.commit()
        flash(f"Connection request sent to @{target.username}.", "success")

    return redirect(url_for("tweets.profile", username=target.username))


@connections_bp.route("/accept/<int:conn_id>", methods=["POST"])
@login_required
def accept(conn_id: int):
    conn = Connection.query.get_or_404(conn_id)
    if conn.receiver_id != current_user.id:
        abort(403)
    conn.status = CONN_ACCEPTED
    db.session.commit()
    flash(f"You are now connected with @{conn.requester.username}.", "success")
    return redirect(url_for("connections.requests"))


@connections_bp.route("/reject/<int:conn_id>", methods=["POST"])
@login_required
def reject(conn_id: int):
    conn = Connection.query.get_or_404(conn_id)
    if conn.receiver_id != current_user.id:
        abort(403)
    conn.status = CONN_REJECTED
    db.session.commit()
    flash("Request declined.", "info")
    return redirect(url_for("connections.requests"))


@connections_bp.route("/requests")
@login_required
def requests():
    pending = current_user.pending_incoming
    return _render("connections/requests.html", pending=pending)


@connections_bp.route("/list")
@login_required
def list_connections():
    users = current_user.connections
    return _render("connections/list.html", users=users)


def _render(template, **ctx):
    from flask import render_template
    return render_template(template, **ctx)
