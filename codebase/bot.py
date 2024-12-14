import os
import telebot
import signal
import sys
from dotenv import load_dotenv
from src.commands.basic_commands import register_basic_handlers
from src.commands.fun_commands import register_fun_handlers
from src.commands.google_drive_commands import register_google_drive_handlers
from src.commands.registration_commands import register_registration_handlers
from telebot.handler_backends import State, StatesGroup
from telebot.types import BotCommand
from src.commands import BOT_COMMANDS, BotStates
from src.database.db import BotDB
from telebot.storage import StateMemoryStorage

# Specify the path to the .env file if it's not in the current directory
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

state_storage = StateMemoryStorage()

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"), state_storage=state_storage)
bot.set_my_commands(BOT_COMMANDS)  # Register commands with Telegram

# Initialize the database
db = BotDB()

# Register all command handlers
register_basic_handlers(bot, db=db)
register_fun_handlers(bot)
register_google_drive_handlers(bot)
register_registration_handlers(bot)

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    print('\n🛑 Stopping the bot...')
    db.close()  # Close all database connections
    bot.stop_polling()
    sys.exit(0)

# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)   # Handles Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Handles termination signal
signal.signal(signal.SIGHUP, signal_handler)    # Handles hangup signal

# Update help command text
help_text = "📚 *Available Commands:*\n"
for command in BOT_COMMANDS:
    help_text += f"/{command.command} - {command.description}\n"
help_text += "\n*Note:* Other commands will be available after your registration is approved."

@bot.message_handler(commands=['help'])
def update_help(message):
    bot.reply_to(message, help_text, parse_mode="Markdown")

if __name__ == '__main__':
    print('🤖 Bot started. Press Ctrl+C to stop.')
    bot.infinity_polling()
