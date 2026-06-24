from apscheduler.schedulers.background import BackgroundScheduler
from memory.models import db, Task, User
from datetime import datetime, timedelta


class ProactiveEngine:
    """
    Background checks -> generates proactive nudges.
    Reddit demand #3: 'AI khud initiate kare'
    """

    def __init__(self, app, notify_callback):
        self.app = app
        self.notify_callback = notify_callback  # function(user_id, message)
        self.scheduler = BackgroundScheduler()

    def start(self):
        self.scheduler.add_job(self.check_overdue_tasks, "interval", minutes=30)
        self.scheduler.add_job(self.check_stale_tasks, "interval", hours=12)
        self.scheduler.add_job(self.check_upcoming_deadlines, "interval", minutes=15)
        self.scheduler.start()

    def check_overdue_tasks(self):
        with self.app.app_context():
            now = datetime.utcnow()
            overdue = Task.query.filter(
                Task.status == "pending", Task.due_date < now
            ).all()
            for task in overdue:
                task.status = "overdue"
                self.notify_callback(task.user_id, f"⚠️ Task overdue: '{task.title}'")
            db.session.commit()

    def check_stale_tasks(self):
        """Tasks with no progress in 3+ days"""
        with self.app.app_context():
            threshold = datetime.utcnow() - timedelta(days=3)
            stale = Task.query.filter(
                Task.status == "pending",
                (Task.last_progress_at == None) | (Task.last_progress_at < threshold),
                Task.created_at < threshold,
            ).all()
            for task in stale:
                self.notify_callback(
                    task.user_id,
                    f"👀 Tumne '{task.title}' par 3 din se kaam nahi kiya. Continue karna hai?"
                )

    def check_upcoming_deadlines(self):
        with self.app.app_context():
            now = datetime.utcnow()
            soon = now + timedelta(minutes=30)
            upcoming = Task.query.filter(
                Task.status == "pending",
                Task.due_date >= now,
                Task.due_date <= soon,
            ).all()
            for task in upcoming:
                self.notify_callback(task.user_id, f"⏰ '{task.title}' 30 min me due hai.")
