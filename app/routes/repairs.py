import csv
import io

from flask import (Blueprint, Response, abort, flash, g, redirect, render_template,
                   request, url_for)

from ..extensions import db
from ..models import (FINAL_STATUSES, PRIORITIES, STATUSES, WORKABLE_STATUSES,
                      Notification, RepairRequest, RepairUpdate, User, Vehicle)
from ..security import audit, permission_required, to_int, utcnow

bp = Blueprint("repairs", __name__, url_prefix="/repairs")


def _users_with(code):
    users = User.query.filter_by(is_active=True, is_deleted=False).all()
    return [u for u in users if u.has_permission(code)]


def _notify(users, message, link, exclude_id=None):
    """Internal notification center. SMTP / Teams delivery can hook in here."""
    for user in users:
        if user is None or user.id == exclude_id:
            continue
        db.session.add(Notification(user_id=user.id, message=message[:500], link=link))


def _load(rid):
    return db.get_or_404(RepairRequest, rid)


def _back(r):
    return redirect(url_for("repairs.detail", rid=r.id))


def _can_work(r):
    return r.assignee_id == g.current_user.id or g.current_user.has_permission("repair.assign")


@bp.route("/")
@permission_required("repair.view")
def index():
    status = request.args.get("status", "")
    query = RepairRequest.query
    if status in STATUSES:
        query = query.filter_by(status=status)
    repairs = query.order_by(RepairRequest.id.desc()).all()
    vehicles = Vehicle.query.order_by(Vehicle.plate).all()
    return render_template("repairs/index.html", repairs=repairs, vehicles=vehicles,
                           statuses=STATUSES, priorities=PRIORITIES, selected=status)


@bp.route("/new", methods=["POST"])
@permission_required("repair.create")
def create():
    f = request.form
    vehicle = db.session.get(Vehicle, to_int(f.get("vehicle_id"), 0))
    title = f.get("title", "").strip()
    priority = f.get("priority", "Normal")
    if vehicle is None or not title:
        flash("Avtomobil və nasazlıq başlığı mütləqdir.", "error")
        return redirect(url_for("repairs.index"))
    if priority not in PRIORITIES:
        priority = "Normal"

    r = RepairRequest(vehicle_id=vehicle.id, title=title,
                      description=f.get("description", "").strip(),
                      priority=priority, status="Yeni",
                      created_by_id=g.current_user.id)
    db.session.add(r)
    db.session.flush()
    r.number = f"ESD-{utcnow().year}-{r.id:04d}"
    link = url_for("repairs.detail", rid=r.id)
    _notify(_users_with("repair.assign"),
            f"Yeni müraciət {r.number}: {vehicle.plate} – {title}", link)
    audit("repair.created", r.number, f"vehicle={vehicle.plate}")
    db.session.commit()
    flash(f"Müraciət {r.number} yaradıldı.", "success")
    return redirect(link)


@bp.route("/<int:rid>")
@permission_required("repair.view")
def detail(rid):
    r = _load(rid)
    assignees = _users_with("repair.update")
    return render_template("repairs/detail.html", r=r, assignees=assignees,
                           workable=WORKABLE_STATUSES, final=FINAL_STATUSES)


@bp.route("/<int:rid>/assign", methods=["POST"])
@permission_required("repair.assign")
def assign(rid):
    r = _load(rid)
    if r.status in FINAL_STATUSES:
        flash("Bağlanmış müraciət təyin edilə bilməz.", "error")
        return _back(r)
    assignee = db.session.get(User, to_int(request.form.get("assignee_id"), 0))
    if assignee is None or not assignee.has_permission("repair.update"):
        flash("Seçilmiş icraçı düzgün deyil.", "error")
        return _back(r)

    r.assignee_id = assignee.id
    r.assignment_notes = request.form.get("notes", "").strip()
    r.status = "Təyin edildi"
    _notify([assignee], f"{r.number} sizə təyin edildi", url_for("repairs.detail", rid=r.id))
    audit("repair.assigned", r.number, f"assignee={assignee.username}")
    db.session.commit()
    flash("İcraçı təyin edildi.", "success")
    return _back(r)


