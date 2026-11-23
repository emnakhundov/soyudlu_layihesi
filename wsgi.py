from app import create_app
from app.extensions import db
from app.seed import seed

app = create_app()

# Creates tables and the initial admin account (idempotent).
with app.app_context():
    db.create_all()
    seed()
