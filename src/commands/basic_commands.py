import os
from telebot import TeleBot
from src.database.db import BotDB
from src.commands.constants import (
    CMD_START, CMD_HELP, BOT_COMMANDS, CMD_REGISTER, CMD_MYID
)

def register_basic_handlers(bot: TeleBot, db: BotDB):
    def is_admin(user_id):
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        return user_id in admin_ids

    @bot.message_handler(commands=[CMD_START])
    def start(message):
        bot.reply_to(message, "👋 Hello! I am your Event Management Bot.\nUse /help to see available commands.")

    @bot.message_handler(commands=[CMD_HELP])
    def help_command(message):
        # Get user's registration status
        is_registered = db.is_user_registered(message.from_user.id)

        # Get all commands from BOT_COMMANDS
        commands = BOT_COMMANDS

        if is_registered:
            # Show all commands
            help_text = "📚 *Available Commands:*\n"
            for command in commands:
                help_text += f"/{command.command} - {command.description}\n"
        else:
            # Filter out commands that require registration
            public_commands = ['/start', '/help', '/register', '/myid']
            help_text = "📚 *Available Commands:*\n"
            for command in commands:
                if f"/{command.command}" in public_commands:
                    help_text += f"/{command.command} - {command.description}\n"
            
            help_text += "\n*Note:* Additional commands will be available after your registration is approved."

        bot.reply_to(message, help_text, parse_mode="Markdown")

    @bot.message_handler(commands=[CMD_MYID])
    def get_user_id(message):
        bot.reply_to(message, f"Your Telegram ID is: {message.from_user.id}")
