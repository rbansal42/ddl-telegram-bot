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

# Specify the path to the .env file if it's not in the current directory
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

state_storage = StateMemoryStorage()

# Configure timeouts
apihelper.CONNECT_TIMEOUT = 30
apihelper.READ_TIMEOUT = 30

# Initialize services
services = ServiceContainer()

# Initialize bot with custom timeout settings
bot = TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"), threaded=True, state_storage=state_storage)
bot.set_my_commands(BOT_COMMANDS)  # Only show public commands by default

# Register all command handlers with services
register_basic_handlers(bot, services.db)
register_fun_handlers(bot)
register_registration_handlers(bot, services.db)
register_owner_handlers(bot, services.db, services.drive_service)
register_member_management_handlers(bot, services.db)
register_member_handlers(bot, services.db)
register_drive_handlers(bot, services.db, services.drive_service)
register_admin_handlers(bot, services.db)
# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    print('\n🛑 Stopping the bot...')
    services.close()  # Close all services
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
    """Update command menu based on user role"""
    print(f"========================== [DEBUG] Help command triggered ==========================")
    try:
        user_id = message.from_user.id
        print(f"[DEBUG] Processing help command for user ID: {user_id}")
        
        user = services.db.users.find_one({'user_id': user_id})
        print(f"[DEBUG] User data: {user}")
        
        if user and user.get('registration_status') == 'approved':
            role = user.get('role', 'unregistered')
            print(f"[DEBUG] User role: {role}")
            
            commands = get_commands_for_role(role)
            print(f"[DEBUG] Retrieved {len(commands)} commands for role {role}")
            
            # Update bot commands for this user
            bot.set_my_commands(commands, scope=BotCommandScopeChat(message.chat.id))
            print(f"[DEBUG] Updated bot commands for chat ID: {message.chat.id}")
            
            help_text = "📚 *Available Commands:*\n"
            for command in commands:
                help_text += f"/{command.command} - {command.description}\n"
        else:
            print("[DEBUG] User not approved - showing public commands only")
            help_text = "📚 *Available Commands:*\n"
            for command in PUBLIC_COMMANDS:
                help_text += f"/{command.command} - {command.description}\n"
            help_text += "\n*Note:* Additional commands will be available after your registration is approved."
        
        print("[DEBUG] Sending help text to user")
        bot.reply_to(message, help_text, parse_mode="Markdown")
        print("[DEBUG] Help text sent successfully")
        
    except Exception as e:
        print(f"[DEBUG] Error in update_help: {str(e)}")
        print(f"Error updating commands: {e}")
        bot.reply_to(message, "❌ Error updating commands menu.")

if __name__ == '__main__':
    print('🤖 Bot started. Press Ctrl+C to stop.')
    bot.infinity_polling()
