# Standard library imports
import os
import signal
import sys

# Third-party imports
from dotenv import load_dotenv
import telebot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from telebot.types import BotCommand, BotCommandScopeChat
from telebot import TeleBot, apihelper

# Local application imports
from src.commands.admin_commands import register_member_management_handlers
from src.commands.basic_commands import register_basic_handlers
from src.commands.constants import BOT_COMMANDS
from src.commands.owner.drive_management import register_drive_handlers
from src.commands.fun_commands import register_fun_handlers
from src.commands.member_commands import register_member_handlers
from src.commands.owner.admin_management import register_admin_handlers
from src.commands.owner_commands import register_owner_handlers
from src.commands.registration_commands import register_registration_handlers
from src.services.service_container import ServiceContainer
from src.utils.command_helpers import get_commands_for_role
from src.utils.state_management import UserStateManager
from src.commands.drive.events.upload_items import register_upload_handlers
from src.commands.drive.events.add_event import register_event_handlers

# Initialize services and bot
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

state_storage = StateMemoryStorage()
services = ServiceContainer()
bot = TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"), threaded=True, state_storage=state_storage)
bot.set_my_commands(BOT_COMMANDS)  # Only show public commands by default

# Initialize state manager before registering handlers
state_manager = UserStateManager()

# Register all command handlers with services
register_basic_handlers(bot, services.db)
register_fun_handlers(bot)
register_registration_handlers(bot, services.db)
register_owner_handlers(bot, services.db, services.drive_service)
register_member_management_handlers(bot, services.db)
register_member_handlers(bot, services.db)

# Register drive handlers with state manager
event_handlers = register_event_handlers(bot, services.db, services.drive_service, state_manager)
upload_handlers = register_upload_handlers(bot, services.db, services.drive_service, state_manager)
register_drive_handlers(bot, services.db, services.drive_service)
register_admin_handlers(bot, services.db)

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    print('\n🛑 Stopping the bot...')
    services.close()
    bot.stop_polling()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGHUP, signal_handler)

if __name__ == '__main__':
    print('🤖 Bot started. Press Ctrl+C to stop.')
    bot.infinity_polling()
