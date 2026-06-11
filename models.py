"""SQLAlchemy models for users, tweets, connections, messages, and reports."""
from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Account status values
STATUS_ACTIVE          = "active"
STATUS_WARNED          = "warned"
STATUS_TEMP_BLOCKED    = "temporarily_blocked"
STATUS_BANNED          = "permanently_banned"

# Connection status values
CONN_PENDING  = "pending"
CONN_ACCEPTED = "accepted"
CONN_REJECTED = "rejected"


class Connection(db.Model):
    """
    Directed connection request: requester → receiver.
    Once accepted, both users are considered connected.
    """
    __tablename__ = "connections"

    id           = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id  = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status       = db.Column(db.String(20), nullable=False, default=CONN_PENDING)
    created_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    requester = db.relationship("User", foreign_keys=[requester_id], backref="sent_requests")
    receiver  = db.relationship("User", foreign_keys=[receiver_id],  backref="received_requests")

    __table_args__ = (
        db.UniqueConstraint("requester_id", "receiver_id", name="uq_connection"),
    )


class Message(db.Model):
    """Direct message between two connected users."""
    __tablename__ = "messages"

    id           = db.Column(db.Integer, primary_key=True)
    sender_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id  = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content      = db.Column(db.String(1000), nullable=False)

    # NLP fields
    prediction       = db.Column(db.String(20), nullable=True)  # 'abusive' | 'non_abusive'
    confidence_score = db.Column(db.Float, nullable=True)

    is_read    = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    sender   = db.relationship("User", foreign_keys=[sender_id],   backref="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_messages")

    @property
    def is_abusive(self) -> bool:
        return self.prediction == "abusive"


class Report(db.Model):
    """A user reports an abusive message to admins."""
    __tablename__ = "reports"

    id          = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message_id  = db.Column(db.Integer, db.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    reason      = db.Column(db.String(300), nullable=True)
    resolved    = db.Column(db.Boolean, nullable=False, default=False)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    reporter = db.relationship("User",    foreign_keys=[reporter_id], backref="filed_reports")
    message  = db.relationship("Message", foreign_keys=[message_id],  backref="reports")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(64),  unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20),  nullable=False, default="user")

    # Abuse monitoring
    abuse_score    = db.Column(db.Integer, nullable=False, default=0)
    warning_count  = db.Column(db.Integer, nullable=False, default=0)
    account_status = db.Column(db.String(30), nullable=False, default=STATUS_ACTIVE)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tweets = db.relationship("Tweet", backref="author", lazy="dynamic", cascade="all, delete-orphan")

    # ── Connection helpers ──────────────────────────────────────────────────
    def connection_status_with(self, other_user) -> str | None:
        """Return connection status between self and other_user, or None."""
        conn = Connection.query.filter(
            (
                (Connection.requester_id == self.id) & (Connection.receiver_id == other_user.id)
            ) | (
                (Connection.requester_id == other_user.id) & (Connection.receiver_id == self.id)
            )
        ).first()
        return conn.status if conn else None

    def is_connected_with(self, other_user) -> bool:
        return self.connection_status_with(other_user) == CONN_ACCEPTED

    def pending_request_from(self, other_user) -> bool:
        """True if other_user sent a pending request to self."""
        return Connection.query.filter_by(
            requester_id=other_user.id, receiver_id=self.id, status=CONN_PENDING
        ).first() is not None

    @property
    def connections(self):
        """All accepted connections as User objects."""
        sent = (
            db.session.query(User)
            .join(Connection, Connection.receiver_id == User.id)
            .filter(Connection.requester_id == self.id, Connection.status == CONN_ACCEPTED)
        )
        received = (
            db.session.query(User)
            .join(Connection, Connection.requester_id == User.id)
            .filter(Connection.receiver_id == self.id, Connection.status == CONN_ACCEPTED)
        )
        return sent.union(received).all()

    @property
    def pending_incoming(self):
        """Pending connection requests sent TO this user."""
        return Connection.query.filter_by(receiver_id=self.id, status=CONN_PENDING).all()

    @property
    def unread_message_count(self):
        return Message.query.filter_by(receiver_id=self.id, is_read=False).count()

    # ── Status helpers ──────────────────────────────────────────────────────
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def can_post(self) -> bool:
        return self.account_status in (STATUS_ACTIVE, STATUS_WARNED)

    @property
    def post_block_reason(self) -> str | None:
        if self.account_status == STATUS_TEMP_BLOCKED:
            return "Your account is temporarily blocked due to repeated abusive content."
        if self.account_status == STATUS_BANNED:
            return "Your account has been permanently banned."
        return None


class Tweet(db.Model):
    __tablename__ = "tweets"

    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.String(280), nullable=False)

    prediction       = db.Column(db.String(20), nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    @property
    def is_abusive(self) -> bool:
        return self.prediction == "abusive"
