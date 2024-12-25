# Standard library imports
import os

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, BotCommand, BotCommandScopeChat

# Local application imports
from src.commands.constants import (
    CMD_START, 
    CMD_HELP, 
    PUBLIC_COMMANDS,
    CMD_MYID   
)

from src.database.mongo_db import MongoDB
from src.utils.user_actions import log_action, ActionType
from src.utils.command_helpers import get_commands_for_role

def register_basic_handlers(bot: TeleBot, db: MongoDB):
    def is_admin(user_id):
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        return user_id in admin_ids

    @bot.message_handler(commands=[CMD_START])
    def start(message: Message):
        """Handle the /start command"""
        user_id = message.from_user.id
        user = db.users.find_one({'user_id': user_id})
        
        if user:
            # Update command menu based on user's role
            commands = get_commands_for_role(user['role'].lower())
            bot.set_my_commands(commands, scope=BotCommandScopeChat(user_id))
            bot.reply_to(message, f"Welcome back! You are registered as a {user['role']}.\nUse /help to see available commands.")
        else:
            bot.set_my_commands(get_commands_for_role("public"), scope=BotCommandScopeChat(user_id))
            bot.reply_to(message, "Welcome! Please use /register to request access to the bot.")

    @bot.message_handler(commands=[CMD_HELP])
    def help_command(message):
        try:
            user_id = message.from_user.id
            is_registered = db.is_user_registered(user_id)
            user = db.users.find_one({'user_id': user_id})

            if is_registered and user and user.get('registration_status') == 'approved':
                role = user.get('role', 'unregistered')
                commands = get_commands_for_role(role)
                
                # Update bot commands for this user
                bot.set_my_commands(commands, scope=BotCommandScopeChat(message.chat.id))
                
                help_text = "📚 *Available Commands:*\n"
                for command in commands:
                    help_text += f"/{command.command} - {command.description}\n"
            else:
                # Show only public commands
                help_text = "📚 *Available Commands:*\n"
                for command in PUBLIC_COMMANDS:
                    help_text += f"/{command.command} - {command.description}\n"
                help_text += "\n*Note:* Additional commands will be available after your registration is approved."

            log_action(
                ActionType.COMMAND_HELP,
                message.from_user.id,
                metadata={
                    'is_registered': is_registered,
                    'chat_id': message.chat.id
                }
            )
            bot.reply_to(message, help_text, parse_mode="Markdown")
            
        except Exception as e:
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'help'}
            )
            bot.reply_to(message, "❌ An error occurred while processing your command.")

    @bot.message_handler(commands=[CMD_MYID])
    def get_user_id(message):
        bot.reply_to(message, f"Your Telegram ID is: {message.from_user.id}")
