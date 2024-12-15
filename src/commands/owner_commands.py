# Standard library imports
import os

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Local application imports
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_admin_or_owner, check_event_permission
from src.services.google.drive_service import GoogleDriveService
from src.utils.file_helpers import format_file_size
from src.utils.notifications import notify_user, NotificationType
from src.utils.user_actions import log_action, ActionType
from src.utils.message_helpers import escape_markdown, create_list_message
from src.commands.owner.admin_management import register_admin_handlers

def register_owner_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService):
    """Register all owner-specific command handlers"""

    @bot.message_handler(commands=['ownerhelp'])
    @check_admin_or_owner(bot, db)
    def owner_help(message):
        """Show all owner-level commands"""
        
        # Define command sections with their descriptions
        drive_commands = {
            '/listteamdrive': 'List all files in Team Drive',
            '/driveinfo': 'Get Drive access information',
            '/listdrives': 'List all shared drives',
            '/listevents': 'List contents of the events folder',
            '/addevent': 'Add a new event folder'
        }
        
        member_commands = {
            '/remove_member': 'Remove a member from the system'
        }
        
        admin_commands = {
            '/addadmin': 'Add a new admin user',
            '/removeadmin': 'Remove an admin user',
            '/listadmins': 'List all admin users'
        }
        
        other_commands = {
            '/ownerhelp': 'Show this help message'
        }
        
        # Create the help message using the helper functions
        sections = [
            ('Drive Management', drive_commands),
            ('Member Management', member_commands),
            ('Admin Management', admin_commands),
            ('Other', other_commands)
        ]
        
        # Build the message using create_list_message for each section
        help_text = "*👑 Owner Commands:*\n\n"
        
        for section_title, commands in sections:
            # Convert commands dict to list of dicts for create_list_message
            command_items = [
                {'command': cmd, 'description': desc}
                for cmd, desc in commands.items()
            ]
            
            section_message = create_list_message(
                title=f"*{section_title}:*",
                items=command_items,
                item_template="{command} \\- {description}",
                empty_message="No commands available."
            )
            help_text += f"{section_message}\n"
        
        # Add usage examples
        examples = [
            {'command': '/remove_member 123456789', 'desc': 'Remove member with ID 123456789'},
            {'command': '/listteamdrive', 'desc': 'Show contents of Team Drive'},
            {'command': '/listeventsfolder', 'desc': 'List all event folders'},
            {'command': '/addadmin 123456789', 'desc': 'Add a new admin user'}
        ]
        
        examples_section = create_list_message(
            title="*Usage Examples:*",
            items=examples,
            item_template="• {command} \\- {desc}"
        )
        
        help_text += f"\n{examples_section}"
        
        # Send the message
        bot.reply_to(
            message,
            help_text,
            parse_mode="MarkdownV2"
        )