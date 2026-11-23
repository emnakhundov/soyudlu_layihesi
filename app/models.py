from .extensions import db
from .security import utcnow

SUPER_ADMIN = "Super Admin"
STATUSES = ["Yeni", "Təyin edildi", "Təmirdə", "Gözləmədə", "Tamamlandı", "Təsdiqləndi"]
WORKABLE_STATUSES = ("Təyin edildi", "Təmirdə", "Gözləmədə")
FINAL_STATUSES = ("Tamamlandı", "Təsdiqləndi")
PRIORITIES = ["Normal", "Yüksək", "Təcili"]

user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
)
role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)
user_permissions = db.Table(
    "user_permissions",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255), default="")


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255), default="")
    permissions = db.relationship("Permission", secondary=role_permissions, lazy="selectin")


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), default="")
    full_name = db.Column(db.String(120), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer)
    force_password_change = db.Column(db.Boolean, default=True, nullable=False)
    is_2fa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    totp_secret = db.Column(db.String(64))
    last_totp_step = db.Column(db.Integer, default=0, nullable=False)
    recovery_codes = db.Column(db.Text, default="[]", nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login = db.Column(db.DateTime)

    roles = db.relationship("Role", secondary=user_roles, lazy="selectin")
    direct_permissions = db.relationship("Permission", secondary=user_permissions, lazy="selectin")

    @property
    def is_super_admin(self):
        return any(r.name == SUPER_ADMIN for r in self.roles)

    def has_permission(self, code):
        if not self.is_active or self.is_deleted:
            return False
        if self.is_super_admin:
            return True
        if any(p.code == code for p in self.direct_permissions):
            return True
        return any(p.code == code for r in self.roles for p in r.permissions)

    def is_locked(self):
        return bool(self.locked_until and self.locked_until > utcnow())


class Vehicle(db.Model):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), unique=True, nullable=False)
    make = db.Column(db.String(80), default="")
    model = db.Column(db.String(80), default="")
    year = db.Column(db.Integer)
    mileage = db.Column(db.Integer, default=0)
    department = db.Column(db.String(120), default="")
    status = db.Column(db.String(30), default="Aktiv")
    created_at = db.Column(db.DateTime, default=utcnow)


class RepairRequest(db.Model):
    __tablename__ = "repair_requests"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    priority = db.Column(db.String(20), default="Normal")
    status = db.Column(db.String(30), default="Yeni", index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    assignment_notes = db.Column(db.Text, default="")
    completion_notes = db.Column(db.Text, default="")
    reject_reason = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)

    vehicle = db.relationship("Vehicle")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    assignee = db.relationship("User", foreign_keys=[assignee_id])
    updates = db.relationship("RepairUpdate", back_populates="repair",
                              order_by="RepairUpdate.created_at")


class RepairUpdate(db.Model):
    __tablename__ = "repair_updates"
    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_requests.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    note = db.Column(db.Text, nullable=False)
    status_after = db.Column(db.String(30))
    parts_used = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow)

    repair = db.relationship("RepairRequest", back_populates="updates")
    user = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(255), default="")
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class AuditLog(db.Model):
    """Append-only: the application never updates or deletes rows here."""
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    target = db.Column(db.String(200), default="")
    details = db.Column(db.Text, default="")
    ip = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    user = db.relationship("User")
