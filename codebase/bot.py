import os
import telebot
import signal
import sys
from dotenv import load_dotenv
from commands.basic_commands import register_basic_handlers
from commands.cat_command import register_cat_handlers
from commands.event_commands import register_event_handlers
from commands.file_commands import register_file_handlers
from commands.fun_commands import register_fun_handlers
from commands.google_drive_commands import register_google_drive_handlers  # Import the new handler
from telebot.handler_backends import State, StatesGroup
from telebot.types import BotCommand
from commands import BOT_COMMANDS  # Import from commands.py
from database.db import BotDB
from commands.registration_commands import register_registration_handlers

# Specify the path to the .env file if it's not in the current directory
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))
bot.set_my_commands(BOT_COMMANDS)  # Register commands with Telegram

class BotStates(StatesGroup):
    # States for handling file operations
    waiting_for_file = State()
    waiting_for_event_name = State()
    waiting_for_delete_confirmation = State()
    waiting_for_gdrive_url = State()  # New state for gdrive
    # Additional states can be added here if needed

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    print('\nStopping the bot...')
    db.close()  # Close database connection
    bot.stop_polling()
    sys.exit(0)

# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)  # Handles Ctrl+C
signal.signal(signal.SIGTERM, signal_handler) # Handles termination signal

# Register all command handlers
register_basic_handlers(bot)
register_cat_handlers(bot)
register_event_handlers(bot)
register_file_handlers(bot)
register_fun_handlers(bot)
register_google_drive_handlers(bot)  # Register the new Google Drive handlers
register_registration_handlers(bot)

# After bot initialization
db = BotDB()

if __name__ == '__main__':
    print('Bot started. Press Ctrl+C to stop')
    bot.infinity_polling()
