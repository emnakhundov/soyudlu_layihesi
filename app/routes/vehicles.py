from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import RepairRequest, Vehicle
from ..security import audit, permission_required, to_int

bp = Blueprint("vehicles", __name__, url_prefix="/vehicles")


@bp.route("/")
@permission_required("vehicle.view")
def index():
    vehicles = Vehicle.query.order_by(Vehicle.plate).all()
    return render_template("vehicles/index.html", vehicles=vehicles)


@bp.route("/new", methods=["POST"])
@permission_required("vehicle.manage")
def create():
    f = request.form
    plate = f.get("plate", "").strip().upper()
    if not plate:
        flash("Qeydiyyat nişanı mütləqdir.", "error")
        return redirect(url_for("vehicles.index"))
    if Vehicle.query.filter_by(plate=plate).first():
        flash("Bu qeydiyyat nişanı artıq mövcuddur.", "error")
        return redirect(url_for("vehicles.index"))

    vehicle = Vehicle(
        plate=plate,
        make=f.get("make", "").strip(),
        model=f.get("model", "").strip(),
        year=to_int(f.get("year")),
        mileage=to_int(f.get("mileage"), 0),
        department=f.get("department", "").strip(),
    )
    db.session.add(vehicle)
    db.session.flush()
    audit("vehicle.created", plate)
    db.session.commit()
    flash("Avtomobil əlavə olundu.", "success")
    return redirect(url_for("vehicles.detail", vid=vehicle.id))


@bp.route("/<int:vid>")
@permission_required("vehicle.view")
def detail(vid):
    vehicle = db.get_or_404(Vehicle, vid)
    repairs = (RepairRequest.query.filter_by(vehicle_id=vid)
               .order_by(RepairRequest.id.desc()).all())
    return render_template("vehicles/detail.html", v=vehicle, repairs=repairs)
