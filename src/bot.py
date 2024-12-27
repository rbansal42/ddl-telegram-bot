# Standard library imports
import os
import signal
import sys
import logging
import atexit

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
from src.commands.drive.events.upload_items import register_upload_handlers
from src.commands.drive.events.add_event import register_event_handlers
from src.commands.drive.media_copy import register_media_copy_handlers
from src.services.service_container import ServiceContainer
from src.utils.command_helpers import get_commands_for_role
from src.utils.state_management import UserStateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize services and bot
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

state_storage = StateMemoryStorage()
services = ServiceContainer()
bot = TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"), threaded=True, state_storage=state_storage)

# Set public commands globally for all users
bot.delete_my_commands()  # Clear any existing commands
bot.set_my_commands(BOT_COMMANDS)  # Set public commands globally

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
register_media_copy_handlers(bot, services.db, services.drive_service, state_manager)

def cleanup_resources():
    """Cleanup function to be called on shutdown"""
    try:
        logger.info("Cleaning up resources...")
        services.close()
        logger.info("Resources cleaned up successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    signal_name = signal.Signals(signum).name
    logger.info(f'\n🛑 Received signal {signal_name} ({signum})')
    logger.info('Initiating graceful shutdown...')
    
    try:
        # Stop accepting new requests
        bot.stop_polling()
        logger.info("Stopped accepting new requests")
        
        # Cleanup resources
        cleanup_resources()
        
        # Exit gracefully
        logger.info("Shutdown completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        sys.exit(1)

# Register cleanup function
atexit.register(cleanup_resources)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination
signal.signal(signal.SIGHUP, signal_handler)   # Terminal closed

if __name__ == '__main__':
    try:
        logger.info('🤖 Bot started. Press Ctrl+C to stop.')
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        sys.exit(1)
