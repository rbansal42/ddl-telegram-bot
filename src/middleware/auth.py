from functools import wraps
from src.database.mongo_db import MongoDB
from src.database.roles import Role

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

def check_owner(bot, db):
    def decorator(func):
        @wraps(func)
        def wrapper(message, *args, **kwargs):
            user_id = message.from_user.id
            user = db.users.find_one({'user_id': user_id})
            
            if not user or user.get('role') != Role.OWNER.name.lower():
                bot.reply_to(message, 
                    "⛔️ This command is only available to the bot owner.")
                return
                
            return func(message, *args, **kwargs)
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