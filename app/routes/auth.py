import base64
import hmac
import io
import json
import secrets
import time
from datetime import timedelta

import pyotp
import qrcode
from flask import (Blueprint, current_app, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import User
from ..security import audit, check_password_policy, hash_password, utcnow, verify_password

bp = Blueprint("auth", __name__)


def _pre_user():
    """User who has passed the password step but is not yet fully logged in."""
    uid = session.get("pre_uid")
    return db.session.get(User, uid) if uid else None


def _next_step(user):
    if user.force_password_change:
        return "auth.change_password"
    if not user.is_2fa_enabled:
        return "auth.setup_2fa"
    return "auth.verify_2fa"


def _match_step(totp, code, last_step):
    """Returns the matching 30-second step (±1 window), rejecting replays."""
    base = int(time.time()) // 30
    for offset in (-1, 0, 1):
        step = base + offset
        if step <= last_step:
            continue
        if hmac.compare_digest(totp.at(step * 30), code):
            return step
    return None


def _use_recovery_code(user, code):
    codes = json.loads(user.recovery_codes or "[]")
    for index, code_hash in enumerate(codes):
        if check_password_hash(code_hash, code.upper()):
            del codes[index]
            user.recovery_codes = json.dumps(codes)
            return True
    return False


def _qr_data_uri(text):
    buffer = io.BytesIO()
    qrcode.make(text).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _finish_login(user):
    session.clear()
    session["user_id"] = user.id
    session["last_seen"] = time.time()
    user.last_login = utcnow()
    user.failed_login_attempts = 0
    audit("login.success", user.username, user_id=user.id)
    db.session.commit()
    return redirect(url_for("main.dashboard"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.current_user is not None:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username, is_deleted=False).first()

        if user is None:
            audit("login.failed", username, "unknown user")
            db.session.commit()
            flash("Yanlış istifadəçi adı və ya parol.", "error")
            return render_template("login.html")

        if user.is_locked() or not user.is_active:
            audit("login.blocked", username, user_id=user.id)
            db.session.commit()
            flash("Hesab bloklanıb və ya deaktivdir.", "error")
            return render_template("login.html")

        if not verify_password(user.password_hash, password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= current_app.config["MAX_FAILED_LOGINS"]:
                user.locked_until = utcnow() + timedelta(minutes=current_app.config["LOCKOUT_MINUTES"])
                user.failed_login_attempts = 0
            audit("login.failed", username, "wrong password", user_id=user.id)
            db.session.commit()
            flash("Yanlış istifadəçi adı və ya parol.", "error")
            return render_template("login.html")

        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
        session.clear()
        session["pre_uid"] = user.id
        return redirect(url_for(_next_step(user)))

    return render_template("login.html")


@bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    user = g.current_user or _pre_user()
    if user is None:
        return redirect(url_for("auth.login"))
    voluntary = g.current_user is not None

    if request.method == "POST":
        errors = []
        if voluntary and not verify_password(user.password_hash, request.form.get("current_password", "")):
            errors.append("Cari parol yanlışdır")
        new = request.form.get("new_password", "")
        if new != request.form.get("confirm_password", ""):
            errors.append("Yeni parollar uyğun gəlmir")
        errors += check_password_policy(new)
        if verify_password(user.password_hash, new):
            errors.append("Yeni parol köhnə parolla eyni ola bilməz")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("change_password.html", voluntary=voluntary)

        user.password_hash = hash_password(new)
        user.force_password_change = False
        audit("password.changed", user.username, user_id=user.id)
        db.session.commit()
        if voluntary:
            flash("Parol yeniləndi.", "success")
            return redirect(url_for("main.dashboard"))
        return redirect(url_for(_next_step(user)))

    return render_template("change_password.html", voluntary=voluntary)


@bp.route("/setup-2fa", methods=["GET", "POST"])
def setup_2fa():
    user = _pre_user()
    if user is None:
        return redirect(url_for("auth.login"))
    if user.force_password_change:
        return redirect(url_for("auth.change_password"))
    if user.is_2fa_enabled:
        return redirect(url_for("auth.verify_2fa"))

    secret = session.get("totp_setup")
    if not secret:
        secret = pyotp.random_base32()
        session["totp_setup"] = secret
    totp = pyotp.TOTP(secret)

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        step = _match_step(totp, code, 0) if code.isdigit() and len(code) == 6 else None
        if step is None:
            flash("Kod yanlışdır və ya vaxtı keçib. Yenidən cəhd edin.", "error")
        else:
            codes = [secrets.token_hex(4).upper() for _ in range(10)]
            user.totp_secret = secret
            user.is_2fa_enabled = True
            user.last_totp_step = step
            user.recovery_codes = json.dumps([generate_password_hash(c) for c in codes])
            session.pop("totp_setup", None)
            audit("2fa.enabled", user.username, user_id=user.id)
            db.session.commit()
            return render_template("recovery_codes.html", codes=codes)

    uri = totp.provisioning_uri(name=user.username, issuer_name=current_app.config["TOTP_ISSUER"])
    return render_template("setup_2fa.html", qr=_qr_data_uri(uri), secret=secret)


@bp.route("/verify-2fa", methods=["GET", "POST"])
def verify_2fa():
    user = _pre_user()
    if user is None:
        return redirect(url_for("auth.login"))
    if user.force_password_change:
        return redirect(url_for("auth.change_password"))
    if not user.is_2fa_enabled:
        return redirect(url_for("auth.setup_2fa"))
    if user.is_locked():
        session.clear()
        flash("Hesab müvəqqəti bloklanıb.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code", "").strip().replace(" ", "")
        ok = False
        if code.isdigit() and len(code) == 6:
            step = _match_step(pyotp.TOTP(user.totp_secret), code, user.last_totp_step)
            if step is not None:
                user.last_totp_step = step
                ok = True
        if not ok and _use_recovery_code(user, code):
            audit("2fa.recovery_used", user.username, user_id=user.id)
            ok = True
        if ok:
            return _finish_login(user)

        user.failed_login_attempts += 1
        if user.failed_login_attempts >= current_app.config["MAX_FAILED_LOGINS"]:
            user.locked_until = utcnow() + timedelta(minutes=current_app.config["LOCKOUT_MINUTES"])
            user.failed_login_attempts = 0
            session.clear()
        audit("2fa.failed", user.username, user_id=user.id)
        db.session.commit()
        flash("Kod yanlışdır və ya artıq istifadə olunub.", "error")
        if "pre_uid" not in session:
            return redirect(url_for("auth.login"))

    return render_template("verify_2fa.html")


@bp.route("/complete-login")
def complete_login():
    user = _pre_user()
    if user is None or user.force_password_change or not user.is_2fa_enabled:
        return redirect(url_for("auth.login"))
    return _finish_login(user)


@bp.route("/logout")
def logout():
    if g.current_user is not None:
        audit("logout", g.current_user.username, user_id=g.current_user.id)
        db.session.commit()
    session.clear()
    return redirect(url_for("auth.login"))
