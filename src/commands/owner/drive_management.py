# Standard library imports
import os
from typing import Optional

# Third-party imports
from telebot import TeleBot
from telebot.types import Message

# Local application imports
from src.database.mongo_db import MongoDB
from src.middleware.auth import check_admin_or_owner
from src.services.drive_service import GoogleDriveService
from src.utils.user_actions import log_action, ActionType
from src.utils.state_management import UserStateManager
# Import handlers from drive modules
from src.commands.drive.core.list_handlers import register_list_handlers
from src.commands.drive.events.add_event import register_event_handlers
from src.commands.drive.events.list_events import register_list_events_handlers

def register_drive_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService):
    """Register all drive-related handlers"""
    print("[DEBUG] Registering drive handlers...")
    
    # Register core drive handlers
    list_handlers = register_list_handlers(bot, drive_service, db)
    print("[DEBUG] Core drive handlers registered")
    
    # Register event handlers
    list_event_handlers = register_list_events_handlers(bot, db, drive_service)
    print("[DEBUG] Event handlers registered")
    
    # Register drive info command
    @bot.message_handler(commands=['driveinfo'])
    @check_admin_or_owner(bot, db)
    def get_drive_info(message):
        """Get information about Drive access and status"""
        try:
            success, access_info = drive_service.verify_drive_access()
            
            if not success:
                bot.reply_to(
                    message,
                    "❌ Failed to verify Drive access. Please check credentials and permissions."
                )
                log_action(
                    ActionType.COMMAND_FAILED,
                    message.from_user.id,
                    error_message="Failed to verify drive access",
                    metadata={'command': 'driveinfo'}
                )
                return
                
            response = (
                "*Google Drive Status:*\n\n"
                "*Team Drive:*\n"
                f"├ Name: `{access_info['team_drive']['name']}`\n"
                f"├ Access Level: `{access_info['team_drive']['access_level'].value}`\n"
                f"└ URL: `{access_info['team_drive']['url']}`\n\n"
                "*Root Folder:*\n"
                f"├ Name: `{access_info['root_folder']['name']}`\n" 
                f"├ Access Level: `{access_info['root_folder']['access_level'].value}`\n"
                f"└ URL: `{access_info['root_folder']['url']}`\n"
            )
            
            bot.reply_to(
                message,
                response,
                parse_mode="Markdown"
            )
            
            log_action(
                ActionType.COMMAND_SUCCESS,
                message.from_user.id,
                metadata={'command': 'driveinfo'}
            )
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error getting drive info: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'driveinfo'}
            )
    
    # Return all handlers
    return