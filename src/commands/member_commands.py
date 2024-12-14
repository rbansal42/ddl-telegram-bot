import os
from telebot import TeleBot, types
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