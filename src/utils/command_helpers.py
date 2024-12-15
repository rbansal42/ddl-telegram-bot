from typing import List
from telebot.types import BotCommand
from src.database.roles import Role
from src.commands.constants import (
    PUBLIC_COMMANDS,
    MEMBER_COMMANDS,
    ADMIN_COMMANDS,
    OWNER_COMMANDS
)

def get_commands_for_role(role: str) -> List[BotCommand]:
    """Get the appropriate command list based on user role"""
    if role == Role.OWNER.name.lower():
        return OWNER_COMMANDS
    elif role == Role.ADMIN.name.lower():
        return ADMIN_COMMANDS
    elif role == Role.MEMBER.name.lower():
        return MEMBER_COMMANDS
    else:
        return PUBLIC_COMMANDS