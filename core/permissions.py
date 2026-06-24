from memory.models import db, Permission
from datetime import datetime


class PermissionManager:
    """
    Every skill must check_permission() before acting.
    Permissions are explicit, scoped, and revocable.
    """

    @staticmethod
    def has_permission(user_id: int, skill_name: str, required_scope: str = "read") -> bool:
        perm = Permission.query.filter_by(
            user_id=user_id, skill_name=skill_name, granted=True
        ).first()
        if not perm:
            return False

        scope_rank = {"read": 1, "write": 2, "send": 3}
        return scope_rank.get(perm.scope, 0) >= scope_rank.get(required_scope, 0)

    @staticmethod
    def grant(user_id: int, skill_name: str, scope: str, oauth_token: str = None, refresh_token: str = None):
        perm = Permission.query.filter_by(user_id=user_id, skill_name=skill_name).first()
        if not perm:
            perm = Permission(user_id=user_id, skill_name=skill_name)
            db.session.add(perm)

        perm.scope = scope
        perm.granted = True
        perm.granted_at = datetime.utcnow()
        if oauth_token:
            perm.oauth_token = oauth_token
        if refresh_token:
            perm.oauth_refresh_token = refresh_token

        db.session.commit()
        return perm

    @staticmethod
    def revoke(user_id: int, skill_name: str):
        perm = Permission.query.filter_by(user_id=user_id, skill_name=skill_name).first()
        if perm:
            perm.granted = False
            perm.oauth_token = None
            perm.oauth_refresh_token = None
            db.session.commit()
        return True

    @staticmethod
    def get_token(user_id: int, skill_name: str):
        perm = Permission.query.filter_by(
            user_id=user_id, skill_name=skill_name, granted=True
        ).first()
        return perm.oauth_token if perm else None

    @staticmethod
    def list_permissions(user_id: int):
        perms = Permission.query.filter_by(user_id=user_id).all()
        return [
            {"skill": p.skill_name, "scope": p.scope, "granted": p.granted, "granted_at": str(p.granted_at)}
            for p in perms
        ]
