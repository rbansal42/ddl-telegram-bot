# Standard library imports
import os

# Third-party imports
from telebot import TeleBot, types

# Local application imports
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_admin_or_owner
from src.utils.notifications import notify_user, NotificationType
from src.utils.user_actions import log_action, ActionType
from src.utils.markup_helpers import create_navigation_markup
from src.utils.pagination import paginate_items

def register_member_management_handlers(bot: TeleBot, db: MongoDB):
    
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
                
    @bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
    @check_admin_or_owner(bot, db)
    def handle_remove_member(call):
        """Handle member removal confirmation"""
        try:
            # Get the ID of who initiated the command
            admin_id = call.from_user.id
            user_id = int(call.data.split('_')[1])
            member = db.users.find_one({'user_id': user_id})
            
            if not member:
                bot.answer_callback_query(call.id, "❌ Member not found!")
                return
                
            # Create confirmation markup
            markup = types.InlineKeyboardMarkup()
            confirm_button = types.InlineKeyboardButton(
                "✅ Confirm Remove", callback_data=f"confirmremove_{user_id}_{admin_id}")
            cancel_button = types.InlineKeyboardButton(
                "❌ Cancel", callback_data=f"cancelremove_{admin_id}")
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
    @check_admin_or_owner(bot, db)
    def handle_remove_confirmation(call):
        """Handle final member removal"""
        try:
            # Extract both user_id and admin_id from callback data
            _, user_id, admin_id = call.data.split('_')
            user_id = int(user_id)
            admin_id = int(admin_id)  # This is the original admin who initiated the removal
            
            member = db.users.find_one({'user_id': user_id})
            
            if not member:
                bot.answer_callback_query(call.id, "❌ Member not found!")
                return
            
            # Remove member
            db.users.delete_one({'user_id': user_id})
            
            # Notify the removed member using the correct admin_id
            try:
                notify_user(
                    bot,
                    NotificationType.ACCESS_REVOKED,
                    user_id,
                    f"You have been removed from the system."
                )
            except Exception as e:
                pass
            
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


    @bot.callback_query_handler(func=lambda call: call.data.startswith('listadmins_'))
    def handle_list_admins_pagination(call):
        """Handle pagination for listadmins command"""
        try:
            # Manual admin or owner check
            user = db.users.find_one({'user_id': call.from_user.id})
            if not user or user.get('role') not in [Role.ADMIN.name.lower(), Role.OWNER.name.lower()]:
                bot.answer_callback_query(call.id, "⛔️ This command is only available to admins and owner.")
                return

            # Extract the requested page number from callback_data
            _, page_str = call.data.split('_')
            page = int(page_str)

            # Retrieve admins
            admins = list(db.users.find({'role': Role.ADMIN.name.lower()}))
            if not admins:
                bot.answer_callback_query(call.id, "📝 No admins found.")
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
            bot.answer_callback_query(call.id, "❌ Invalid page number.")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")