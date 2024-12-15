# Standard library imports
from typing import Optional

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Local application imports
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_admin_or_owner
from src.utils.notifications import notify_user, NotificationType
from src.utils.user_actions import log_action, ActionType

def register_admin_handlers(bot: TeleBot, db: MongoDB):
    """Register all admin management related command handlers"""

    def promote_to_admin(bot: TeleBot, db: MongoDB, chat_id: int, member_id: int) -> None:
        """Helper function to promote a member to admin"""
        user = db.users.find_one({'user_id': member_id})
        
        if not user:
            raise Exception("User not found.")
        
        if user.get('role') == Role.ADMIN.name.lower():
            raise Exception("User is already an admin.")
            
        if user.get('role') != Role.MEMBER.name.lower():
            raise Exception("Only members can be promoted to admin.")
            
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

    def demote_to_member(bot: TeleBot, db: MongoDB, chat_id: int, admin_id: int) -> None:
        """Helper function to demote an admin to member"""
        user = db.users.find_one({'user_id': admin_id})
        
        if not user:
            raise Exception("User not found.")
        
        if user.get('role') != Role.ADMIN.name.lower():
            raise Exception("User is not an admin.")
            
        db.users.update_one(
            {'user_id': admin_id},
            {'$set': {'role': Role.MEMBER.name.lower()}}
        )
        
        bot.send_message(chat_id, f"✅ Admin {admin_id} has been demoted to member.")
        
        try:
            notify_user(
                bot,
                NotificationType.DEMOTION_TO_MEMBER,
                admin_id,
                issuer_id=chat_id
            )
        except Exception as e:
            print(f"Failed to notify demoted admin: {e}")

    @bot.message_handler(commands=['addadmin'])
    @check_admin_or_owner(bot, db)
    def add_admin(message: Message) -> None:
        """Add a new admin user"""
        try:
            args = message.text.split()
            if len(args) == 1:  # No user_id provided
                members_query = {
                    'registration_status': 'approved',
                    'role': Role.MEMBER.name.lower()
                }
                
                members = db.users.find(members_query)
                member_list = list(members)
                
                if not member_list:
                    bot.reply_to(message, "📝 No registered members found to promote.")
                    return

                markup = InlineKeyboardMarkup()
                for member in member_list:
                    full_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() or 'N/A'
                    email = member.get('email', 'N/A')
                    user_id = member.get('user_id')
                    
                    markup.add(
                        InlineKeyboardButton(
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
    @check_admin_or_owner(bot, db)
    def remove_admin(message: Message) -> None:
        """Remove an admin user"""
        try:
            args = message.text.split()
            if len(args) == 1:  # No user_id provided
                admins = db.users.find({'role': Role.ADMIN.name.lower()})
                admin_list = list(admins)
                
                if not admin_list:
                    bot.reply_to(message, "📝 No admins found to demote.")
                    return

                markup = InlineKeyboardMarkup()
                for admin in admin_list:
                    full_name = f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip() or 'N/A'
                    email = admin.get('email', 'N/A')
                    user_id = admin.get('user_id')
                    
                    markup.add(
                        InlineKeyboardButton(
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith('promote_'))
    def handle_admin_promotion(call: CallbackQuery) -> None:
        """Handle member promotion to admin"""
        try:
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith('demote_'))
    def handle_admin_demotion(call: CallbackQuery) -> None:
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

    @bot.message_handler(commands=['listadmins'])
    @check_admin_or_owner(bot, db)
    def list_admins(message: Message, page: int = 1) -> None:
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
            markup = InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"listadmins_{page-1}"))
            if page < total_pages:
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"listadmins_{page+1}"))

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
    def handle_list_admins_pagination(call: CallbackQuery) -> None:
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