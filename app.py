from flask import Flask, request, jsonify, render_template, session
from config import Config
from memory.models import db, User, Task, ActionLog
from core.orchestrator import Orchestrator
from core.permissions import PermissionManager
from core.proactive_engine import ProactiveEngine
from google_auth_oauthlib.flow import Flow
import os

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # dev only, remove in production

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

orchestrator = Orchestrator(Config)

# In-memory notification store for demo (replace with WebSocket/push in real app)
pending_notifications = {}


def notify_user(user_id, message):
    pending_notifications.setdefault(user_id, []).append(message)


proactive = ProactiveEngine(app, notify_user)


@app.route("/")
def home():
    return render_template("chat.html")


@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    user = User(username=data["username"], email=data.get("email"))
    db.session.add(user)
    db.session.commit()
    return jsonify({"user_id": user.id, "username": user.username})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_id = data["user_id"]
    message = data["message"]
    result = orchestrator.handle_message(user_id, message)
    return jsonify(result)


@app.route("/api/notifications/<int:user_id>", methods=["GET"])
def get_notifications(user_id):
    notes = pending_notifications.pop(user_id, [])
    return jsonify({"notifications": notes})


@app.route("/api/permissions/<int:user_id>", methods=["GET"])
def list_permissions(user_id):
    return jsonify(PermissionManager.list_permissions(user_id))


@app.route("/api/permissions/revoke", methods=["POST"])
def revoke_permission():
    data = request.json
    PermissionManager.revoke(data["user_id"], data["skill_name"])
    return jsonify({"status": "revoked"})


@app.route("/api/tasks/<int:user_id>", methods=["GET"])
def list_tasks(user_id):
    tasks = Task.query.filter_by(user_id=user_id).all()
    return jsonify([{
        "id": t.id, "title": t.title, "status": t.status,
        "due_date": str(t.due_date) if t.due_date else None,
    } for t in tasks])


@app.route("/api/actions/<int:user_id>", methods=["GET"])
def list_actions(user_id):
    actions = ActionLog.query.filter_by(user_id=user_id).order_by(ActionLog.timestamp.desc()).limit(50).all()
    return jsonify([{
        "skill": a.skill_name, "action": a.action, "status": a.status,
        "timestamp": str(a.timestamp),
    } for a in actions])


# ---- OAuth flow for Google (Email + Calendar) ----

@app.route("/oauth/start/<int:user_id>")
def oauth_start(user_id):
    session["oauth_user_id"] = user_id
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [Config.GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=Config.GOOGLE_SCOPES,
        redirect_uri=Config.GOOGLE_REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return jsonify({"auth_url": auth_url})


@app.route("/oauth/callback")
def oauth_callback():
    user_id = session.get("oauth_user_id")
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [Config.GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=Config.GOOGLE_SCOPES,
        redirect_uri=Config.GOOGLE_REDIRECT_URI,
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    PermissionManager.grant(user_id, "email", "send", creds.token, creds.refresh_token)
    PermissionManager.grant(user_id, "calendar", "write", creds.token, creds.refresh_token)

    return "Google account connected! Email + Calendar access granted. You can close this tab."


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    proactive.start()
    app.run(debug=True, port=10000)
