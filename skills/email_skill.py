from skills.base_skill import BaseSkill
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText


class EmailSkill(BaseSkill):
    name = "email"
    requires_scope = "read"

    def _get_service(self):
        token = self._get_oauth_token()
        creds = Credentials(token=token)
        return build("gmail", "v1", credentials=creds)

    def _get_oauth_token(self):
        from core.permissions import PermissionManager
        return PermissionManager.get_token(self.user_id, self.name)

    def execute(self, action: str, params: dict) -> dict:
        if action == "read_unread":
            return self._read_unread(params.get("max_results", 10))
        elif action == "search":
            return self._search(params.get("query", ""), params.get("max_results", 10))
        elif action == "send":
            self.requires_scope = "send"
            return self._send(params["to"], params["subject"], params["body"])
        elif action == "draft_reply":
            return self._draft_reply(params["message_id"], params["body"])
        else:
            return {"status": "failed", "error": f"Unknown email action: {action}"}

    def _read_unread(self, max_results=10):
        service = self._get_service()
        results = service.users().messages().list(
            userId="me", q="is:unread", maxResults=max_results
        ).execute()
        messages = results.get("messages", [])

        output = []
        for msg in messages:
            full = service.users().messages().get(userId="me", id=msg["id"]).execute()
            headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
            output.append({
                "id": msg["id"],
                "from": headers.get("From"),
                "subject": headers.get("Subject"),
                "snippet": full.get("snippet"),
            })
        return {"status": "success", "result": output}

    def _search(self, query, max_results=10):
        service = self._get_service()
        results = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        return {"status": "success", "result": results.get("messages", [])}

    def _send(self, to, subject, body):
        service = self._get_service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"status": "success", "result": {"message_id": sent["id"]}}

    def _draft_reply(self, message_id, body):
        service = self._get_service()
        original = service.users().messages().get(userId="me", id=message_id).execute()
        headers = {h["name"]: h["value"] for h in original["payload"]["headers"]}
        thread_id = original["threadId"]

        message = MIMEText(body)
        message["to"] = headers.get("From")
        message["subject"] = "Re: " + headers.get("Subject", "")
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw, "threadId": thread_id}}
        ).execute()
        return {"status": "success", "result": {"draft_id": draft["id"]}}
