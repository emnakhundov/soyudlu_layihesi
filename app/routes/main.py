from flask import Blueprint, g, redirect, render_template, request, url_for

from ..extensions import db
from ..models import WORKABLE_STATUSES, Notification, RepairRequest, STATUSES

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return redirect(url_for("main.dashboard"))


@bp.route("/dashboard")
def dashboard():
    user = g.current_user
    counts = {s: RepairRequest.query.filter_by(status=s).count() for s in STATUSES}
    my_tasks = (RepairRequest.query
                .filter_by(assignee_id=user.id)
                .filter(RepairRequest.status.in_(WORKABLE_STATUSES))
                .order_by(RepairRequest.id.desc()).all())
    pending = []
    if user.has_permission("repair.approve"):
        pending = RepairRequest.query.filter_by(status="Tamamlandı").order_by(RepairRequest.id).all()
    notes = (Notification.query.filter_by(user_id=user.id)
             .order_by(Notification.created_at.desc()).limit(30).all())
    return render_template("dashboard/index.html", counts=counts, my_tasks=my_tasks,
                           pending=pending, notes=notes)


@bp.route("/notifications/<int:nid>/read", methods=["POST"])
def mark_read(nid):
    note = Notification.query.filter_by(id=nid, user_id=g.current_user.id).first_or_404()
    note.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for("main.dashboard"))
