from functools import wraps
from src.database.db import BotDB

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