# Standard library imports
import os
from functools import wraps
from typing import Callable, Optional

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Local application imports
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.utils.user_actions import log_action, ActionType

def check_registration(bot, db):
    def decorator(func):
        @wraps(func)
        def wrapper(message, *args, **kwargs):
            # Commands that don't require registration
            public_commands = ['/start', '/help', '/register', '/myid']
            
            # Check if this is a public command
            if any(message.text.startswith(cmd) for cmd in public_commands):
                return func(message, *args, **kwargs)

            # Check if user is registered
            user_id = message.from_user.id
            if not db.is_user_registered(user_id):
                bot.reply_to(message, 
                    "⚠️ You need to register first to use this bot.\n"
                    "Use /register to start the registration process.")
                return
            
            return func(message, *args, **kwargs)
        return wrapper
    return decorator 

def check_owner(bot: TeleBot, db: MongoDB):
    """
    Decorator to ensure that only the bot owner can execute the decorated handler.
    
    It handles both message handlers and callback query handlers by determining
    the type of the first argument and extracting the user ID accordingly.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not args:
                return

            # Determine the type of the first argument
            first_arg = args[0]
            if isinstance(first_arg, Message):
                user_id = first_arg.from_user.id
                is_callback = False
            elif isinstance(first_arg, CallbackQuery):
                user_id = first_arg.from_user.id
                is_callback = True
            else:
                # Unsupported handler type
                return

            # Retrieve the owner ID from environment variables
            owner_id = 940075808
            if owner_id is None:
                # Owner ID not set; optionally, you can log this as an error
                if is_callback:
                    bot.answer_callback_query(first_arg.id, "❌ Owner ID is not configured.")
                else:
                    bot.reply_to(first_arg, "❌ Owner ID is not configured.")
                return

            try:
                owner_id = int(owner_id)
            except ValueError:
                # Invalid owner ID format
                if is_callback:
                    bot.answer_callback_query(first_arg.id, "❌ Invalid owner ID configuration.")
                else:
                    bot.reply_to(first_arg, "❌ Invalid owner ID configuration.")
                return

            if user_id != owner_id:
                # User is not the owner; deny access
                if is_callback:
                    bot.answer_callback_query(first_arg.id, "⛔️ This command is only available to the bot owner.")
                else:
                    bot.reply_to(first_arg, "⛔️ This command is only available to the bot owner.")
                return

            # User is the owner; proceed to execute the handler
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

def check_admin_or_owner(bot, db):
    def decorator(func):
        @wraps(func)
        def wrapper(message, *args, **kwargs):
            user_id = message.from_user.id
            user = db.users.find_one({'user_id': user_id})
            
            if not user or (
                user.get('role') != Role.ADMIN.name.lower() and 
                user.get('role') != Role.OWNER.name.lower()
            ):
                bot.reply_to(message, 
                    "⛔️ This command is only available to admins and owner.")
                return
                
            return func(message, *args, **kwargs)
        return wrapper
    return decorator

def is_admin(user_id: int) -> bool:
    """Check if a user ID belongs to an admin or owner"""
    try:
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        owner_id = os.getenv("OWNER_ID")
        
        # Convert admin IDs string to list of integers
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        
        # Add owner ID to admin list if configured
        if owner_id:
            admin_ids.append(int(owner_id))
            
        return user_id in admin_ids
        
    except ValueError:
        # Handle invalid ID format
        return False

def check_event_permission(bot, db):
    def decorator(func):
        @wraps(func)
        def wrapper(message, *args, **kwargs):
            user_id = message.from_user.id
            user = db.users.find_one({'user_id': user_id})
            
            if not user or not Permissions.has_permission(
                Role[user.get('role', '').upper()], 
                'can_manage_events'
            ):
                bot.reply_to(message, 
                    "⛔️ You don't have permission to manage events.")
                return
                
            return func(message, *args, **kwargs)
        return wrapper
    return decorator