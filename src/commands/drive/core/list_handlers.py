# Standard library imports
import os
from typing import Optional
import re

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, CallbackQuery
import logging

# Local application imports
from src.database.mongo_db import MongoDB
from src.middleware.auth import check_admin_or_owner
from src.services.drive_service import GoogleDriveService
from src.utils.pagination import paginate_items
from src.utils.markup_helpers import create_navigation_markup
from src.utils.message_helpers import split_and_send_messages
from src.utils.drive_formatters import format_drive_items
from src.utils.user_actions import log_action, ActionType
from src.utils.message_helpers import escape_markdown

logger = logging.getLogger(__name__)

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

    @bot.message_handler(commands=['folderstats'])
    def get_folder_stats(message):
        """Get statistics about a Google Drive folder"""
        try:
            # Ask for folder URL
            msg = bot.reply_to(
                message,
                "📊 Please send the Google Drive folder URL to get its statistics."
            )
            
            # Register the next step handler
            bot.register_next_step_handler(msg, process_folder_stats)
            
            log_action(
                ActionType.COMMAND_START,
                message.from_user.id,
                metadata={'command': 'folderstats'}
            )

        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'folderstats'}
            )

    def process_folder_stats(message):
        """Process the folder URL and show stats"""
        try:
            # Extract folder ID from URL
            folder_id = extract_folder_id(message.text)
            if not folder_id:
                bot.reply_to(
                    message,
                    "❌ Invalid folder link. Please send a valid Google Drive folder link."
                )
                return

            # Send processing message
            status_msg = bot.reply_to(message, "🔍 Analyzing folder contents...")

            # Get folder details
            bot.edit_message_text(
                "🔍 Getting folder details...",
                status_msg.chat.id,
                status_msg.message_id
            )
            folder_details = drive_service.get_folder_details(folder_id)
            folder_name = folder_details.get('name', 'Unknown Folder')

            # Get folder stats for media files
            bot.edit_message_text(
                "🔍 Analyzing media files...\n"
                f"📁 Folder: {folder_name}",
                status_msg.chat.id,
                status_msg.message_id
            )
            media_stats = drive_service.get_folder_stats(folder_id)
            
            # Get total folder size (all files)
            bot.edit_message_text(
                "🔍 Calculating total folder size...\n"
                f"📁 Folder: {folder_name}",
                status_msg.chat.id,
                status_msg.message_id
            )
            total_size = drive_service.get_folder_size(folder_id)

            # Format sizes
            def format_size(size_bytes):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size_bytes < 1024:
                        return f"{size_bytes:.1f} {unit}"
                    size_bytes /= 1024
                return f"{size_bytes:.1f} TB"

            bot.edit_message_text(
                "📊 Preparing statistics...\n"
                f"📁 Folder: {folder_name}",
                status_msg.chat.id,
                status_msg.message_id
            )

            # Create response
            if media_stats['success']:
                media_files = media_stats['files']
                
                # Group files by type
                type_stats = {}
                for file in media_files:
                    file_type = file['mimeType'].split('/')[-1].upper()
                    if file_type not in type_stats:
                        type_stats[file_type] = {
                            'count': 0,
                            'size': 0
                        }
                    type_stats[file_type]['count'] += 1
                    type_stats[file_type]['size'] += int(file.get('size', 0))

                # Create response
                response = (
                    f"📊 *Folder Statistics*\n\n"
                    f"*Folder:* `{escape_markdown(folder_name)}`\n\n"
                    f"*Media Files:*\n"
                )

                # Add stats for each media type
                for file_type, stats in type_stats.items():
                    response += (
                        f"• {file_type}: "
                        f"`{stats['count']} files` "
                        f"\\({escape_markdown(format_size(stats['size']))}\\)\n"
                    )

                # Add total stats
                response += (
                    f"\n*Total Media:* `{media_stats['total_files']} files` "
                    f"\\({escape_markdown(format_size(media_stats['total_size']))}\\)\n"
                    f"*Total Folder Size:* `{escape_markdown(format_size(total_size))}`"
                )

            else:
                response = (
                    f"📊 *Folder Statistics*\n\n"
                    f"*Folder:* `{escape_markdown(folder_name)}`\n"
                    f"*Total Size:* `{escape_markdown(format_size(total_size))}`\n\n"
                    f"❌ Error getting media stats: {escape_markdown(media_stats['error'])}"
                )

            # Update the status message with results
            bot.edit_message_text(
                response,
                status_msg.chat.id,
                status_msg.message_id,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )

            log_action(
                ActionType.COMMAND_SUCCESS,
                message.from_user.id,
                metadata={
                    'command': 'folderstats',
                    'folder_id': folder_id,
                    'folder_name': folder_name
                }
            )

        except Exception as e:
            bot.reply_to(message, f"❌ Error analyzing folder: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'folderstats'}
            )

    # Add extract_folder_id function from media_copy
    def extract_folder_id(url: str) -> Optional[str]:
        """Extract Google Drive folder ID from URL"""
        patterns = [
            r'folders/([a-zA-Z0-9-_]+)',  # matches folders/FOLDER_ID
            r'id=([a-zA-Z0-9-_]+)',       # matches id=FOLDER_ID
            r'open\?id=([a-zA-Z0-9-_]+)'  # matches open?id=FOLDER_ID
        ]
        
        logger.debug(f"Attempting to extract folder ID from URL: {url}")
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                folder_id = match.group(1)
                logger.info(f"Successfully extracted folder ID: {folder_id}")
                return folder_id
        logger.warning("No folder ID found in URL")
        return None

    # Register the command
    bot.message_handler(commands=['folderstats'])(get_folder_stats)

    return {
        'list_team_drive_contents': list_team_drive_contents,
        'list_drives': list_drives,
        'handle_list_pagination': handle_list_pagination
    } 