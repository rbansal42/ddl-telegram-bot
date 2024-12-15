from datetime import datetime, timedelta
from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from src.database.mongo_db import MongoDB
from src.services.google.drive_service import GoogleDriveService
from src.utils.user_actions import log_action, ActionType
from src.utils.state_management import UserStateManager
from src.utils.file_helpers import get_file_info

def register_upload_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
    
    def send_upload_status(message: Message, file_type: str, file_name: str, file_size: str):
        """Send upload status message"""
        type_emoji = {
            'document': '📄',
            'photo': '🖼',
            'video': '🎥',
            'audio': '🎵'
        }
        
        return bot.reply_to(
            message,
            f"{type_emoji.get(file_type, '📁')} Uploading {file_type}...\n"
            f"Name: {file_name}\n"
            f"Size: {file_size}\n\n"
            "Please wait..."
        )

    @bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
    def handle_file_upload(message: Message):
        user_id = message.from_user.id
        print(f"\n[DEBUG] File upload attempt from user {user_id}")
        
        user_state = state_manager.get_state(user_id)
        if not user_state.get('upload_mode'):
            print(f"[DEBUG] User {user_id} not in upload mode")
            return
            
        if datetime.now() > user_state.get('upload_expires_at', datetime.now()):
            print(f"[DEBUG] Upload session expired for user {user_id}")
            bot.reply_to(
                message, 
                "⏰ Upload session has expired.\n"
                "Please create a new event folder to upload files."
            )
            state_manager.clear_state(user_id)
            return
        
        try:
            folder_id = user_state['folder_id']
            file_type, file_name, file_size = get_file_info(message)
            
            # Send initial status message
            status_msg = send_upload_status(message, file_type, file_name, file_size)
            
            # Get file info and download
            if message.document:
                file_info = bot.get_file(message.document.file_id)
            elif message.photo:
                file_info = bot.get_file(message.photo[-1].file_id)
            elif message.video:
                file_info = bot.get_file(message.video.file_id)
            elif message.audio:
                file_info = bot.get_file(message.audio.file_id)
            
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Upload to Drive
            file = drive_service.upload_file(downloaded_file, file_name, folder_id)
            
            # Update status message with success
            bot.edit_message_text(
                f"✅ File uploaded successfully!\n"
                f"Name: {file_name}\n"
                f"Size: {file_size}\n"
                f"Link: {file.get('webViewLink', 'Not available')}",
                status_msg.chat.id,
                status_msg.message_id
            )
            
            log_action(
                ActionType.FILE_UPLOADED,
                user_id,
                metadata={
                    'file_name': file_name,
                    'file_id': file['id'],
                    'folder_id': folder_id,
                    'file_type': file_type,
                    'file_size': file_size
                }
            )
            
        except Exception as e:
            print(f"[DEBUG] Error during file upload: {str(e)}")
            bot.reply_to(
                message, 
                f"❌ Failed to upload file:\n"
                f"Error: {str(e)}\n\n"
                f"Please try again or contact support if the issue persists."
            )
            log_action(
                ActionType.UPLOAD_FAILED,
                user_id,
                error_message=str(e)
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('upload_'))
    def handle_upload_action(call: CallbackQuery):
        user_id = call.from_user.id
        action = call.data.split('_')[1]
        print(f"\n[DEBUG] Upload action {action} triggered by user {user_id}")
        
        if action == 'done':
            print(f"[DEBUG] Completing upload session for user {user_id}")
            state_manager.clear_state(user_id)
            bot.edit_message_text(
                "✅ Upload session completed. Thank you!",
                call.message.chat.id,
                call.message.message_id
            )
        
        elif action == 'cancel':
            print(f"[DEBUG] Cancelling upload session for user {user_id}")
            state_manager.clear_state(user_id)
            bot.edit_message_text(
                "❌ Upload session cancelled.",
                call.message.chat.id,
                call.message.message_id
            )

    return {
        'handle_file_upload': handle_file_upload,
        'handle_upload_action': handle_upload_action
    }