@bp.route("/<int:rid>/update", methods=["POST"])
@permission_required("repair.update")
def update(rid):
    r = _load(rid)
    if r.status not in WORKABLE_STATUSES:
        flash("Bu mərhələdə iş yenilənə bilməz.", "error")
        return _back(r)
    if not _can_work(r):
        abort(403)

    note = request.form.get("note", "").strip()
    if not note:
        flash("İş qeydi mütləqdir.", "error")
        return _back(r)
    new_status = request.form.get("status", "Təmirdə")
    if new_status not in ("Təmirdə", "Gözləmədə"):
        new_status = "Təmirdə"

    db.session.add(RepairUpdate(repair_id=r.id, user_id=g.current_user.id, note=note,
                                status_after=new_status,
                                parts_used=request.form.get("parts_used", "").strip()))
    r.status = new_status
    _notify([r.created_by], f"{r.number}: {note[:120]}", url_for("repairs.detail", rid=r.id),
            exclude_id=g.current_user.id)
    audit("repair.updated", r.number, new_status)
    db.session.commit()
    return _back(r)


@bp.route("/<int:rid>/complete", methods=["POST"])
@permission_required("repair.update")
def complete(rid):
    r = _load(rid)
    if r.status not in WORKABLE_STATUSES or r.assignee_id != g.current_user.id:
        abort(403)

    r.status = "Tamamlandı"
    r.completed_at = utcnow()
    r.completion_notes = request.form.get("completion_notes", "").strip()
    link = url_for("repairs.detail", rid=r.id)
    _notify(_users_with("repair.approve") + [r.created_by],
            f"{r.number} tamamlandı, təsdiq gözləyir", link, exclude_id=g.current_user.id)
    audit("repair.completed", r.number)
    db.session.commit()
    flash("İş tamamlandı və təsdiqə göndərildi.", "success")
    return _back(r)


@bp.route("/<int:rid>/approve", methods=["POST"])
@permission_required("repair.approve")
def approve(rid):
    r = _load(rid)
    if r.status != "Tamamlandı":
        flash("Yalnız tamamlanmış iş təsdiqlənə bilər.", "error")
        return _back(r)

    r.status = "Təsdiqləndi"
    r.approved_at = utcnow()
    _notify([r.created_by, r.assignee], f"{r.number} təsdiqləndi",
            url_for("repairs.detail", rid=r.id), exclude_id=g.current_user.id)
    audit("repair.approved", r.number)
    db.session.commit()
    flash("İş təsdiqləndi.", "success")
    return _back(r)


@bp.route("/<int:rid>/reject", methods=["POST"])
@permission_required("repair.approve")
def reject(rid):
    r = _load(rid)
    reason = request.form.get("reason", "").strip()
    if r.status != "Tamamlandı" or not reason:
        flash("Rədd üçün iş tamamlanmış olmalı və səbəb yazılmalıdır.", "error")
        return _back(r)

    r.status = "Təmirdə"
    r.reject_reason = reason
    r.completed_at = None
    _notify([r.assignee, r.created_by], f"{r.number} rədd edildi: {reason}",
            url_for("repairs.detail", rid=r.id), exclude_id=g.current_user.id)
    audit("repair.rejected", r.number, reason)
    db.session.commit()
    flash("İş icraya qaytarıldı.", "info")
    return _back(r)


@bp.route("/export.csv")
@permission_required("report.view")
def export_csv():
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Nömrə", "Avtomobil", "Başlıq", "Prioritet", "Status",
                     "İcraçı", "Yaradan", "Yaradılma", "Tamamlanma", "Təsdiq"])
    for r in RepairRequest.query.order_by(RepairRequest.id).all():
        writer.writerow([
            r.number, r.vehicle.plate, r.title, r.priority, r.status,
            r.assignee.username if r.assignee else "",
            r.created_by.username,
            r.created_at.strftime("%d.%m.%Y %H:%M") if r.created_at else "",
            r.completed_at.strftime("%d.%m.%Y %H:%M") if r.completed_at else "",
            r.approved_at.strftime("%d.%m.%Y %H:%M") if r.approved_at else "",
        ])
    audit("report.export", "repairs.csv")
    db.session.commit()
    return Response(
        "\ufeff" + buffer.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=repairs.csv"},
    )
