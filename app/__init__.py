import os
import time

from flask import Flask, flash, g, redirect, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config

from .extensions import csrf, db

# Endpoints reachable without a fully logged-in session.
PUBLIC_ENDPOINTS = {
    "auth.login", "auth.change_password", "auth.setup_2fa",
    "auth.verify_2fa", "auth.complete_login", "auth.logout", "static",
}


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    from .routes.admin import bp as admin_bp
    from .routes.auth import bp as auth_bp
    from .routes.main import bp as main_bp
    from .routes.repairs import bp as repairs_bp
    from .routes.vehicles import bp as vehicles_bp

    for blueprint in (auth_bp, main_bp, vehicles_bp, repairs_bp, admin_bp):
        app.register_blueprint(blueprint)

    @app.before_request
    def load_current_user():
        from .models import User

        g.current_user = None
        endpoint = request.endpoint or ""
        uid = session.get("user_id")

        if uid is None:
            if endpoint in PUBLIC_ENDPOINTS:
                return None
            return redirect(url_for("auth.login"))

        timeout = app.config["SESSION_TIMEOUT_MINUTES"] * 60
        if time.time() - session.get("last_seen", 0) > timeout:
            session.clear()
            flash("Sessiya vaxtı bitdi. Yenidən daxil olun.", "error")
            return redirect(url_for("auth.login"))

        user = db.session.get(User, uid)
        if user is None or not user.is_active or user.is_deleted:
            session.clear()
            return redirect(url_for("auth.login"))

        g.current_user = user
        session["last_seen"] = time.time()

        if user.force_password_change and endpoint not in ("auth.change_password", "auth.logout", "static"):
            return redirect(url_for("auth.change_password"))
        return None

    @app.context_processor
    def inject_globals():
        from .models import Notification

        user = g.get("current_user")
        unread = 0
        if user is not None:
            unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        return {"current_user": user, "unread_count": unread}

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response
    @app.after_request
    def force_utf8(response):
        if response.mimetype == "text/html":
            response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response

    return app
