from enum import Enum, auto
import logging

class Role(Enum):
    OWNER = 4
    ADMIN = 3
    MANAGER = 2
    MEMBER = 1
    PENDING = 0

class Permissions:
    ROLE_PERMISSIONS = {
        Role.OWNER: {
            'can_manage_admins': True,
            'can_manage_managers': True,
            'can_manage_members': True,
            'can_approve_registrations': True,
            'can_view_logs': True,
            'can_manage_events': True,
            'can_delete_events': True,
            'can_view_events': True,
            'can_edit_settings': True
        },
        Role.ADMIN: {
            'can_manage_admins': False,
            'can_manage_managers': True,
            'can_manage_members': True,
            'can_approve_registrations': True,
            'can_view_logs': True,
            'can_manage_events': True,
            'can_delete_events': True,
            'can_view_events': True,
            'can_edit_settings': False
        },
        Role.MANAGER: {
            'can_manage_admins': False,
            'can_manage_managers': False,
            'can_manage_members': True,
            'can_approve_registrations': False,
            'can_view_logs': False,
            'can_manage_events': True,
            'can_delete_events': False,
            'can_view_events': True,
            'can_edit_settings': False
        },
        Role.MEMBER: {
            'can_manage_admins': False,
            'can_manage_managers': False,
            'can_manage_members': False,
            'can_approve_registrations': False,
            'can_view_logs': False,
            'can_manage_events': False,
            'can_delete_events': False,
            'can_view_events': True,
            'can_edit_settings': False
        },
        Role.PENDING: {
            'can_manage_admins': False,
            'can_manage_managers': False,
            'can_manage_members': False,
            'can_approve_registrations': False,
            'can_view_logs': False,
            'can_manage_events': False,
            'can_delete_events': False,
            'can_view_events': False,
            'can_edit_settings': False
        }
    }

    @staticmethod
    def has_permission(role: Role, permission: str) -> bool:
        return Permissions.ROLE_PERMISSIONS.get(role, {}).get(permission, False) 

def remove_user_from_database(user_id: int) -> bool:
    try:
        from src.database.mongo_db import MongoDB
        db = MongoDB()
        result = db.users.delete_one({'user_id': user_id})
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"Error removing user from database: {e}")
        return False 

def is_owner(user_id: int) -> bool:
    try:
        from src.database.mongo_db import MongoDB
        db = MongoDB()
        user = db.users.find_one({'user_id': user_id})
        return user is not None and user.get('role') == Role.OWNER.name.lower()
    except Exception as e:
        logging.error(f"Error checking owner status: {e}")
        return False 