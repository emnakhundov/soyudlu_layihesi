from flask import current_app

from .extensions import db
from .models import SUPER_ADMIN, Permission, Role, User
from .security import hash_password

PERMISSIONS = {
    "vehicle.view": "Avtomobilləri görmək",
    "vehicle.manage": "Avtomobil əlavə etmək",
    "repair.view": "Təmir müraciətlərini görmək",
    "repair.create": "Təmir müraciəti yaratmaq",
    "repair.assign": "Təmir işini təyin etmək",
    "repair.update": "Təmir işini icra etmək",
    "repair.approve": "Təmiri təsdiq / rədd etmək",
    "report.view": "Hesabatları görmək və ixrac etmək",
    "audit.view": "Audit jurnalına baxmaq",
    "user.manage": "İstifadəçiləri idarə etmək",
    "role.manage": "Rolları idarə etmək",
}

ROLES = {
    SUPER_ADMIN: (["*"], "Bütün icazələr, dəyişdirilmir"),
    "Administrator": (
        ["vehicle.view", "vehicle.manage", "repair.view", "report.view",
         "audit.view", "user.manage", "role.manage"],
        "Sistem administratoru",
    ),
    "Dispetçer": (["vehicle.view", "repair.view", "repair.create", "report.view"],
                  "Müraciət yaradır"),
    "Təmir mühəndisi": (
        ["vehicle.view", "repair.view", "repair.assign", "repair.update",
         "repair.approve", "report.view"],
        "Təyin edir və təsdiqləyir",
    ),
    "Təmir texniki": (["vehicle.view", "repair.view", "repair.update"],
                      "Təmir işlərini icra edir"),
    "Nəzarətçi": (["vehicle.view", "repair.view", "repair.assign",
                   "repair.approve", "report.view"], "Nəzarət və təsdiq"),
    "İzləyici": (["vehicle.view", "repair.view", "report.view"], "Yalnız baxış"),
}


def seed():
    """Idempotent: safe to run on every start."""
    perm_map = {}
    for code, description in PERMISSIONS.items():
        perm = Permission.query.filter_by(code=code).first()
        if perm is None:
            perm = Permission(code=code, description=description)
            db.session.add(perm)
        perm_map[code] = perm
    db.session.flush()

    all_perms = Permission.query.all()
    for name, (codes, description) in ROLES.items():
        if Role.query.filter_by(name=name).first() is None:
            role = Role(name=name, description=description)
            role.permissions = all_perms if codes == ["*"] else [perm_map[c] for c in codes]
            db.session.add(role)
    db.session.flush()

    admin_name = current_app.config["ADMIN_USERNAME"]
    if User.query.filter_by(username=admin_name).first() is None:
        admin = User(
            username=admin_name,
            email=current_app.config["ADMIN_EMAIL"],
            full_name="Sistem administratoru",
            password_hash=hash_password(current_app.config["ADMIN_PASSWORD"]),
            force_password_change=True,
            is_2fa_enabled=False,
        )
        admin.roles = [Role.query.filter_by(name=SUPER_ADMIN).first()]
        db.session.add(admin)

    db.session.commit()
