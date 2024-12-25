from datetime import datetime, timedelta
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.database.mongo_db import MongoDB
from src.services.drive_service import GoogleDriveService
from src.utils.message_helpers import escape_markdown
from src.utils.user_actions import log_action, ActionType
from src.utils.state_management import UserStateManager
from src.utils.file_helpers import get_file_info, format_file_size
from src.utils.file_handler import TempFileHandler
from telebot.handler_backends import State, StatesGroup
from typing import Dict, List
import time
import logging

logger = logging.getLogger(__name__)
CMD_UPLOAD_TO_EVENT = 'upload_to_event'

class UploadStates(StatesGroup):
    selecting_event = State()
    uploading = State()

class UploadManager:
    def __init__(self, bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
        self.bot = bot
        self.db = db
        self.drive_service = drive_service
        self.state_manager = state_manager
        self.temp_handler = TempFileHandler()
        self.ITEMS_PER_PAGE = 5
        self.register_handlers()

    def register_handlers(self):
        """Register all handlers"""
        # Command handler
        self.bot.message_handler(commands=[CMD_UPLOAD_TO_EVENT])(self.handle_upload_to_event)
        
        # Callback handlers
        self.bot.callback_query_handler(func=lambda call: call.data.startswith('upload_event_'))(self.handle_event_selection)
        self.bot.callback_query_handler(func=lambda call: call.data.startswith('upload_page_'))(self.handle_upload_pagination)
        self.bot.callback_query_handler(func=lambda call: call.data == 'status_info')(self.handle_status_info)
        self.bot.callback_query_handler(func=lambda call: call.data in ['upload_done', 'upload_cancel'])(self.handle_upload_action)
        
        # File upload handler
        self.bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])(self.handle_file_upload)

    def create_status_markup(self, user_id: int) -> InlineKeyboardMarkup:
        """Create status message markup"""
        file_count, total_size = self.state_manager.get_upload_stats(user_id)
        size_str = format_file_size(total_size)
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(
            f"📥 {file_count} files received ({size_str})",
            callback_data="status_info"
        ))
        markup.row(
            InlineKeyboardButton("✅ Done", callback_data="upload_done"),
            InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")
        )
        return markup

    def handle_upload_to_event(self, message: Message):
        """Handle /upload_to_event command"""
        try:
            user_id = message.from_user.id
            logger.info(f"Upload to event command received from user {user_id}")

            # Get events from drive
            events = self.drive_service.list_events()
            if not events:
                logger.warning("No events found")
                self.bot.reply_to(message, "❌ No events found. Please create an event first.")
                return

            # Sort events by name (newest first)
            events = sorted(events, key=lambda x: x['name'], reverse=True)
            self.show_event_list(message, events)

        except Exception as e:
            logger.error(f"Error in handle_upload_to_event: {str(e)}", exc_info=True)
            self.bot.reply_to(message, f"❌ Error: {str(e)}")

    def show_event_list(self, message: Message | CallbackQuery, events: List[Dict], page: int = 0):
        """Show paginated list of events"""
        try:
            is_new_message = isinstance(message, Message)
            chat_id = message.chat.id if is_new_message else message.message.chat.id
            message_id = None if is_new_message else message.message.message_id

            # Calculate pagination
            total_pages = (len(events) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
            page = max(0, min(page, total_pages - 1))
            start_idx = page * self.ITEMS_PER_PAGE
            end_idx = start_idx + self.ITEMS_PER_PAGE
            current_events = events[start_idx:end_idx]

            # Create markup
            markup = InlineKeyboardMarkup(row_width=1)
            
            # Add event buttons
            for event in current_events:
                markup.add(InlineKeyboardButton(
                    event['name'],
                    callback_data=f"upload_event_{event['id']}"
                ))

            # Add navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"upload_page_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"upload_page_{page+1}"))
            if nav_buttons:
                markup.row(*nav_buttons)

            # Add cancel button
            markup.row(InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel"))

            # Create message text
            text = (
                "📤 *Select Event to Upload Media*\n\n"
                "Choose an event to upload media files to:\n\n"
                f"(Showing {start_idx+1}-{min(end_idx, len(events))} of {len(events)} events)"
            )

            # Send or edit message
            if is_new_message:
                self.bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)
            else:
                self.bot.edit_message_text(
                    text,
                    chat_id,
                    message_id,
                    parse_mode="Markdown",
                    reply_markup=markup
                )

        except Exception as e:
            logger.error(f"Error showing event list: {str(e)}", exc_info=True)
            error_msg = f"❌ Error: {str(e)}"
            if is_new_message:
                self.bot.reply_to(message, error_msg)
            else:
                self.bot.edit_message_text(error_msg, chat_id, message_id)

    def handle_event_selection(self, call: CallbackQuery):
        """Handle event selection"""
        try:
            user_id = call.from_user.id
            logger.info(f"Event selection from user {user_id}")
            
            event_id = call.data.split('_')[2]
            logger.info(f"Selected event ID: {event_id}")
            
            # Get event details
            events = self.drive_service.list_events()
            event = next((e for e in events if e['id'] == event_id), None)
            
            if not event:
                logger.warning(f"Event {event_id} not found")
                self.bot.answer_callback_query(call.id, "❌ Event not found")
                return

            # Set upload state
            state_data = {
                'state': 'upload_mode',
                'folder_id': event['id'],
                'folder_name': event['name'],
                'upload_expires_at': datetime.now() + timedelta(minutes=60)
            }
            logger.info(f"Setting state for user {user_id}: {state_data}")
            self.state_manager.set_state(user_id, state_data)

            # Send instructions
            self.bot.edit_message_text(
                f"📤 *Upload Files to {escape_markdown(event['name'])}*\n\n"
                "You can now upload files to this event:\n"
                "• Send any documents, photos, videos, or audio files\n"
                "• Multiple files can be uploaded\n"
                "• Session expires in 60 minutes\n\n"
                "Press *Done* when finished or *Cancel* to stop uploading.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="MarkdownV2",
                reply_markup=self.create_status_markup(user_id)
            )
            
            self.bot.answer_callback_query(call.id)
            logger.info("Event selection completed")

        except Exception as e:
            logger.error(f"Error in event selection: {str(e)}", exc_info=True)
            self.bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    def handle_upload_pagination(self, call: CallbackQuery):
        """Handle pagination for event list"""
        try:
            page = int(call.data.split('_')[2])
            events = self.drive_service.list_events()
            events = sorted(events, key=lambda x: x['name'], reverse=True)
            self.show_event_list(call, events, page)
            self.bot.answer_callback_query(call.id)
        except Exception as e:
            logger.error(f"Error in pagination: {str(e)}", exc_info=True)
            self.bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    def handle_status_info(self, call: CallbackQuery):
        """Handle status info button click"""
        logger.info(f"Status info requested by user {call.from_user.id}")
        self.bot.answer_callback_query(
            call.id,
            "These files will be uploaded when you press Done"
        )

    def handle_upload_action(self, call: CallbackQuery):
        """Handle upload actions (done/cancel)"""
        user_id = call.from_user.id
        action = call.data.split('_')[1]
        logger.info(f"Upload action {action} from user {user_id}")
        
        if action == 'cancel':
            self.temp_handler.cleanup_session(user_id)
            self.state_manager.clear_state(user_id)
            self.bot.edit_message_text(
                "❌ Upload cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            return

        if action == 'done':
            self.process_uploads(call)

    def handle_file_upload(self, message: Message):
        """Handle file uploads"""
        user_id = message.from_user.id
        logger.info(f"File upload from user {user_id}")
        
        user_state = self.state_manager.get_state(user_id)
        if not user_state or not user_state.get('upload_mode'):
            logger.info(f"User {user_id} not in upload mode")
            return

        if datetime.now() > user_state.get('upload_expires_at', datetime.now()):
            logger.warning(f"Upload session expired for user {user_id}")
            self.bot.reply_to(message, "⏰ Upload session expired. Please start a new upload.")
            self.state_manager.clear_state(user_id)
            self.temp_handler.cleanup_session(user_id)
            return

        try:
            self.process_uploaded_file(message)
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}", exc_info=True)
            self.bot.reply_to(message, f"❌ Error processing file: {str(e)}")

    def process_uploaded_file(self, message: Message):
        """Process an uploaded file"""
        user_id = message.from_user.id
        file_type, file_name, file_size = get_file_info(message)
        logger.info(f"Processing file: {file_name}")

        # Get file info
        if message.document:
            file_info = self.bot.get_file(message.document.file_id)
            size_bytes = message.document.file_size
        elif message.photo:
            file_info = self.bot.get_file(message.photo[-1].file_id)
            size_bytes = file_info.file_size
        elif message.video:
            file_info = self.bot.get_file(message.video.file_id)
            size_bytes = message.video.file_size
        elif message.audio:
            file_info = self.bot.get_file(message.audio.file_id)
            size_bytes = message.audio.file_size

        # Save file
        temp_path = self.temp_handler.save_telegram_file(
            self.bot,
            file_info,
            file_name,
            user_id
        )

        # Add to pending uploads
        self.state_manager.add_pending_upload(user_id, {
            'name': file_name,
            'size': file_size,
            'size_bytes': size_bytes,
            'type': file_type,
            'path': temp_path
        })

        # Update status message
        user_state = self.state_manager.get_state(user_id)
        if not user_state.get('status_message_id'):
            status_msg = self.bot.send_message(
                message.chat.id,
                "📤 *Upload Session Active*\n"
                "Send files to upload or press Done when finished.",
                parse_mode="Markdown",
                reply_markup=self.create_status_markup(user_id)
            )
            user_state['status_message_id'] = status_msg.message_id
            self.state_manager.set_state(user_id, user_state)
        else:
            self.bot.edit_message_reply_markup(
                message.chat.id,
                user_state['status_message_id'],
                reply_markup=self.create_status_markup(user_id)
            )

    def process_uploads(self, call: CallbackQuery):
        """Process all pending uploads"""
        user_id = call.from_user.id
        user_state = self.state_manager.get_state(user_id)
        pending_uploads = self.state_manager.get_pending_uploads(user_id)

        if not pending_uploads:
            self.bot.edit_message_text(
                "❌ No files to upload.",
                call.message.chat.id,
                call.message.message_id
            )
            self.state_manager.clear_state(user_id)
            return

        try:
            folder_id = user_state['folder_id']
            folder_name = user_state['folder_name']
            total_files = len(pending_uploads)
            uploaded_files = []

            # Update status message
            status_text = (
                f"⏳ *Processing Uploads*\n\n"
                f"Preparing to upload {total_files} files to {escape_markdown(folder_name)}\n"
                f"Please wait..."
            )
            self.bot.edit_message_text(
                status_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="MarkdownV2"
            )

            # Upload files
            for index, file in enumerate(pending_uploads, 1):
                progress = (index / total_files) * 100
                progress_bar = "▓" * int(progress/5) + "░" * (20-int(progress/5))
                
                status_text = (
                    f"⏳ *Uploading Files*\n\n"
                    f"Progress: `[{progress_bar}]` {progress:.1f}%\n"
                    f"File {index}/{total_files}: `{escape_markdown(file['name'])}`"
                )
                
                self.bot.edit_message_text(
                    status_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="MarkdownV2"
                )

                # Upload file
                with open(file['path'], 'rb') as f:
                    uploaded_file = self.drive_service.upload_file(
                        f.read(),
                        file['name'],
                        folder_id
                    )
                    uploaded_files.append({
                        **file,
                        'web_link': uploaded_file['webViewLink']
                    })

            # Show completion message
            total_size = format_file_size(sum(f['size_bytes'] for f in uploaded_files))
            summary = "*Successfully Uploaded Files:*\n"
            for file in uploaded_files:
                emoji = {
                    'document': '📄',
                    'photo': '🖼',
                    'video': '🎥',
                    'audio': '🎵'
                }.get(file['type'], '📁')
                summary += f"{emoji} [{escape_markdown(file['name'])}]({escape_markdown(file['web_link'])}) - {escape_markdown(file['size'])}\n"
            summary += f"\n*Total Size:* {escape_markdown(total_size)}"

            self.bot.edit_message_text(
                f"✅ *Upload Complete!*\n\n{summary}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )

            # Log action
            log_action(
                ActionType.FILES_UPLOADED,
                user_id,
                metadata={
                    'folder_name': folder_name,
                    'file_count': len(uploaded_files),
                    'total_size': sum(f['size_bytes'] for f in uploaded_files)
                }
            )

            # Cleanup
            self.temp_handler.cleanup_session(user_id)
            self.state_manager.clear_state(user_id)

        except Exception as e:
            logger.error(f"Error processing uploads: {str(e)}", exc_info=True)
            self.bot.edit_message_text(
                f"❌ Error uploading files: {str(e)}",
                call.message.chat.id,
                call.message.message_id
            )
            log_action(
                ActionType.UPLOAD_FAILED,
                user_id,
                error_message=str(e)
            )

def register_upload_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
    """Register upload handlers"""
    upload_manager = UploadManager(bot, db, drive_service, state_manager)
    return {
        'handle_file_upload': upload_manager.handle_file_upload,
        'handle_upload_action': upload_manager.handle_upload_action,
        'handle_upload_to_event': upload_manager.handle_upload_to_event,
        'handle_upload_pagination': upload_manager.handle_upload_pagination,
        'handle_event_selection': upload_manager.handle_event_selection
    }
