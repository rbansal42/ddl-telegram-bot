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

def register_upload_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
    temp_handler = TempFileHandler()
    ITEMS_PER_PAGE = 5
    
    def create_status_markup(user_id: int):
        file_count, total_size = state_manager.get_upload_stats(user_id)
        size_str = format_file_size(total_size)
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(
            f"📥 {file_count} files received ({size_str})",
            callback_data="status_info"
        ))
        markup.row(
            InlineKeyboardButton("✅ Done", callback_data="upload_done"),
            InlineKeyboardButton("❌ Cancel Upload", callback_data="upload_cancel")
        )
        return markup

    def update_status_message(chat_id: int, message_id: int, user_id: int):
        try:
            bot.edit_message_reply_markup(
                chat_id,
                message_id,
                reply_markup=create_status_markup(user_id)
            )
        except Exception as e:
            print(f"[DEBUG] Error updating status message: {str(e)}")

    def update_progress_message(bot, chat_id, message_id, user_id, state_manager):
        completed_count, total_count, completed_size, total_size = state_manager.get_upload_progress(user_id)
        progress_percent = (completed_size / total_size * 100) if total_size > 0 else 0
        completed_size_str = format_file_size(completed_size)
        total_size_str = format_file_size(total_size)
        
        progress_bar = "▓" * int(progress_percent/10) + "░" * (10-int(progress_percent/10))
        
        message = (
            f"⏳ *Uploading Files*\n\n"
            f"Progress: [{progress_bar}] {progress_percent:.1f}%\n"
            f"Files: {completed_count}/{total_count}\n"
            f"Size: {completed_size_str}/{total_size_str}"
        )
        
        bot.edit_message_text(
            message,
            chat_id,
            message_id,
            parse_mode="Markdown"
        )

    @bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
    def handle_file_upload(message):
        user_id = message.from_user.id
        user_state = state_manager.get_state(user_id)
        
        if not user_state.get('upload_mode'):
            return
            
        if datetime.now() > user_state.get('upload_expires_at', datetime.now()):
            bot.reply_to(
                message, 
                "⏰ Upload session has expired.\nPlease create a new event folder to upload files."
            )
            state_manager.clear_state(user_id)
            temp_handler.cleanup_session(user_id)
            return
        
        try:
            file_type, file_name, file_size = get_file_info(message)
            
            # Get file info and size in bytes
            if message.document:
                file_info = bot.get_file(message.document.file_id)
                size_bytes = message.document.file_size
            elif message.photo:
                file_info = bot.get_file(message.photo[-1].file_id)
                size_bytes = file_info.file_size
            elif message.video:
                file_info = bot.get_file(message.video.file_id)
                size_bytes = message.video.file_size
            elif message.audio:
                file_info = bot.get_file(message.audio.file_id)
                size_bytes = message.audio.file_size
            
            # Save file locally
            temp_path = temp_handler.save_telegram_file(
                bot, 
                file_info, 
                file_name, 
                user_id
            )
            
            # Add to pending uploads with size in bytes
            state_manager.add_pending_upload(user_id, {
                'name': file_name,
                'size': file_size,
                'size_bytes': size_bytes,
                'type': file_type,
                'path': temp_path
            })
            
            # Create or update status message
            if not user_state.get('status_message_id'):
                status_msg = bot.send_message(
                    message.chat.id,
                    "📤 *Upload Session Active*\n"
                    "Send files to upload or press Done when finished.",
                    parse_mode="Markdown",
                    reply_markup=create_status_markup(user_id)
                )
                user_state['status_message_id'] = status_msg.message_id
                state_manager.set_state(user_id, user_state)
            else:
                update_status_message(
                    message.chat.id,
                    user_state['status_message_id'],
                    user_id
                )
            
        except Exception as e:
            print(f"[DEBUG] Error during file upload: {str(e)}")
            bot.reply_to(message, f"❌ Failed to process file: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data == "status_info")
    def handle_status_info(call: CallbackQuery):
        bot.answer_callback_query(
            call.id,
            "These files will be uploaded when you press Done"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('upload_'))
    def handle_upload_action(call: CallbackQuery):
        user_id = call.from_user.id
        action = call.data.split('_')[1]
        print(f"\n[DEBUG] Upload action {action} triggered by user {user_id}")
        user_state = state_manager.get_state(user_id)
        
        if action == 'done':
            pending_uploads = state_manager.get_pending_uploads(user_id)
            
            if not pending_uploads:
                bot.edit_message_text(
                    "❌ No files were uploaded.",
                    call.message.chat.id,
                    call.message.message_id
                )
                state_manager.clear_state(user_id)
                return
            
            try:
                # Update the existing upload session message with progress
                file_count, total_size = state_manager.get_upload_stats(user_id)
                size_str = format_file_size(total_size)
                bot.edit_message_text(
                    f"⏳ *Processing Uploads*\n\n"
                    f"Preparing to upload {file_count} files {escape_markdown(size_str)} to Drive\.\n" 
                    f"Please wait while files are being {escape_markdown('processed.')}",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="MarkdownV2"
                )
                
                # Get folder ID from state
                folder_id = user_state['folder_id']
                folder_name = user_state['folder_name']
                print(f"[DEBUG] Folder ID: {folder_id}, Folder Name: {folder_name}")

                # Initialize progress tracking
                state_manager.set_state(user_id, {
                    **user_state,
                    'completed_uploads': []
                })
                
                # Upload files and update progress in the same message
                uploaded_files = []
                total_files = len(pending_uploads)
                
                for index, file in enumerate(pending_uploads, 1):
                    # Update progress message
                    progress_percent = (index / total_files) * 100
                    progress_bar = "▓" * int(progress_percent/10) + "░" * (10-int(progress_percent/10))
                    
                    status_text = (
                        f"⏳ *Uploading Files*\n\n"
                        f"Progress: `[{escape_markdown(progress_bar)}]` {progress_percent:.1f}%\n"
                        f"File {index}/{total_files}: `{escape_markdown(file['name'])}`\n"
                        f"Total Size: {escape_markdown(size_str)}"
                    )
                    
                    bot.edit_message_text(
                        status_text,
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode="MarkdownV2"
                    )

                    # Upload the file
                    with open(file['path'], 'rb') as f:
                        file_content = f.read()
                        uploaded_file = drive_service.upload_file(
                            file_content,
                            file['name'],
                            folder_id
                        )
                        uploaded_files.append({
                            **file,
                            'web_link': uploaded_file['webViewLink']
                        })
                
                # Format final summary
                total_size = format_file_size(state_manager.get_upload_stats(user_id)[1])
                summary = "*Successfully Uploaded Files:*\n"
                for file in uploaded_files:
                    file_type = file['type']
                    emoji = {
                        'document': '📄',
                        'photo': '🖼',
                        'video': '🎥',
                        'audio': '🎵'
                    }.get(file_type, '📁')
                    summary += f"{emoji} [{escape_markdown(file['name'])}]({escape_markdown(file['web_link'])}) - {escape_markdown(file['size'])}\n"
                summary += f"\n*Total Size:* {escape_markdown(total_size)}"
                
                # Update final message
                bot.edit_message_text(
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
                        'total_size': state_manager.get_upload_stats(user_id)[1]
                    }
                )
                
                # Cleanup
                temp_handler.cleanup_session(user_id)
                state_manager.clear_state(user_id)
                
            except Exception as e:
                bot.edit_message_text(
                    f"❌ Error uploading files: {str(e)}",
                    call.message.chat.id,
                    call.message.message_id
                )
                log_action(
                    ActionType.UPLOAD_FAILED,
                    user_id,
                    error_message=str(e)
                )
        
        elif action == 'cancel':
            temp_handler.cleanup_session(user_id)
            state_manager.clear_state(user_id)
            bot.edit_message_text(
                "��� Upload session cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            log_action(
                ActionType.UPLOAD_CANCELLED,
                user_id
            )

    def handle_upload_to_event(message: Message | CallbackQuery, page: int = 0):
        """Handle the upload to event command with pagination"""
        try:
            is_new_command = isinstance(message, Message)
            user_id = message.from_user.id if is_new_command else message.from_user.id
            logger.info(f"Processing upload to event command from user {user_id}")

            # Get available events from drive service
            events = drive_service.list_events()
            if not events:
                logger.warning("No events found")
                error_text = "❌ No events found. Please create an event first."
                if is_new_command:
                    bot.reply_to(message, error_text)
                else:
                    bot.edit_message_text(error_text, message.message.chat.id, message.message.message_id)
                return

            # Sort events by name in reverse order (latest first)
            events = sorted(events, key=lambda x: x['name'], reverse=True)
            
            # Calculate pagination
            total_pages = (len(events) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            page = max(0, min(page, total_pages - 1))
            start_idx = page * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            current_events = events[start_idx:end_idx]
            
            logger.debug(f"Showing events {start_idx+1}-{min(end_idx, len(events))} of {len(events)}")

            # Create event selection markup
            markup = InlineKeyboardMarkup(row_width=1)
            
            # Add event buttons
            for event in current_events:
                event_name = event['name']
                logger.debug(f"Adding event to markup: {event_name} (ID: {event['id']})")
                markup.add(InlineKeyboardButton(
                    event_name,
                    callback_data=f"upload_event_{event['id']}"
                ))

            # Add pagination buttons if needed
            pagination_buttons = []
            if page > 0:
                pagination_buttons.append(
                    InlineKeyboardButton("⬅️ Previous", callback_data=f"upload_page_{page-1}")
                )
            if page < total_pages - 1:
                pagination_buttons.append(
                    InlineKeyboardButton("➡️ Next", callback_data=f"upload_page_{page+1}")
                )
            if pagination_buttons:
                markup.row(*pagination_buttons)

            # Add cancel button
            markup.row(InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel"))

            message_text = (
                "📤 *Select Event to Upload Media*\n\n"
                "Choose an event to upload media files to:\n\n"
                f"(Showing {start_idx+1}-{min(end_idx, len(events))} of {len(events)} events)"
            )

            if is_new_command:
                bot.reply_to(message, message_text, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.edit_message_text(
                    message_text,
                    message.message.chat.id,
                    message.message.message_id,
                    parse_mode="Markdown",
                    reply_markup=markup
                )

        except Exception as e:
            logger.error(f"Error in handle_upload_to_event: {str(e)}", exc_info=True)
            error_message = f"❌ An error occurred: {str(e)}"
            if is_new_command:
                bot.reply_to(message, error_message)
            else:
                bot.edit_message_text(
                    error_message,
                    message.message.chat.id,
                    message.message.message_id
                )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('upload_page_'))
    def handle_upload_pagination(call: CallbackQuery):
        """Handle pagination for upload to event command"""
        try:
            page = int(call.data.split('_')[2])
            handle_upload_to_event(call, page)
            bot.answer_callback_query(call.id)
        except Exception as e:
            logger.error(f"Error in handle_upload_pagination: {str(e)}", exc_info=True)
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('upload_event_'))
    def handle_event_selection(call: CallbackQuery):
        """Handle event selection for upload"""
        try:
            event_id = call.data.split('_')[2]
            events = drive_service.list_events()
            event = next((e for e in events if e['id'] == event_id), None)
            
            if not event:
                bot.answer_callback_query(call.id, "❌ Event not found")
                return

            # Set up upload session state
            state_data = {
                'state': 'upload_mode',
                'folder_id': event['id'],
                'folder_name': event['name'],
                'upload_expires_at': datetime.now() + timedelta(minutes=60)
            }
            state_manager.set_state(call.from_user.id, state_data)

            # Send upload instructions
            bot.edit_message_text(
                f"📤 *Upload Files to {escape_markdown(event['name'])}*\n\n"
                "You can now upload files to this event:\n"
                "• Send any documents, photos, videos, or audio files\n"
                "• Multiple files can be uploaded\n"
                "• Session expires in 60 minutes\n\n"
                "Press *Done* when finished or *Cancel* to stop uploading.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="MarkdownV2",
                reply_markup=create_status_markup(call.from_user.id)
            )
            
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"Error in handle_event_selection: {str(e)}", exc_info=True)
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    # Register the command handler
    bot.register_message_handler(handle_upload_to_event, commands=[CMD_UPLOAD_TO_EVENT, 'upload_media'])

    # Return all handlers
    return {
        'handle_file_upload': handle_file_upload,
        'handle_upload_action': handle_upload_action,
        'handle_upload_to_event': handle_upload_to_event,
        'handle_upload_pagination': handle_upload_pagination,
        'handle_event_selection': handle_event_selection
    }
