"""Admin dashboard — restricted to users with role='admin'."""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from models import db, User, Tweet, Message, Report, STATUS_TEMP_BLOCKED, STATUS_BANNED
from services.abuse_service import reset_user_abuse, unblock_user

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


@admin_bp.route("/")
@admin_required
def dashboard():
    users         = User.query.order_by(User.created_at.desc()).all()
    tweets        = Tweet.query.order_by(Tweet.created_at.desc()).limit(200).all()
    abusive_tweets = Tweet.query.filter_by(prediction="abusive").order_by(Tweet.created_at.desc()).all()
    abusive_msgs  = Message.query.filter_by(prediction="abusive").order_by(Message.created_at.desc()).all()
    reports       = Report.query.filter_by(resolved=False).order_by(Report.created_at.desc()).all()
    blocked       = User.query.filter_by(account_status=STATUS_TEMP_BLOCKED).all()
    banned        = User.query.filter_by(account_status=STATUS_BANNED).all()
    return render_template(
        "admin.html",
        users=users, tweets=tweets,
        abusive_tweets=abusive_tweets, abusive_msgs=abusive_msgs,
        reports=reports, blocked=blocked, banned=banned,
    )


@admin_bp.route("/reset/<int:user_id>", methods=["POST"])
@admin_required
def reset_score(user_id: int):
    user = User.query.get_or_404(user_id)
    reset_user_abuse(user)
    flash(f"Abuse score reset for @{user.username}.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/unblock/<int:user_id>", methods=["POST"])
@admin_required
def unblock(user_id: int):
    user = User.query.get_or_404(user_id)
    unblock_user(user)
    flash(f"@{user.username} has been unblocked.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/report/resolve/<int:report_id>", methods=["POST"])
@admin_required
def resolve_report(report_id: int):
    report = Report.query.get_or_404(report_id)
    report.resolved = True
    db.session.commit()
    flash("Report marked as resolved.", "success")
    return redirect(url_for("admin.dashboard"))
