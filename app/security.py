import re
from datetime import datetime, timezone
from functools import wraps

from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask import abort, g, redirect, request, url_for

from .extensions import db, ph


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password):
    return ph.hash(password)


def verify_password(password_hash, password):
    try:
        return ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def check_password_policy(password):
    rules = [
        (len(password) >= 10, "Parol ən azı 10 simvoldan ibarət olmalıdır"),
        (re.search(r"[A-Z]", password), "Ən azı bir böyük latın hərfi olmalıdır"),
        (re.search(r"[a-z]", password), "Ən azı bir kiçik latın hərfi olmalıdır"),
        (re.search(r"\d", password), "Ən azı bir rəqəm olmalıdır"),
        (re.search(r"[^\w\s]", password), "Ən azı bir xüsusi simvol olmalıdır"),
    ]
    return [message for ok, message in rules if not ok]


def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def audit(action, target="", details="", user_id=None):
    """Adds an audit entry to the session. The caller commits."""
    from .models import AuditLog

    if user_id is None and g.get("current_user") is not None:
        user_id = g.current_user.id
    db.session.add(AuditLog(
        user_id=user_id,
        action=action,
        target=str(target)[:200],
        details=str(details)[:1000],
        ip=request.remote_addr,
    ))


def permission_required(*codes):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = g.get("current_user")
            if user is None:
                return redirect(url_for("auth.login"))
            if not all(user.has_permission(code) for code in codes):
                audit("permission.denied", request.path, ",".join(codes))
                db.session.commit()
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator
