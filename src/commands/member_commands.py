# Standard library imports
import os

# Third-party imports
from telebot import TeleBot, types

# Local application imports
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_admin_or_owner
from src.utils.markup_helpers import create_member_list_markup

def register_member_handlers(bot: TeleBot):
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
            
            if not member_list:
                bot.reply_to(message, "📝 No registered members found.")
                return
                
            # Create paginated response
            page_size = 10
            total_members = len(member_list)
            total_pages = (total_members + page_size - 1) // page_size
            
            # Get first page members
            start_idx = 0
            end_idx = min(page_size, total_members)
            current_page_members = member_list[start_idx:end_idx]
            
            # Create markup for first page
            markup = create_member_list_markup(current_page_members, 1, total_pages)
            
            bot.reply_to(message, 
                "👥 *Members List*\n",
                reply_markup=markup,
                parse_mode="Markdown")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error listing members: {e}")
            
    @bot.callback_query_handler(func=lambda call: call.data.startswith('members_'))
    def handle_members_navigation(call):
        """Handle member list navigation"""
        try:
            # Debug prints
            print("=== Members Pagination Handler Debug ===")
            print(f"Callback received from user ID: {call.from_user.id}")
            print(f"Callback data: {call.data}")

            # Manual admin or owner check
            user = db.users.find_one({'user_id': call.from_user.id})
            if not user or user.get('role') not in [Role.ADMIN.name.lower(), Role.OWNER.name.lower()]:
                print(f"Access denied for user {call.from_user.id}")
                bot.answer_callback_query(call.id, "⛔️ This command is only available to admins and owner.")
                return

            print("Admin or Owner verified, proceeding with pagination")

            # Extract the requested page number from callback_data
            _, page_str = call.data.split('_')
            page = int(page_str)
            print(f"Requested page: {page}")

            # Retrieve members
            members = list(db.users.find({
                'registration_status': 'approved',
                'role': Role.MEMBER.name.lower()
            }))
            if not members:
                bot.answer_callback_query(call.id, "📝 No members found.")
                return

            # Pagination settings
            page_size = 10
            total_members = len(members)
            total_pages = (total_members + page_size - 1) // page_size

            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages

            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            current_members = members[start_idx:end_idx]

            # Build the response message
            response = f"👥 *Members List (Page {page}/{total_pages}):*\n\n"
            for member in current_members:
                response += (
                    f"• ID: `{member['user_id']}`\n"
                    f"  Username: @{member.get('username', 'N/A')}\n"
                    f"  Name: {member.get('first_name', '')} {member.get('last_name', '')}\n\n"
                )

            # Create navigation markup
            markup = types.InlineKeyboardMarkup()
            buttons = []

            if page > 1:
                buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"members_{page-1}"))
            if page < total_pages:
                buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"members_{page+1}"))

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
            print(f"Error in members pagination handler: {str(e)}")
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}") 