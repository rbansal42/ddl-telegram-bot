# Standard library imports
import os

# Third-party imports
from telebot import TeleBot, types

# Local application imports
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_admin_or_owner
from src.utils.markup_helpers import create_member_list_markup

def register_member_handlers(bot: TeleBot, db: MongoDB):
    pass  # Member handlers will be added here 