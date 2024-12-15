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
    def list_admins(message):
        """List all admin users"""
        try:
            admins = db.users.find({'role': Role.ADMIN.name.lower()})
            admin_list = list(admins)
            
            if not admin_list:
                bot.reply_to(message, "📝 No admins found.")
                return
                
            response = "👥 *Admin List:*\n\n"
            for admin in admin_list:
                response += (f"• ID: `{admin['user_id']}`\n"
                           f"  Username: @{admin.get('username', 'N/A')}\n"
                           f"  Name: {admin.get('first_name', '')} {admin.get('last_name', '')}\n\n")
                           
            bot.reply_to(message, response, parse_mode="Markdown")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error listing admins: {e}")
            
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

    @bot.message_handler(commands=['listdrive'])
    @check_owner(bot, db)
    def list_drive_contents(message):
        """List all files in the Team Drive folder"""
        try:
            args = message.text.split()
            folder_id = args[1] if len(args) > 1 else None
            recursive = False

            files = drive_service.list_files(folder_id, recursive)
            
            if not files:
                bot.reply_to(message, "📂 No files found in this folder.")
                return

            def format_file_list(files_list, level=0):
                response = ""
                indent = "  " * level
                
                for file in files_list:
                    is_folder = file['mimeType'] == 'application/vnd.google-apps.folder'
                    icon = "📂" if is_folder else "📄"
                    size = format_file_size(int(file.get('size', 0))) if not is_folder else ""
                    modified = format_timestamp(file['modifiedTime'])
                    
                    response += (
                        f"{indent}{icon} *{file['name']}*\n"
                        f"{indent}├ ID: `{file['id']}`\n"
                        f"{indent}├ Modified: {modified}\n"
                    )
                    
                    if size:
                        response += f"{indent}├ Size: {size}\n"
                    
                    if file.get('webViewLink'):
                        response += f"{indent}└ [Open in Drive]({file['webViewLink']})\n"
                    
                    response += "\n"
                    
                    # Recursively format children if present
                    if file.get('children'):
                        response += format_file_list(file['children'], level + 1)
                
                return response

            # Create paginated response
            full_response = format_file_list(files)
            max_length = 4096  # Telegram message length limit
            
            # Split response into chunks if needed
            if len(full_response) <= max_length:
                bot.reply_to(message, full_response, parse_mode="Markdown", disable_web_page_preview=True)
            else:
                chunks = [full_response[i:i + max_length] for i in range(0, len(full_response), max_length)]
                for i, chunk in enumerate(chunks, 1):
                    header = f"📋 File List (Part {i}/{len(chunks)}):\n\n"
                    bot.reply_to(message, header + chunk, parse_mode="Markdown", disable_web_page_preview=True)

        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

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
    def list_drives(message):
        """List all shared drives accessible to the service account"""
        try:
            drives = drive_service.list_drives()
            if not drives:
                bot.reply_to(message, "📂 No drives found.")
                return

            # Split drives into chunks of 10
            chunk_size = 10
            drive_chunks = [drives[i:i + chunk_size] for i in range(0, len(drives), chunk_size)]

            for i, chunk in enumerate(drive_chunks, 1):
                response = f"📂 *Drive List (Part {i}/{len(drive_chunks)}):*\n\n"
                
                for drive in chunk:
                    response += f"• *Name:* {drive['name']}\n"
                    response += f"  *ID:* `{drive['id']}`\n"
                    response += f"  *Type:* `{drive['type']}`\n\n"

                bot.reply_to(message, response, parse_mode="Markdown")

        except Exception as e:
            bot.reply_to(message, f"❌ Error listing drives: {str(e)}")