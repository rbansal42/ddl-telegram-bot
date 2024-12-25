# Standard library imports
import os
from typing import Optional, List

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, CallbackQuery

# Local application imports
from src.database.mongo_db import MongoDB
from src.middleware.auth import check_admin_or_owner
from src.services.google.drive_service import GoogleDriveService
from src.utils.pagination import paginate_items
from src.utils.markup_helpers import create_navigation_markup
from src.utils.message_helpers import split_and_send_messages
from src.utils.drive_formatters import format_drive_items

def sort_items_by_date(items: List[dict]) -> List[dict]:
    """Sort items by their name which contains date in descending order (latest first)"""
    return sorted(items, key=lambda x: x['name'], reverse=True)

def register_list_events_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService):
    """Register event listing related command handlers"""

    @bot.message_handler(commands=['listevents'])
    @check_admin_or_owner(bot, db)
    def list_events_folder(message, page: int = 1):
        """List contents of the events folder with pagination"""
        try:
            root_folder_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
            if not root_folder_id:
                bot.reply_to(message, "❌ Root folder ID is not configured.")
                return
            
            items = drive_service.list_files(folder_id=root_folder_id, recursive=False)
            if not items:
                bot.reply_to(message, "📝 No items found in the events folder.")
                return

            # Sort items by date (latest first)
            sorted_items = sort_items_by_date(items)
            
            pagination_data = paginate_items(sorted_items, page)
            response = f"📂 *Events Folder Contents (Page {pagination_data['page']}/{pagination_data['total_pages']}):*\n\n"
            response += format_drive_items(pagination_data['current_items'])

            markup = create_navigation_markup(
                pagination_data['page'],
                pagination_data['total_pages'],
                'listeventsfolder'
            )

            split_and_send_messages(bot, message, response, markup=markup)

        except Exception as e:
            bot.reply_to(message, f"❌ Error listing events folder: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('listeventsfolder_'))
    def handle_list_events_folder_pagination(call):
        """Handle pagination for listeventsfolder command"""
        try:
            _, page_str = call.data.split('_')
            page = int(page_str)
            
            root_folder_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
            items = drive_service.list_files(folder_id=root_folder_id, recursive=False)
            
            # Sort items by date (latest first)
            sorted_items = sort_items_by_date(items)
            
            pagination_data = paginate_items(sorted_items, page)
            response = f"📂 *Events Folder Contents (Page {pagination_data['page']}/{pagination_data['total_pages']}):*\n\n"
            response += format_drive_items(pagination_data['current_items'])

            markup = create_navigation_markup(
                pagination_data['page'],
                pagination_data['total_pages'],
                'listeventsfolder'
            )

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=response,
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=markup
            )
            
            bot.answer_callback_query(call.id)

        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    return {
        'list_events_folder': list_events_folder,
        'handle_list_events_folder_pagination': handle_list_events_folder_pagination
    }
