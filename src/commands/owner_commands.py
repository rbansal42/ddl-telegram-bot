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

def register_owner_handlers(bot: TeleBot):
    """Register all owner-specific command handlers"""
    db = MongoDB()
    drive_service = GoogleDriveService()
    
    # Register admin management handlers
    admin_handlers = register_admin_handlers(bot)
    promote_to_admin = admin_handlers['promote_to_admin']

    @bot.callback_query_handler(func=lambda call: call.data.startswith('promote_'))
    def handle_admin_promotion(call):
        """Handle member promotion to admin"""
        try:
            user_id = call.from_user.id
            user = db.users.find_one({'user_id': user_id})
            
            if not user or user.get('role') != Role.OWNER.name.lower():
                bot.answer_callback_query(call.id, "⛔️ This action is only available to the bot owner.")
                return
            
            _, member_id = call.data.split('_')
            member_id = int(member_id)
            
            promote_to_admin(bot, db, call.message.chat.id, member_id)
            
            bot.edit_message_text(
                f"✅ Admin promotion completed.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    # Keep existing handlers (remove_member, drive commands, etc.)
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
            '/listdrives': 'List all shared drives'
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
            {'command': '/listteamdrive', 'desc': 'Show contents of Team Drive'}
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

    @bot.message_handler(commands=['listteamdrive'])
    @check_admin_or_owner(bot, db)
    def list_team_drive_contents(message, page: int = 1):
        """List all files and folders in the Team Drive with pagination"""
        try:
            files = list(drive_service.list_team_drive_contents())
            if not files:
                bot.reply_to(message, "📂 No files or folders found in Team Drive.")
                return

            # Pagination settings
            page_size = 5
            total_files = len(files)
            total_pages = (total_files + page_size - 1) // page_size

            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages

            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            current_files = files[start_idx:end_idx]

            # Build the response message
            response = f"📂 *Team Drive Contents (Page {page}/{total_pages}):*\n\n"
            folders = [f for f in current_files if f['mimeType'] == 'application/vnd.google-apps.folder']
            files_only = [f for f in current_files if f['mimeType'] != 'application/vnd.google-apps.folder']

            if folders:
                response += "*Folders:*\n"
                for folder in folders:
                    response += f"📁 [{folder['name']}]({folder['webViewLink']})\n"
                response += "\n"

            if files_only:
                response += "*Files:*\n"
                for file in files_only:
                    response += f"📄 [{file['name']}]({file['webViewLink']})\n"

            # Create navigation markup
            markup = InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"listteamdrive_{page-1}"))
            if page < total_pages:
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"listteamdrive_{page+1}"))

            if buttons:
                markup.row(*buttons)

            # Split response if needed
            max_length = 4096
            if len(response) <= max_length:
                bot.reply_to(
                    message,
                    response,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                    reply_markup=markup
                )
            else:
                # Handle splitting messages if necessary
                chunks = [response[i:i + max_length] for i in range(0, len(response), max_length)]
                for i, chunk in enumerate(chunks, 1):
                    header = f"📋 Team Drive Contents (Part {i}/{len(chunks)}):\n\n"
                    bot.reply_to(
                        message,
                        header + chunk,
                        parse_mode="Markdown",
                        disable_web_page_preview=True,
                        reply_markup=markup if i == 1 else None  # Only attach markup to the first chunk
                    )

        except Exception as e:
            bot.reply_to(message, f"❌ Error listing Team Drive contents: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'listteamdrive'}
            )

    @bot.message_handler(commands=['driveinfo'])
    @check_admin_or_owner(bot, db)
    def get_drive_info(message):
        """Get information about Drive access and status"""
        try:
            success, access_info = drive_service.verify_drive_access()
            
            if not success:
                bot.reply_to(message, f"❌ Drive access verification failed: {access_info.get('error')}")
                return
            
            team_drive_info = access_info['team_drive']
            root_folder_info = access_info['root_folder']
            
            response = (
                "🔐 *Drive Access Information:*\n\n"
                "*Team Drive:*\n"
                f"├ Name: [{team_drive_info['name']}]({team_drive_info['url']})\n"
                f"└ Access: `{team_drive_info['access_level'].value}`\n\n"
                "*Root Folder:*\n"
                f"├ Name: [{root_folder_info['name']}]({root_folder_info['url']})\n"
                f"└ Access: `{root_folder_info['access_level'].value}`\n"
            )
            
            bot.reply_to(
                message, 
                response, 
                parse_mode="Markdown",
                disable_web_page_preview=True  # Prevents link preview
            )
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}") 

    @bot.message_handler(commands=['listdrives'])
    @check_admin_or_owner(bot, db)
    def list_drives(message, page: int = 1):
        """List all shared drives with pagination"""
        try:
            drives = list(drive_service.list_drives())
            if not drives:
                bot.reply_to(message, "📂 No drives found.")
                return

            # Pagination settings
            page_size = 5
            total_drives = len(drives)
            total_pages = (total_drives + page_size - 1) // page_size

            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages

            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            current_drives = drives[start_idx:end_idx]

            # Build the response message
            response = f"📂 *Drive List (Page {page}/{total_pages}):*\n\n"
            for drive in current_drives:
                response += (
                    f"• *Name:* {drive['name']}\n"
                    f"  *ID:* `{drive['id']}`\n"
                    f"  *Type:* `{drive['type']}`\n\n"
                )

            # Create navigation markup
            markup = InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"listdrives_{page-1}"))
            if page < total_pages:
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"listdrives_{page+1}"))

            if buttons:
                markup.row(*buttons)

            bot.reply_to(
                message,
                response,
                parse_mode="Markdown",
                reply_markup=markup
            )

        except Exception as e:
            bot.reply_to(message, f"❌ Error listing drives: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'listdrives'}
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('listdrives_'))
    def handle_list_drives_pagination(call):
        """Handle pagination for listdrives command"""
        try:
            # Debug prints
            print("=== Drive Pagination Handler Debug ===")
            print(f"Callback received from user ID: {call.from_user.id}")
            print(f"Callback data: {call.data}")

            # Hardcoded owner check for testing
            if call.from_user.id != 940075808:  # Replace with your Telegram ID
                print(f"Access denied for user {call.from_user.id}")
                bot.answer_callback_query(call.id, "⛔️ This command is only available to the bot owner.")
                return

            print("Owner verified, proceeding with pagination")

            # Extract the requested page number from callback_data
            _, page_str = call.data.split('_')
            page = int(page_str)
            print(f"Requested page: {page}")

            # Get drives list
            drives = list(drive_service.list_drives())

            # Pagination settings
            page_size = 5
            total_drives = len(drives)
            total_pages = (total_drives + page_size - 1) // page_size

            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages

            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            current_drives = drives[start_idx:end_idx]

            # Build the response message
            response = f"📂 *Drive List (Page {page}/{total_pages}):*\n\n"
            for drive in current_drives:
                response += (
                    f"• *Name:* {drive['name']}\n"
                    f"  *ID:* `{drive['id']}`\n"
                    f"  *Type:* `{drive['type']}`\n\n"
                )

            # Create navigation markup
            markup = InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"listdrives_{page-1}"))
            if page < total_pages:
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"listdrives_{page+1}"))

            if buttons:
                markup.row(*buttons)

            # Update the existing message
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=response,
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=markup
            )

            # Acknowledge the callback
            bot.answer_callback_query(call.id)

        except ValueError as ve:
            print(f"ValueError: {ve}")
            bot.answer_callback_query(call.id, "❌ Invalid page number.")
        except Exception as e:
            print(f"Error in drive pagination handler: {str(e)}")
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('listteamdrive_'))
    def handle_list_team_drive_pagination(call):
        """Handle pagination for listteamdrive command"""
        try:
            # Debug prints
            print("=== Team Drive Pagination Handler Debug ===")
            print(f"Callback received from user ID: {call.from_user.id}")
            print(f"Callback data: {call.data}")

            # Hardcoded owner check for testing
            if call.from_user.id != 940075808:  # Replace with your Telegram ID
                print(f"Access denied for user {call.from_user.id}")
                bot.answer_callback_query(call.id, "⛔️ This command is only available to the bot owner.")
                return

            print("Owner verified, proceeding with pagination")

            # Extract the requested page number from callback_data
            _, page_str = call.data.split('_')
            page = int(page_str)
            print(f"Requested page: {page}")

            # Get team drive contents
            files = list(drive_service.list_team_drive_contents())

            # Pagination settings
            page_size = 5
            total_files = len(files)
            total_pages = (total_files + page_size - 1) // page_size

            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages

            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            current_files = files[start_idx:end_idx]

            # Build the response message
            response = f"📂 *Team Drive Contents (Page {page}/{total_pages}):*\n\n"
            folders = [f for f in current_files if f['mimeType'] == 'application/vnd.google-apps.folder']
            files_only = [f for f in current_files if f['mimeType'] != 'application/vnd.google-apps.folder']

            if folders:
                response += "*Folders:*\n"
                for folder in folders:
                    response += f"📁 [{folder['name']}]({folder['webViewLink']})\n"
                response += "\n"

            if files_only:
                response += "*Files:*\n"
                for file in files_only:
                    response += f"📄 [{file['name']}]({file['webViewLink']})\n"

            # Create navigation markup
            markup = InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"listteamdrive_{page-1}"))
            if page < total_pages:
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"listteamdrive_{page+1}"))

            if buttons:
                markup.row(*buttons)

            # Handle message length
            max_length = 4096
            if len(response) <= max_length:
                # Update the existing message
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=response,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                    reply_markup=markup
                )
            else:
                # For long messages, send a new message
                chunks = [response[i:i + max_length] for i in range(0, len(response), max_length)]
                for i, chunk in enumerate(chunks, 1):
                    header = f"📋 Team Drive Contents (Part {i}/{len(chunks)}):\n\n"
                    if i == 1:
                        bot.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text=header + chunk,
                            parse_mode="Markdown",
                            disable_web_page_preview=True,
                            reply_markup=markup
                        )
                    else:
                        bot.send_message(
                            call.message.chat.id,
                            header + chunk,
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )
            
            # Acknowledge the callback
            bot.answer_callback_query(call.id)

        except ValueError as ve:
            print(f"ValueError: {ve}")
            bot.answer_callback_query(call.id, "❌ Invalid page number.")
        except Exception as e:
                print(f"Error in team drive pagination handler: {str(e)}")
                bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    @bot.message_handler(commands=['listeventsfolder'])
    @check_admin_or_owner(bot, db)
    def list_events_folder(message, page: int = 1):
        """List contents of the events folder with pagination"""
        try:
            # Retrieve the root folder ID from environment variables
            root_folder_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
            if not root_folder_id:
                bot.reply_to(message, "❌ Root folder ID is not configured.")
                return
            
            # Fetch the contents of the root folder
            items = drive_service.list_files(folder_id=root_folder_id, recursive=False)
            if not items:
                bot.reply_to(message, "📝 No items found in the events folder.")
                return
    
            # Pagination settings
            page_size = 5
            total_items = len(items)
            total_pages = (total_items + page_size - 1) // page_size
    
            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages
    
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            current_items = items[start_idx:end_idx]
    
            # Build the response message
            response = f"📂 *Events Folder Contents (Page {page}/{total_pages}):*\n\n"
            folders = [item for item in current_items if item['mimeType'] == 'application/vnd.google-apps.folder']
            files_only = [item for item in current_items if item['mimeType'] != 'application/vnd.google-apps.folder']
    
            if folders:
                response += "*Folders:*\n"
                for folder in folders:
                    response += f"📁 [{folder['name']}]({folder['webViewLink']})\n"
                response += "\n"
    
            if files_only:
                response += "*Files:*\n"
                for file in files_only:
                    file_size = format_file_size(int(file.get('size', 0))) if 'size' in file else 'N/A'
                    response += f"📄 [{file['name']}]({file['webViewLink']}) - {file_size}\n"
    
            # Create navigation markup
            markup = InlineKeyboardMarkup()
            buttons = []
    
            if page > 1:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"listeventsfolder_{page-1}"))
            if page < total_pages:
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"listeventsfolder_{page+1}"))
    
            if buttons:
                markup.row(*buttons)
    
            bot.reply_to(
                message,
                response,
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=markup
            )
    
        except Exception as e:
            bot.reply_to(message, f"❌ Error listing events folder contents: {e}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'listeventsfolder'}
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('listeventsfolder_'))
    def handle_list_events_folder_pagination(call):
        """Handle pagination for listeventsfolder command"""
        try:
            # Extract the requested page number from callback_data
            _, page_str = call.data.split('_')
            page = int(page_str)
            
            # Get folder contents
            root_folder_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
            items = drive_service.list_files(folder_id=root_folder_id, recursive=False)
            
            # Pagination settings
            page_size = 5
            total_items = len(items)
            total_pages = (total_items + page_size - 1) // page_size
            
            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages
                
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            current_items = items[start_idx:end_idx]
            
            # Build the response message
            response = f"📂 *Events Folder Contents (Page {page}/{total_pages}):*\n\n"
            folders = [item for item in current_items if item['mimeType'] == 'application/vnd.google-apps.folder']
            files_only = [item for item in current_items if item['mimeType'] != 'application/vnd.google-apps.folder']
            
            if folders:
                response += "*Folders:*\n"
                for folder in folders:
                    response += f"📁 [{folder['name']}]({folder['webViewLink']})\n"
                response += "\n"
                
            if files_only:
                response += "*Files:*\n"
                for file in files_only:
                    file_size = format_file_size(int(file.get('size', 0))) if 'size' in file else 'N/A'
                    response += f"📄 [{file['name']}]({file['webViewLink']}) - {file_size}\n"
                    
            # Create navigation markup
            markup = InlineKeyboardMarkup()
            buttons = []
            
            if page > 1:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"listeventsfolder_{page-1}"))
            if page < total_pages:
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"listeventsfolder_{page+1}"))
                
            if buttons:
                markup.row(*buttons)
                
            # Update the existing message
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=response,
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=markup
            )
            
            # Acknowledge the callback
            bot.answer_callback_query(call.id)

        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")
    
    @bot.message_handler(commands=['addevent'])
    @check_event_permission(bot, db)  # Changed from check_admin_or_owner
    def add_event(message):
        """Start the process of adding a new event folder"""
        try:
            # Ask for event name
            msg = bot.reply_to(message, "📝 Please enter the name of the event:")
            bot.register_next_step_handler(msg, process_event_name)
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'addevent'}
            )

    def process_event_name(message):
        """Process the event name and ask for date options"""
        try:
            # Store event name in user data
            user_data = {}
            user_data['event_name'] = message.text.strip()
            
            # Create markup for date options
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📅 Custom Date", callback_data="date_custom"),
                InlineKeyboardButton("📆 Today", callback_data="date_today")
            )
            
            # Ask for date preference
            bot.reply_to(
                message,
                "Choose date option:",
                reply_markup=markup
            )
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

    def process_event_date(message, user_data):
        """Process the event date and create the folder"""
        try:
            from datetime import datetime
            
            # Parse and validate date
            try:
                date = datetime.strptime(message.text.strip(), '%d/%m/%Y')
                formatted_date = date.strftime('%Y-%m-%d')
            except ValueError:
                bot.reply_to(message, "❌ Invalid date format. Please use DD/MM/YYYY")
                return

            # Create folder name
            folder_name = f"{formatted_date}; {user_data['event_name']}"
            
            # Create folder in Drive
            folder = drive_service.create_folder(folder_name)
            
            # Set sharing permissions
            sharing_url = drive_service.set_folder_sharing_permissions(folder['id'])
            
            # Escape the texts using the helper function
            escaped_name = escape_markdown(user_data['event_name'])
            escaped_url = escape_markdown(sharing_url)
            
            # Format response
            response = (
                f"✅ Event folder created successfully\\!\n\n"
                f"*Event:* {escaped_name}\n"
                f"*Link:* {escaped_url}"
            )
            
            bot.reply_to(
                message,
                response,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )
            
            # Log action
            log_action(
                ActionType.FOLDER_CREATED,
                message.from_user.id,
                metadata={
                    'folder_name': folder_name,
                    'folder_id': folder['id']
                }
            )
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error creating event folder: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'addevent'}
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('date_'))
    def handle_date_option(call):
        """Handle date option selection"""
        try:
            option = call.data.split('_')[1]
            user_data = {}
            user_data['event_name'] = call.message.reply_to_message.text.strip()
            
            if option == 'today':
                # Use current date
                from datetime import datetime
                date = datetime.now()
                formatted_date = date.strftime('%Y-%m-%d')
                
                # Create folder directly
                folder_name = f"{formatted_date}; {user_data['event_name']}"
                folder = drive_service.create_folder(folder_name)
                sharing_url = drive_service.set_folder_sharing_permissions(folder['id'])
                
                # Escape the texts using the helper function
                escaped_name = escape_markdown(user_data['event_name'])
                escaped_url = escape_markdown(sharing_url)
                
                # Format response
                response = (
                    f"✅ Event folder created successfully\\!\n\n"
                    f"*Event:* {escaped_name}\n"
                    f"*Link:* {escaped_url}"
                )
                
                bot.edit_message_text(
                    response,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True
                )
                
                # Log action
                log_action(
                    ActionType.FOLDER_CREATED,
                    call.from_user.id,
                    metadata={
                        'folder_name': folder_name,
                        'folder_id': folder['id']
                    }
                )
                
            else:  # custom date
                msg = bot.edit_message_text(
                    "📅 Please enter the event date in format DD/MM/YYYY:",
                    call.message.chat.id,
                    call.message.message_id
                )
                bot.register_next_step_handler(msg, process_event_date, user_data)
                
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    return {
        'admin_handlers': admin_handlers,
        # Other handlers...
    }