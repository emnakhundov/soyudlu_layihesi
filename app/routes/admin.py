import secrets

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..extensions import db
from ..models import AuditLog, Permission, Role, SUPER_ADMIN, User
from ..security import audit, hash_password, permission_required, to_int, utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _ids(field):
    return [i for i in (to_int(x) for x in request.form.getlist(field)) if i]


def _user(uid):
    return db.get_or_404(User, uid)


@bp.route("/users")
@permission_required("user.manage")
def users():
    users = User.query.filter_by(is_deleted=False).order_by(User.username).all()
    roles = Role.query.order_by(Role.name).all()
    return render_template("admin/users.html", users=users, roles=roles)


@bp.route("/users/new", methods=["POST"])
@permission_required("user.manage")
def create_user():
    f = request.form
    username = f.get("username", "").strip()
    if not username or User.query.filter_by(username=username).first():
        flash("İstifadəçi adı boşdur və ya artıq mövcuddur.", "error")
        return redirect(url_for("admin.users"))

    temporary = secrets.token_urlsafe(9) + "Aa1!"
    user = User(
        username=username,
        email=f.get("email", "").strip(),
        full_name=f.get("full_name", "").strip(),
        password_hash=hash_password(temporary),
        force_password_change=True,
        is_2fa_enabled=False,
    )
    user.roles = Role.query.filter(Role.id.in_(_ids("role_ids"))).all()
    db.session.add(user)
    audit("user.created", username)
    db.session.commit()
    flash(f"İstifadəçi yaradıldı. Müvəqqəti parol (yalnız bir dəfə göstərilir): {temporary}", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:uid>/roles", methods=["POST"])
@permission_required("user.manage")
def set_roles(uid):
    user = _user(uid)
    new_roles = Role.query.filter(Role.id.in_(_ids("role_ids"))).all()
    touches_super = any(r.name == SUPER_ADMIN for r in new_roles) or user.is_super_admin
    if touches_super and not g.current_user.is_super_admin:
        abort(403)
    user.roles = new_roles
    audit("user.roles_changed", user.username, ",".join(r.name for r in new_roles))
    db.session.commit()
    flash("Rollar yeniləndi.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:uid>/action/<action>", methods=["POST"])
@permission_required("user.manage")
def user_action(uid, action):
    user = _user(uid)
    if user.id == g.current_user.id:
        flash("Öz hesabınız üzərində bu əməliyyatı etmək olmaz.", "error")
        return redirect(url_for("admin.users"))
    if user.is_super_admin and not g.current_user.is_super_admin:
        abort(403)

    if action == "toggle":
        user.is_active = not user.is_active
        audit("user.toggled", user.username, f"active={user.is_active}")
    elif action == "reset-2fa":
        user.is_2fa_enabled = False
        user.totp_secret = None
        user.recovery_codes = "[]"
        user.last_totp_step = 0
        user.force_password_change = True
        audit("user.2fa_reset", user.username)
    elif action == "delete":
        user.is_deleted = True
        user.is_active = False
        user.deleted_at = utcnow()
        user.deleted_by_id = g.current_user.id
        audit("user.deleted", user.username)
    else:
        abort(404)
    db.session.commit()
    flash("Əməliyyat tamamlandı.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/roles")
@permission_required("role.manage")
def roles():
    roles = Role.query.order_by(Role.name).all()
    permissions = Permission.query.order_by(Permission.code).all()
    return render_template("admin/roles.html", roles=roles, permissions=permissions)


@bp.route("/roles/new", methods=["POST"])
@permission_required("role.manage")
def create_role():
    name = request.form.get("name", "").strip()
    if not name or Role.query.filter_by(name=name).first():
        flash("Rol adı boşdur və ya artıq mövcuddur.", "error")
        return redirect(url_for("admin.roles"))
    role = Role(name=name, description=request.form.get("description", "").strip())
    role.permissions = Permission.query.filter(Permission.id.in_(_ids("permission_ids"))).all()
    db.session.add(role)
    audit("role.created", name)
    db.session.commit()
    flash("Rol yaradıldı.", "success")
    return redirect(url_for("admin.roles"))


@bp.route("/audit")
@permission_required("audit.view")
def audit_log():
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(300).all()
    return render_template("admin/audit.html", logs=logs)
