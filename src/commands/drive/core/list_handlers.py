# Standard library imports
import os
from typing import Optional

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, CallbackQuery

# Local application imports
from src.database.mongo_db import MongoDB
from src.middleware.auth import check_admin_or_owner
from src.services.drive_service import GoogleDriveService
from src.utils.pagination import paginate_items
from src.utils.markup_helpers import create_navigation_markup
from src.utils.message_helpers import split_and_send_messages
from src.utils.drive_formatters import format_drive_items
from src.utils.user_actions import log_action, ActionType

def register_list_handlers(bot: TeleBot, drive_service: GoogleDriveService, db: MongoDB):
    """Register all list-related handlers"""

    @bot.message_handler(commands=['listteamdrive'])
    @check_admin_or_owner(bot, db)
    def list_team_drive_contents(message, page: int = 1):
        """List all files and folders in the Team Drive with pagination"""
        try:
            files = list(drive_service.list_team_drive_contents())
            if not files:
                bot.reply_to(message, "📂 No files or folders found in Team Drive.")
                return

            pagination_data = paginate_items(files, page)
            response = f"📂 *Team Drive Contents (Page {pagination_data['page']}/{pagination_data['total_pages']}):*\n\n"
            response += format_drive_items(pagination_data['current_items'])

            markup = create_navigation_markup(
                pagination_data['page'],
                pagination_data['total_pages'],
                'listteamdrive'
            )

            split_and_send_messages(bot, message, response, markup=markup)

        except Exception as e:
            bot.reply_to(message, f"❌ Error listing Team Drive contents: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'listteamdrive'}
            )

    @bot.message_handler(commands=['listdrives'])
    @check_admin_or_owner(bot, db)
    def list_drives(message, page: int = 1):
        """List all shared drives with pagination"""
        try:
            log_action(
                ActionType.COMMAND_START,
                message.from_user.id,
                metadata={'command': 'listdrives', 'page': page}
            )

            drives = list(drive_service.list_drives())
            if not drives:
                bot.reply_to(message, "📂 No drives found.")
                log_action(
                    ActionType.COMMAND_SUCCESS, 
                    message.from_user.id,
                    metadata={'command': 'listdrives', 'result': 'no_drives_found'}
                )
                return

            pagination_data = paginate_items(drives, page)
            response = f"📂 *Drive List (Page {pagination_data['page']}/{pagination_data['total_pages']}):*\n\n"
            
            for drive in pagination_data['current_items']:
                response += (
                    f"• *Name:* {drive['name']}\n"
                    f"  *ID:* `{drive['id']}`\n"
                    f"  *Type:* `{drive['type']}`\n\n"
                )

            markup = create_navigation_markup(
                pagination_data['page'],
                pagination_data['total_pages'],
                'listdrives'
            )
            split_and_send_messages(bot, message, response, markup=markup)

            log_action(
                ActionType.COMMAND_SUCCESS,
                message.from_user.id,
                metadata={
                    'command': 'listdrives',
                    'page': page,
                    'total_drives': len(drives),
                    'total_pages': pagination_data['total_pages']
                }
            )

        except Exception as e:
            bot.reply_to(message, f"❌ Error listing drives: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'listdrives'}
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('listteamdrive_', 'listdrives_')))
    def handle_list_pagination(call):
        """Handle pagination for list commands"""
        try:
            command, page_str = call.data.split('_')
            page = int(page_str)
            
            if command == 'listteamdrive':
                items = list(drive_service.list_team_drive_contents())
                title = "Team Drive Contents"
                format_func = format_drive_items
            else:  # listdrives
                items = list(drive_service.list_drives())
                title = "Drive List"
                format_func = lambda drives: '\n'.join(
                    f"• *Name:* {d['name']}\n  *ID:* `{d['id']}`\n  *Type:* `{d['type']}`\n"
                    for d in drives
                )

            pagination_data = paginate_items(items, page)
            response = f"📂 *{title} (Page {pagination_data['page']}/{pagination_data['total_pages']}):*\n\n"
            response += format_func(pagination_data['current_items'])

            markup = create_navigation_markup(
                pagination_data['page'],
                pagination_data['total_pages'],
                command
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
        'list_team_drive_contents': list_team_drive_contents,
        'list_drives': list_drives,
        'handle_list_pagination': handle_list_pagination
    } 