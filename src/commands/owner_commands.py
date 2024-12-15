# Standard library imports
import os

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BotCommandScopeChat

# Local application imports
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_admin_or_owner, check_event_permission
from src.services.google.drive_service import GoogleDriveService
from src.utils.command_helpers import get_commands_for_role
from src.utils.file_helpers import format_file_size
from src.utils.notifications import notify_user, NotificationType
from src.utils.user_actions import log_action, ActionType
from src.utils.message_helpers import escape_markdown, create_list_message
from src.commands.owner.admin_management import register_admin_handlers

def register_owner_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService):
    """Register all owner-specific command handlers"""

    @bot.message_handler(commands=['refreshcommands'])
    @check_admin_or_owner(bot, db)
    def refresh_commands(message: Message) -> None:
        """Update command menus for all registered users"""
        print("========================== [DEBUG] Refresh Commands Started ==========================")
        print(f"[DEBUG] Message from user ID: {message.from_user.id}")
        try:
            print("[DEBUG] Fetching registered users from database...")
            # Get all registered users
            registered_users = db.users.find({'registration_status': 'approved'})
            registered_users_list = list(registered_users)
            print(f"[DEBUG] Found {len(registered_users_list)} registered users")
            
            success_count = 0
            error_count = 0
            
            for user in registered_users_list:
                print(f"\n[DEBUG] Processing user: {user}")
                try:
                    user_id = user.get('user_id')
                    role = user.get('role', 'unregistered')
                    print(f"[DEBUG] User ID: {user_id}, Role: {role}")
                    
                    # Get appropriate commands for user's role
                    print(f"[DEBUG] Getting commands for role: {role}")
                    commands = get_commands_for_role(role)
                    print(f"[DEBUG] Retrieved {len(commands)} commands")
                    
                    # Update commands for this user
                    print(f"[DEBUG] Updating commands for user {user_id}")
                    bot.set_my_commands(
                        commands,
                        scope=BotCommandScopeChat(user_id)
                    )
                    success_count += 1
                    print(f"[DEBUG] Successfully updated commands for user {user_id}")
                    
                except Exception as e:
                    print(f"[DEBUG] Failed to update commands for user {user.get('user_id')}")
                    print(f"[DEBUG] Error details: {str(e)}")
                    error_count += 1
                    continue
            
            # Send summary message
            print("\n[DEBUG] Preparing summary message")
            summary = (
                f"✅ Command refresh complete\n\n"
                f"Successfully updated: {success_count} users\n"
                f"Failed updates: {error_count} users"
            )
            print(f"[DEBUG] Summary message: {summary}")
            
            print("[DEBUG] Sending reply to user")
            bot.reply_to(message, summary)
            
            # Log the action
            print("[DEBUG] Logging refresh action")
            log_action(
                ActionType.COMMAND_REFRESH,
                message.from_user.id
            )
            print("[DEBUG] Action logged successfully")
            
        except Exception as e:
            print(f"[DEBUG] Critical error in refresh_commands: {str(e)}")
            print(f"[DEBUG] Error type: {type(e)}")
            print("[DEBUG] Sending error message to user")
            bot.reply_to(message, "❌ Error refreshing commands.")
        
        print("========================== [DEBUG] Refresh Commands Completed ==========================")
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