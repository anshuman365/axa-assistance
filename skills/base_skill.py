from abc import ABC, abstractmethod
from memory.models import db, ActionLog
from core.permissions import PermissionManager
import json


class BaseSkill(ABC):
    """
    Every skill (Email, Calendar, Files, Browser, etc.) implements this interface.
    This is what makes the system pluggable — add a new skill without touching the core.
    """
    name = "base"
    requires_scope = "read"
    requires_confirmation = False  # critical actions (send/delete/pay) -> True

    def __init__(self, user_id: int):
        self.user_id = user_id

    def check_permission(self) -> bool:
        return PermissionManager.has_permission(self.user_id, self.name, self.requires_scope)

    @abstractmethod
    def execute(self, action: str, params: dict) -> dict:
        """Must return {"status": "success/failed/pending_confirmation", "result": ...}"""
        raise NotImplementedError

    def log_action(self, action: str, params: dict, result: dict, status: str):
        log = ActionLog(
            user_id=self.user_id,
            skill_name=self.name,
            action=action,
            params=json.dumps(params),
            result=json.dumps(result, default=str),
            status=status,
        )
        db.session.add(log)
        db.session.commit()

    def run(self, action: str, params: dict) -> dict:
        """Standard entrypoint — permission check -> confirmation check -> execute -> log"""
        if not self.check_permission():
            result = {"status": "failed", "error": f"No permission for skill '{self.name}'. Please connect it first."}
            self.log_action(action, params, result, "failed")
            return result

        if self.requires_confirmation and not params.get("confirmed"):
            result = {"status": "pending_confirmation", "message": f"Confirm before I {action}: {params}"}
            self.log_action(action, params, result, "pending_confirmation")
            return result

        try:
            result = self.execute(action, params)
            self.log_action(action, params, result, result.get("status", "success"))
            return result
        except Exception as e:
            result = {"status": "failed", "error": str(e)}
            self.log_action(action, params, result, "failed")
            return result
