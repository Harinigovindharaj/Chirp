"""Mini Twitter Clone — Flask application factory."""
import os
from flask import Flask
from flask_login import LoginManager

from models import db, User
from routes.auth        import auth_bp
from routes.main        import main_bp
from routes.tweets      import tweets_bp
from routes.admin       import admin_bp
from routes.connections import connections_bp
from routes.chat        import chat_bp

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path  = os.path.join(base_dir, "database", "app.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    app.config.update(
        SECRET_KEY                  = os.environ.get("SECRET_KEY", "dev-change-me-in-production"),
        SQLALCHEMY_DATABASE_URI     = f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS = False,
        SESSION_COOKIE_HTTPONLY     = True,
        SESSION_COOKIE_SAMESITE     = "Lax",
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp,         url_prefix="/auth")
    app.register_blueprint(tweets_bp,       url_prefix="/tweets")
    app.register_blueprint(admin_bp,        url_prefix="/admin")
    app.register_blueprint(connections_bp,  url_prefix="/connections")
    app.register_blueprint(chat_bp,         url_prefix="/chat")

    with app.app_context():
        db.create_all()
        _ensure_default_admin()

    return app


def _ensure_default_admin() -> None:
    from werkzeug.security import generate_password_hash
    if User.query.filter_by(role="admin").first():
        return
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash=generate_password_hash("admin123"),
        role="admin",
    )
    db.session.add(admin)
    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
