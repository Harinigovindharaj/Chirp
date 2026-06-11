"""Tweet feed, composer, and personal profile."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from models import db, Tweet, User
from services.nlp_service import predict_abuse
from services.abuse_service import apply_abuse_consequences

tweets_bp = Blueprint("tweets", __name__)


@tweets_bp.route("/")
@login_required
def feed():
    """Public feed — newest first."""
    tweets = Tweet.query.order_by(Tweet.created_at.desc()).limit(100).all()
    return render_template("feed.html", tweets=tweets)


@tweets_bp.route("/new", methods=["POST"])
@login_required
def create():
    content = (request.form.get("content") or "").strip()

    # Block posting if user is blocked/banned
    if not current_user.can_post:
        flash(current_user.post_block_reason or "You cannot post right now.", "danger")
        return redirect(url_for("tweets.feed"))

    if not content:
        flash("Tweet cannot be empty.", "warning")
        return redirect(url_for("tweets.feed"))
    if len(content) > 280:
        flash("Tweet must be 280 characters or fewer.", "warning")
        return redirect(url_for("tweets.feed"))

    # --- NLP pipeline (placeholder) ---
    result = predict_abuse(content)

    tweet = Tweet(
        user_id=current_user.id,
        content=content,
        prediction=result["label"],
        confidence_score=result["confidence"],
    )
    db.session.add(tweet)
    db.session.commit()

    # --- Abuse monitoring ---
    notice = apply_abuse_consequences(current_user, result["label"] == "abusive")
    if notice:
        flash(notice, "warning")
    else:
        flash("Tweet posted.", "success")

    return redirect(url_for("tweets.feed"))


@tweets_bp.route("/profile")
@tweets_bp.route("/profile/<username>")
@login_required
def profile(username: str | None = None):
    user = (
        User.query.filter_by(username=username).first_or_404()
        if username
        else current_user
    )
    user_tweets = (
        Tweet.query.filter_by(user_id=user.id)
        .order_by(Tweet.created_at.desc())
        .all()
    )
    return render_template("profile.html", profile_user=user, tweets=user_tweets)
