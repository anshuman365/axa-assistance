from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    permissions = db.relationship("Permission", backref="user", lazy=True)
    tasks = db.relationship("Task", backref="user", lazy=True)
    memories = db.relationship("MemoryLog", backref="user", lazy=True)
    actions = db.relationship("ActionLog", backref="user", lazy=True)


class Permission(db.Model):
    """Granular permission per skill/service"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    skill_name = db.Column(db.String(80), nullable=False)   # "email", "calendar", etc.
    scope = db.Column(db.String(40), default="read")          # read / write / send
    granted = db.Column(db.Boolean, default=False)
    granted_at = db.Column(db.DateTime, nullable=True)
    oauth_token = db.Column(db.Text, nullable=True)           # encrypt in real prod
    oauth_refresh_token = db.Column(db.Text, nullable=True)


class MemoryLog(db.Model):
    """Episodic + semantic memory metadata (vectors live in ChromaDB)"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    memory_type = db.Column(db.String(40))    # episodic / fact / preference / entity
    content = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(80))         # chat / email / voice_note
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vector_id = db.Column(db.String(80))


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")  # pending/done/overdue
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_progress_at = db.Column(db.DateTime, nullable=True)
    source = db.Column(db.String(80))  # chat / voice_note / email_extracted


class ActionLog(db.Model):
    """Every action Axa takes — full audit trail"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    skill_name = db.Column(db.String(80))
    action = db.Column(db.String(255))
    params = db.Column(db.Text)
    result = db.Column(db.Text)
    status = db.Column(db.String(20))  # success/failed/pending_confirmation
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
