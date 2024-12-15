from datetime import datetime, timedelta
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.database.mongo_db import MongoDB
from src.services.google.drive_service import GoogleDriveService
from src.utils.user_actions import log_action, ActionType
from src.utils.state_management import UserStateManager
from src.utils.file_helpers import get_file_info, format_file_size
from src.utils.file_handler import TempFileHandler
from telebot.handler_backends import State, StatesGroup
from typing import Dict, List
import time

def register_upload_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
    temp_handler = TempFileHandler()
    
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
                # Update status message
                file_count, total_size = state_manager.get_upload_stats(user_id)
                size_str = format_file_size(total_size)
                bot.edit_message_text(
                    f"⏳ Processing uploads...\n"
                    f"Uploading {file_count} files ({size_str}) to Drive.\n"
                    f"Please wait while files are being processed.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
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
                
                # Initial progress message
                update_progress_message(bot, call.message.chat.id, call.message.message_id, user_id, state_manager)
                
                # Upload files
                uploaded_files = []
                for file in pending_uploads:
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
                        
                        # Update progress after each file
                        state_manager.get_state(user_id)['completed_uploads'].append(file)
                        update_progress_message(
                            bot, 
                            call.message.chat.id, 
                            call.message.message_id,
                            user_id,
                            state_manager
                        )
                
                # Format summary
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
                    summary += f"{emoji} [{file['name']}]({file['web_link']}) - {file['size']}\n"
                summary += f"\n*Total Size:* {total_size}"
                
                # Send final message
                bot.edit_message_text(
                    f"✅ *Upload Complete!*\n\n{summary}",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown",
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
                "❌ Upload session cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            log_action(
                ActionType.UPLOAD_CANCELLED,
                user_id
            )

    return {
        'handle_file_upload': handle_file_upload,
        'handle_upload_action': handle_upload_action
    }
