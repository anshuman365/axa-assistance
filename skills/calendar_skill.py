from skills.base_skill import BaseSkill
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta


class CalendarSkill(BaseSkill):
    name = "calendar"
    requires_scope = "read"

    def _get_service(self):
        from core.permissions import PermissionManager
        token = PermissionManager.get_token(self.user_id, self.name)
        creds = Credentials(token=token)
        return build("calendar", "v3", credentials=creds)

    def execute(self, action: str, params: dict) -> dict:
        if action == "list_upcoming":
            return self._list_upcoming(params.get("max_results", 10))
        elif action == "create_event":
            self.requires_scope = "write"
            return self._create_event(params)
        elif action == "delete_event":
            self.requires_scope = "write"
            self.requires_confirmation = True
            return self._delete_event(params["event_id"])
        else:
            return {"status": "failed", "error": f"Unknown calendar action: {action}"}

    def _list_upcoming(self, max_results=10):
        service = self._get_service()
        now = datetime.utcnow().isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary", timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])

        output = [{
            "id": e["id"],
            "summary": e.get("summary"),
            "start": e["start"].get("dateTime", e["start"].get("date")),
        } for e in events]
        return {"status": "success", "result": output}

    def _create_event(self, params):
        service = self._get_service()
        event = {
            "summary": params["title"],
            "description": params.get("description", ""),
            "start": {"dateTime": params["start_time"], "timeZone": params.get("timezone", "Asia/Kolkata")},
            "end": {"dateTime": params["end_time"], "timeZone": params.get("timezone", "Asia/Kolkata")},
        }
        if params.get("attendees"):
            event["attendees"] = [{"email": a} for a in params["attendees"]]

        created = service.events().insert(calendarId="primary", body=event).execute()
        return {"status": "success", "result": {"event_id": created["id"], "link": created.get("htmlLink")}}

    def _delete_event(self, event_id):
        service = self._get_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"status": "success", "result": {"deleted": event_id}}
