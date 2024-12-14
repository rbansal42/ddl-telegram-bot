import os
import telebot
from telebot import TeleBot
from commands import (
    CMD_START, CMD_HELP, CMD_SET_PHOTO, CMD_MYID, BOT_COMMANDS
)
from src.database.db import BotDB

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
            public_commands = ['/start', '/help', '/register', '/myid', '/cat', '/dog', '/space', '/meme', '/funny']
            help_text = "📚 *Available Commands:*\n"
            for command in commands:
                if f"/{command.command}" in public_commands:
                    help_text += f"/{command.command} - {command.description}\n"
            
            help_text += "\n*Note:* Additional commands will be available after your registration is approved."

        bot.reply_to(message, help_text, parse_mode="Markdown")

    @bot.message_handler(commands=[CMD_SET_PHOTO])
    def set_bot_photo(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "Sorry, only administrators can change the bot's profile picture.")
            return
        bot.reply_to(message, "Please send me the new profile picture. The photo should be in JPEG format and less than 5MB.")
        bot.register_next_step_handler(message, handle_photo)

    def handle_photo(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "Sorry, only administrators can change the bot's profile picture.")
            return
        try:
            file_id = message.photo[-1].file_id
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            bot.set_chat_photo(message.chat.id, downloaded_file)
            bot.reply_to(message, "Profile picture updated successfully! ✅")
        except telebot.apihelper.ApiException as e:
            if "file is too big" in str(e):
                bot.reply_to(message, "The photo is too large. Please send a photo smaller than 5MB.")
            elif "wrong file type" in str(e):
                bot.reply_to(message, "The photo must be in JPEG format.")
            else:
                bot.reply_to(message, "Sorry, I couldn't update the profile picture. Make sure you have the right permissions.")

    @bot.message_handler(commands=[CMD_MYID])
    def get_user_id(message):
        bot.reply_to(message, f"Your Telegram ID is: {message.from_user.id}")
