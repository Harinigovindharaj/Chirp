"""
Abuse monitoring rules.

Centralizes the threshold logic so it lives in one place:
    abuse_score = 1  -> warning issued (status: warned)
    abuse_score = 3  -> temporarily blocked
    abuse_score = 5  -> permanently banned
"""
from models import (
    db,
    User,
    STATUS_ACTIVE,
    STATUS_WARNED,
    STATUS_TEMP_BLOCKED,
    STATUS_BANNED,
)

WARN_THRESHOLD = 1
TEMP_BLOCK_THRESHOLD = 3
BAN_THRESHOLD = 5


def apply_abuse_consequences(user: User, was_abusive: bool) -> str | None:
    """
    Update the user's abuse_score / status based on the new tweet's prediction.

    Returns a human-readable notice string (or None) that the caller can flash.
    """
    if not was_abusive:
        return None

    user.abuse_score += 1
    notice = None

    if user.abuse_score >= BAN_THRESHOLD:
        user.account_status = STATUS_BANNED
        notice = "Your account has been permanently banned due to repeated abusive content."
    elif user.abuse_score >= TEMP_BLOCK_THRESHOLD:
        user.account_status = STATUS_TEMP_BLOCKED
        notice = "Your account has been temporarily blocked due to abusive content."
    elif user.abuse_score >= WARN_THRESHOLD:
        user.warning_count += 1
        if user.account_status == STATUS_ACTIVE:
            user.account_status = STATUS_WARNED
        notice = "Warning: this tweet was flagged as abusive."

    db.session.commit()
    return notice


def reset_user_abuse(user: User) -> None:
    user.abuse_score = 0
    user.warning_count = 0
    user.account_status = STATUS_ACTIVE
    db.session.commit()


def unblock_user(user: User) -> None:
    if user.account_status in (STATUS_TEMP_BLOCKED, STATUS_BANNED):
        user.account_status = STATUS_ACTIVE
        db.session.commit()
