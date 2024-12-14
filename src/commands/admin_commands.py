import os
from telebot import TeleBot, types
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_admin_or_owner
from src.utils.notifications import notify_user, NotificationType
from src.utils.user_actions import log_action, ActionType

def register_admin_handlers(bot: TeleBot):
    db = MongoDB()
    
    @bot.message_handler(commands=['listmembers'])
    @check_admin_or_owner(bot, db)
    def list_members(message):
        """List all registered members"""
        try:
            members = db.users.find({
                'registration_status': 'approved',
                'role': Role.MEMBER.name.lower()
            })
            member_list = list(members)
            
            log_action(
                ActionType.ADMIN_COMMAND,
                message.from_user.id,
                metadata={
                    'command': 'listmembers',
                    'members_count': len(member_list)
                }
            )
            
            if not member_list:
                bot.reply_to(message, "📝 No registered members found.")
                return
                
            # Create paginated response
            page_size = 10
            total_members = len(member_list)
            total_pages = (total_members + page_size - 1) // page_size
            
            def create_member_page(page):
                start_idx = (page - 1) * page_size
                end_idx = min(start_idx + page_size, total_members)
                
                response = f"👥 *Members List (Page {page}/{total_pages}):*\n\n"
                for member in member_list[start_idx:end_idx]:
                    response += (f"• ID: `{member['user_id']}`\n"
                               f"  Username: @{member.get('username', 'N/A')}\n"
                               f"  Name: {member.get('first_name', '')} {member.get('last_name', '')}\n\n")
                return response
                
            # Create navigation markup
            def create_navigation_markup(current_page):
                markup = types.InlineKeyboardMarkup()
                buttons = []
                
                if current_page > 1:
                    buttons.append(types.InlineKeyboardButton(
                        "⬅️ Previous", callback_data=f"members_{current_page-1}"))
                    
                if current_page < total_pages:
                    buttons.append(types.InlineKeyboardButton(
                        "Next ➡️", callback_data=f"members_{current_page+1}"))
                    
                markup.row(*buttons)
                return markup
                
            # Send first page
            bot.reply_to(message, 
                create_member_page(1), 
                parse_mode="Markdown",
                reply_markup=create_navigation_markup(1))
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error listing members: {e}")
            
    @bot.callback_query_handler(func=lambda call: call.data.startswith('members_'))
    def handle_members_navigation(call):
        """Handle member list navigation"""
        try:
            if not check_admin_or_owner(bot, db)(lambda: True)(call.message):
                return
                
            page = int(call.data.split('_')[1])
            members = db.users.find({
                'registration_status': 'approved',
                'role': Role.MEMBER.name.lower()
            })
            member_list = list(members)
            
            page_size = 10
            total_members = len(member_list)
            total_pages = (total_members + page_size - 1) // page_size
            
            def create_member_page(page):
                start_idx = (page - 1) * page_size
                end_idx = min(start_idx + page_size, total_members)
                
                response = f"👥 *Members List (Page {page}/{total_pages}):*\n\n"
                for member in member_list[start_idx:end_idx]:
                    response += (f"• ID: `{member['user_id']}`\n"
                               f"  Username: @{member.get('username', 'N/A')}\n"
                               f"  Name: {member.get('first_name', '')} {member.get('last_name', '')}\n\n")
                return response
                
            def create_navigation_markup(current_page):
                markup = types.InlineKeyboardMarkup()
                buttons = []
                
                if current_page > 1:
                    buttons.append(types.InlineKeyboardButton(
                        "⬅️ Previous", callback_data=f"members_{current_page-1}"))
                    
                if current_page < total_pages:
                    buttons.append(types.InlineKeyboardButton(
                        "Next ➡️", callback_data=f"members_{current_page+1}"))
                    
                markup.row(*buttons)
                return markup
                
            bot.edit_message_text(
                create_member_page(page),
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=create_navigation_markup(page)
            )
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)}")

    @bot.message_handler(commands=['adminhelp'])
    @check_admin_or_owner(bot, db)
    def admin_help(message):
        """Show all admin-level commands"""
        help_text = "👮‍♂️ *Admin Commands:*\n\n"
        
        # Add admin-specific commands with descriptions
        admin_commands = {
            "listmembers": "List all registered members",
            "removemember": "Remove a member from the system",
            "pending": "List and manage pending registration requests",
            "adminhelp": "Show this help message"
        }
        
        for cmd, desc in admin_commands.items():
            help_text += f"/{cmd} - {desc}\n"
            
        help_text += "\n*Usage Examples:*\n"
        help_text += "• `/listmembers` - View all registered members with pagination\n"
        help_text += "• `/removemember` - Remove a member (shows interactive member list)\n"
        help_text += "• `/pending` - View and manage pending registration requests\n"
        
        bot.reply_to(message, help_text, parse_mode="Markdown")

    @bot.message_handler(commands=['removemember'])
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
                markup = types.InlineKeyboardMarkup()
                for member in member_list:
                    username = f"@{member.get('username', 'N/A')}"
                    name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
                    button_text = f"{name} ({username})"
                    callback_data = f"remove_{member['user_id']}"
                    markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
                
                bot.reply_to(message, 
                    "👥 *Select a member to remove:*",
                    reply_markup=markup,
                    parse_mode="Markdown")
                
            except Exception as e:
                bot.reply_to(message, f"❌ Error listing members: {e}")
                return
                
    @bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
    def handle_remove_member(call):
        """Handle member removal confirmation"""
        try:
            if not check_admin_or_owner(bot, db)(lambda: True)(call.message):
                return
                
            user_id = int(call.data.split('_')[1])
            member = db.users.find_one({'user_id': user_id})
            
            if not member:
                bot.answer_callback_query(call.id, "❌ Member not found!")
                return
                
            # Create confirmation markup
            markup = types.InlineKeyboardMarkup()
            confirm_button = types.InlineKeyboardButton(
                "✅ Confirm Remove", callback_data=f"confirmremove_{user_id}")
            cancel_button = types.InlineKeyboardButton(
                "❌ Cancel", callback_data="cancelremove")
            markup.row(confirm_button, cancel_button)
            
            username = f"@{member.get('username', 'N/A')}"
            name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
            
            bot.edit_message_text(
                f"⚠️ *Are you sure you want to remove this member?*\n\n"
                f"Name: {name}\n"
                f"Username: {username}\n"
                f"ID: `{user_id}`",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)}")
            
    @bot.callback_query_handler(func=lambda call: call.data.startswith('confirmremove_'))
    def handle_remove_confirmation(call):
        """Handle final member removal"""
        try:
            if not check_admin_or_owner(bot, db)(lambda: True)(call.message):
                return
                
            user_id = int(call.data.split('_')[1])
            member = db.users.find_one({'user_id': user_id})
            
            if not member:
                bot.answer_callback_query(call.id, "❌ Member not found!")
                return
                
            # Remove member
            db.users.delete_one({'user_id': user_id})
            
            # Notify the removed member
            try:
                notify_user(
                    bot,
                    user_id,
                    NotificationType.ACCESS_REVOKED,
                    "You have been removed from the system by an admin."
                )
            except Exception as e:
                print(f"Failed to notify removed member: {e}")
            
            bot.edit_message_text(
                f"✅ Member removed successfully!\n\n"
                f"Name: {member.get('first_name', '')} {member.get('last_name', '')}\n"
                f"Username: @{member.get('username', 'N/A')}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)}")
            
    @bot.callback_query_handler(func=lambda call: call.data == "cancelremove")
    def handle_remove_cancellation(call):
        """Handle cancellation of member removal"""
        try:
            bot.edit_message_text(
                "❌ Member removal cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)}")

    @bot.message_handler(commands=['pending'])
    @check_admin_or_owner(bot, db)
    def list_pending_registrations(message):
        """List all pending registration requests"""
        try:
            pending = db.registration_requests.find({
                'status': 'pending'
            })
            pending_list = list(pending)
            
            if not pending_list:
                bot.reply_to(message, "📝 No pending registration requests.")
                return
                
            for request in pending_list:
                user = db.users.find_one({'user_id': request['user_id']})
                if not user:
                    continue
                    
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{request['_id']}"),
                    types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{request['_id']}")
                )
                
                text = (
                    f"📝 Registration Request\n"
                    f"User ID: `{user['user_id']}`\n"
                    f"Username: @{user.get('username', 'N/A')}\n"
                    f"Name: {user.get('first_name', '')} {user.get('last_name', '')}\n"
                    f"Email: {user.get('email', 'N/A')}"
                )
                
                bot.send_message(
                    message.chat.id,
                    text,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            bot.reply_to(message, f"❌ Error listing pending requests: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
    def handle_registration_decision(call):
        """Handle registration approval/rejection"""
        try:
            if not check_admin_or_owner(bot, db)(lambda: True)(call.message):
                return
                
            action, request_id = call.data.split('_')
            admin_id = call.from_user.id
            
            # Get registration request
            request = db.registration_requests.find_one({'_id': request_id})
            if not request:
                bot.answer_callback_query(call.id, "❌ Request not found!")
                return
                
            user_id = request['user_id']
            
            # Update registration status
            if action == 'approve':
                db.users.update_one(
                    {'user_id': user_id},
                    {
                        '$set': {
                            'registration_status': 'approved',
                            'approved_by': admin_id,
                            'role': Role.MEMBER.name.lower()
                        }
                    }
                )
                db.registration_requests.update_one(
                    {'_id': request_id},
                    {'$set': {'status': 'approved'}}
                )
                
                # Notify user
                notify_user(
                    bot,
                    user_id,
                    NotificationType.REGISTRATION_APPROVED,
                    issuer_id=admin_id
                )
            else:
                db.registration_requests.update_one(
                    {'_id': request_id},
                    {'$set': {'status': 'rejected'}}
                )
                
                # Notify user
                notify_user(
                    bot,
                    user_id,
                    NotificationType.REGISTRATION_REJECTED,
                    issuer_id=admin_id
                )
            
            # Update message
            status = '✅ Approved' if action == 'approve' else '❌ Rejected'
            bot.edit_message_text(
                f"{call.message.text}\n\n{status} by admin.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id, f"Registration {action}d successfully!")
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)}")