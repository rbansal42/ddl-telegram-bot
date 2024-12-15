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

    @bot.message_handler(commands=['remove_member'])
    @check_admin_or_owner(bot, db)
    def remove_member(message):
        """Remove a member from the system"""
        args = message.text.split()
        if len(args) == 1:  # No user_id provided
            try:
                # Get all members
                members = db.users.find({
                    'registration_status': 'approved',
                    'role': Role.MEMBER.name.lower()
                })
                member_list = list(members)
                
                if not member_list:
                    bot.reply_to(message, "📝 No registered members found to remove.")
                    return
                    
                # Create inline keyboard with member buttons
                markup = InlineKeyboardMarkup()
                for member in member_list:
                    full_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() or 'N/A'
                    email = member.get('email', 'N/A')
                    markup.add(
                        InlineKeyboardButton(
                            f"👤 {full_name} | 📧 {email}",
                            callback_data=f"remove_{member['user_id']}"
                        )
                    )
                
                bot.reply_to(message, 
                    "👥 *Select a member to remove:*",
                    reply_markup=markup,
                    parse_mode="Markdown")
                
            except Exception as e:
                bot.reply_to(message, f"❌ Error listing members: {e}")
                return
        else:
            try:
                member_id = int(args[1])
                member = db.users.find_one({'user_id': member_id})
                
                if not member:
                    bot.reply_to(message, "❌ Member not found.")
                    return
                    
                if member.get('role') != Role.MEMBER.name.lower():
                    bot.reply_to(message, "❌ This user is not a member.")
                    return
                    
                result = db.users.delete_one({'user_id': member_id})
                if result.deleted_count > 0:
                    bot.reply_to(message, f"✅ Member {member_id} has been removed.")
                    try:
                        notify_user(
                            bot,
                            NotificationType.MEMBER_REMOVED,
                            member_id,
                            issuer_id=message.from_user.id
                        )
                    except Exception as e:
                        print(f"Failed to notify removed member: {e}")
                else:
                    bot.reply_to(message, "❌ Failed to remove member.")
            except ValueError:
                bot.reply_to(message, "❌ Invalid user ID format.")
            except Exception as e:
                bot.reply_to(message, f"❌ Error removing member: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
    @check_admin_or_owner(bot, db)
    def handle_remove_member(call):
        """Handle member removal confirmation"""
        try:
            if not check_admin_or_owner(bot, db)(lambda: True)(call.message):
                bot.answer_callback_query(call.id, "⛔️ This action is only available to owners.")
                return
                
            _, member_id = call.data.split('_')
            member_id = int(member_id)
            
            member = db.users.find_one({'user_id': member_id})
            if not member:
                bot.answer_callback_query(call.id, "❌ Member not found.")
                return
                
            if member.get('role') != Role.MEMBER.name.lower():
                bot.answer_callback_query(call.id, "❌ This user is not a member.")
                return
            
            result = db.users.delete_one({'user_id': member_id})
            if result.deleted_count > 0:
                bot.edit_message_text(
                    f"✅ Member {member_id} has been removed.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
                try:
                    notify_user(
                        bot,
                        NotificationType.MEMBER_REMOVED,
                        member_id,
                        issuer_id=call.from_user.id
                    )
                except Exception as e:
                    print(f"Failed to notify removed member: {e}")
            else:
                bot.answer_callback_query(call.id, "❌ Failed to remove member.")
                
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")
            
    @bot.callback_query_handler(func=lambda call: call.data.startswith(('confirm_remove_', 'cancel_remove_')))
    def handle_remove_confirmation(call):
        """Handle the confirmation of member removal"""
        try:
            if not check_admin_or_owner(bot, db)(lambda: True)(call.message):
                bot.answer_callback_query(call.id, "⛔️ This action is only available to owners.")
                return
            
            action, _, member_id = call.data.split('_')
            member_id = int(member_id)
            
            if action == 'cancel':
                bot.edit_message_text(
                    "❌ Member removal cancelled.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
                bot.answer_callback_query(call.id)
                return
            
            member = db.users.find_one({'user_id': member_id})
            if not member:
                bot.edit_message_text(
                    "❌ Member not found.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
                bot.answer_callback_query(call.id)
                return
                
            if member.get('role') != Role.MEMBER.name.lower():
                bot.edit_message_text(
                    "❌ This user is not a member.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
                bot.answer_callback_query(call.id)
                return
                
            result = db.users.delete_one({'user_id': member_id})
            if result.deleted_count > 0:
                bot.edit_message_text(
                    f"✅ Member {member_id} has been removed.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
                try:
                    notify_user(
                        bot,
                        NotificationType.MEMBER_REMOVED,
                        member_id,
                        issuer_id=call.from_user.id
                    )
                except Exception as e:
                    print(f"Failed to notify removed member: {e}")
            else:
                bot.edit_message_text(
                    "❌ Failed to remove member.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
            bot.answer_callback_query(call.id)
                
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

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