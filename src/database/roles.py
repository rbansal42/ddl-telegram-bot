from enum import Enum, auto

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