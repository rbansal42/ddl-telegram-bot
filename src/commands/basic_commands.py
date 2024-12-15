# Standard library imports
import os

# Third-party imports
from telebot import TeleBot

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
from telebot.types import BotCommandScopeChat

def register_basic_handlers(bot: TeleBot, db: MongoDB):
    def is_admin(user_id):
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        return user_id in admin_ids

    @bot.message_handler(commands=[CMD_START])
    def start(message):
        try:
            log_action(
                ActionType.COMMAND_START,
                message.from_user.id,
                metadata={
                    'chat_id': message.chat.id,
                    'username': message.from_user.username
                }
            )
            bot.reply_to(message, "👋 Hello! I am your Event Management Bot.\nUse /help to see available commands.")
        except Exception as e:
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'start'}
            )
            bot.reply_to(message, "❌ An error occurred while processing your command.")

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
