import os
from telebot import TeleBot, types
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_owner
from src.utils.notifications import notify_user, NotificationType
from src.utils.user_actions import log_action, ActionType
from src.utils.markup_helpers import create_promotion_markup, create_admin_list_markup
from src.services.google.drive_service import GoogleDriveService
from src.utils.file_helpers import format_file_size, format_timestamp
from functools import wraps

def register_owner_handlers(bot: TeleBot):
    db = MongoDB()
    drive_service = GoogleDriveService()
    
    @bot.message_handler(commands=['addadmin'])
    @check_owner(bot, db)
    def add_admin(message):
        """Add a new admin user"""
        try:
            args = message.text.split()
            if len(args) == 1:  # No user_id provided
                # Get members query
                members_query = {
                    'registration_status': 'approved',
                    'role': Role.MEMBER.name.lower()
                }
                
                # Execute query
                members = db.users.find(members_query)
                member_list = list(members)
                
                if not member_list:
                    bot.reply_to(message, "📝 No registered members found to promote.")
                    return

                # Create markup
                markup = types.InlineKeyboardMarkup()
                for member in member_list:
                    # Format member info in one line
                    full_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() or 'N/A'
                    email = member.get('email', 'N/A')
                    user_id = member.get('user_id')
                    
                    # Single button with all info
                    markup.add(
                        types.InlineKeyboardButton(
                            f"👤 {full_name} | 📧 {email}",
                            callback_data=f"promote_{user_id}"
                        )
                    )
                
                bot.reply_to(message, 
                    "👥 *Select a member to promote to admin:*",
                    reply_markup=markup,
                    parse_mode="Markdown")
                
            else:
                new_admin_id = int(args[1])
                promote_to_admin(bot, db, message.from_user.id, new_admin_id)
                
        except Exception as e:
            print(f"❌ Error in add_admin: {e}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'addadmin'}
            )
            bot.reply_to(message, f"❌ Error adding admin: {e}")

    @bot.message_handler(commands=['removeadmin'])
    @check_owner(bot, db)
    def remove_admin(message):
        """Remove an admin user"""
        try:
            args = message.text.split()
            if len(args) == 1:  # No user_id provided
                admins = db.users.find(
                    {'role': Role.ADMIN.name.lower()},
                    {
                        'user_id': 1,
                        'username': 1,
                        'first_name': 1,
                        'last_name': 1,
                        'email': 1,
                        'role': 1
                    }
                )
                admin_list = list(admins)
                
                if not admin_list:
                    bot.reply_to(message, "📝 No admins found to demote.")
                    return

                # Create markup
                markup = types.InlineKeyboardMarkup()
                for admin in admin_list:
                    # Format admin info in one line
                    full_name = f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip() or 'N/A'
                    email = admin.get('email', 'N/A')
                    user_id = admin.get('user_id')
                    
                    # Single button with all info
                    markup.add(
                        types.InlineKeyboardButton(
                            f"👤 {full_name} | 📧 {email}",
                            callback_data=f"demote_{user_id}"
                        )
                    )
                
                bot.reply_to(message, 
                    "👥 *Select an admin to demote:*",
                    reply_markup=markup,
                    parse_mode="Markdown")
            else:
                admin_id = int(args[1])
                demote_to_member(bot, db, message.from_user.id, admin_id)
                
        except Exception as e:
            bot.reply_to(message, f"❌ Error removing admin: {e}")
            
    @bot.callback_query_handler(func=lambda call: call.data.startswith('demote_'))
    @check_owner(bot, db)
    def handle_admin_demotion(call):
        """Handle admin demotion to member"""
        try:
            _, admin_id = call.data.split('_')
            admin_id = int(admin_id)
            
            demote_to_member(bot, db, call.message.chat.id, admin_id)
            
            bot.edit_message_text(
                f"✅ Admin demotion completed.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    def demote_to_member(bot, db, chat_id, admin_id):
        """Helper function to demote an admin to member"""
        try:
            user = db.users.find_one({'user_id': admin_id})
            
            if not user:
                raise Exception("User not found.")
            
            if user.get('role') != Role.ADMIN.name.lower():
                raise Exception("User is not an admin.")
            
            db.users.update_one(
                {'user_id': admin_id},
                {'$set': {'role': Role.MEMBER.name.lower()}}
            )
            
            log_action(
                ActionType.ADMIN_DEMOTION,
                chat_id,
                metadata={
                    'demoted_user_id': admin_id
                }
            )
            
            bot.send_message(chat_id, f"✅ User {admin_id} has been demoted to member.")
            
            try:
                notify_user(
                    bot,
                    NotificationType.DEMOTION_TO_MEMBER,
                    admin_id,
                    issuer_id=chat_id
                )
            except Exception as e:
                print(f"Failed to notify former admin: {e}")
            
        except Exception as e:
            raise Exception(f"Failed to demote admin to member: {str(e)}")

    def promote_to_admin(bot, db, chat_id, member_id):
        """Helper function to promote a member to admin"""
        user = db.users.find_one({'user_id': member_id})
        
        if not user:
            raise Exception("User not found.")
            
        if user.get('role') != Role.MEMBER.name.lower():
            raise Exception("User is not a member.")
            
        db.users.update_one(
            {'user_id': member_id},
            {'$set': {'role': Role.ADMIN.name.lower()}}
        )
        
        bot.send_message(chat_id, f"✅ User {member_id} has been promoted to admin.")
        
        try:
            notify_user(
                bot,
                NotificationType.PROMOTION_TO_ADMIN,
                member_id,
                issuer_id=chat_id
            )
        except Exception as e:
            print(f"Failed to notify new admin: {e}")

    @bot.message_handler(commands=['listadmins'])
    @check_owner(bot, db)
    def list_admins(message, page: int = 1):
        """List all admin users with pagination"""
        try:
            admins = list(db.users.find({'role': Role.ADMIN.name.lower()}))
            if not admins:
                bot.reply_to(message, "📝 No admins found.")
                return

            # Pagination settings
            page_size = 5
            total_admins = len(admins)
            total_pages = (total_admins + page_size - 1) // page_size

            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages

            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            current_admins = admins[start_idx:end_idx]

            # Build the response message
            response = f"👥 *Admin List (Page {page}/{total_pages}):*\n\n"
            for admin in current_admins:
                response += (
                    f"• ID: `{admin['user_id']}`\n"
                    f"  Username: @{admin.get('username', 'N/A')}\n"
                    f"  Name: {admin.get('first_name', '')} {admin.get('last_name', '')}\n\n"
                )

            # Create navigation markup
            markup = types.InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"listadmins_{page-1}"))
            if page < total_pages:
                buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"listadmins_{page+1}"))

            if buttons:
                markup.row(*buttons)

            bot.reply_to(
                message,
                response,
                parse_mode="Markdown",
                reply_markup=markup
            )

        except Exception as e:
            bot.reply_to(message, f"❌ Error listing admins: {e}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'listadmins'}
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('listadmins_'))
    def handle_list_admins_pagination(call):
        """Handle pagination for listadmins command"""
        try:
            # Extract the requested page number from callback_data
            _, page_str = call.data.split('_')
            page = int(page_str)

            # Call the list_admins function with the new page number
            list_admins(call.message, page)

            # Acknowledge the callback to remove the loading state
            bot.answer_callback_query(call.id)

        except ValueError:
            bot.answer_callback_query(call.id, "❌ Invalid page number.")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    @bot.message_handler(commands=['remove_member'])
    @check_owner(bot, db)
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
                markup = types.InlineKeyboardMarkup()
                for member in member_list:
                    full_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() or 'N/A'
                    email = member.get('email', 'N/A')
                    markup.add(
                        types.InlineKeyboardButton(
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
    @check_owner(bot, db)
    def handle_remove_member(call):
        """Handle member removal confirmation"""
        try:
            if not check_owner(bot, db)(lambda: True)(call.message):
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
            if not check_owner(bot, db)(lambda: True)(call.message):
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
    @check_owner(bot, db)
    def owner_help(message):
        """Show all owner-level commands"""
        help_text = "👑 *Owner Commands:*\n\n"
        
        # Add owner-specific commands
        owner_commands = {
            "addadmin": "Add a new admin user",
            "removeadmin": "Remove an admin user",
            "listadmins": "List all admin users",
            "pending": "List all pending registrations",
            "remove_member": "Remove a member from the system",
            "ownerhelp": "Show this help message"
        }
        
        for cmd, desc in owner_commands.items():
            help_text += f"/{cmd} - {desc}\n"
            
        help_text += "\n*Usage Examples:*\n"
        help_text += "• `/addadmin 123456789` - Make user with ID 123456789 an admin\n"
        help_text += "• `/removeadmin 123456789` - Remove admin privileges from user\n"
        help_text += "• `/listadmins` - Show all current admins\n"
        help_text += "• `/remove_member 123456789` - Remove member with ID 123456789\n"
        
        bot.reply_to(message, help_text, parse_mode="Markdown") 

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

    @bot.message_handler(commands=['listteamdrive'])
    @check_owner(bot, db)
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
            markup = types.InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"listteamdrive_{page-1}"))
            if page < total_pages:
                buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"listteamdrive_{page+1}"))

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
    @check_owner(bot, db)
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
    @check_owner(bot, db)
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
            markup = types.InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"listdrives_{page-1}"))
            if page < total_pages:
                buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"listdrives_{page+1}"))

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
            markup = types.InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"listdrives_{page-1}"))
            if page < total_pages:
                buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"listdrives_{page+1}"))

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
            markup = types.InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"listteamdrive_{page-1}"))
            if page < total_pages:
                buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"listteamdrive_{page+1}"))

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
    @check_owner(bot, db)
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
            markup = types.InlineKeyboardMarkup()
            buttons = []
    
            if page > 1:
                buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"listeventsfolder_{page-1}"))
            if page < total_pages:
                buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"listeventsfolder_{page+1}"))
    
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
            markup = types.InlineKeyboardMarkup()
            buttons = []
            
            if page > 1:
                buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"listeventsfolder_{page-1}"))
            if page < total_pages:
                buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"listeventsfolder_{page+1}"))
                
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