from datetime import datetime, timedelta
from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from src.database.mongo_db import MongoDB
from src.services.google.drive_service import GoogleDriveService
from src.utils.user_actions import log_action, ActionType
from src.utils.state_management import UserStateManager

def register_upload_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
    
    @bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
    def handle_file_upload(message: Message):
        user_id = message.from_user.id
        user_state = state_manager.get_state(user_id)
        
        # Check if user is in upload mode and within time window
        if not user_state.get('upload_mode') or \
           datetime.now() > user_state.get('upload_expires_at', datetime.now()):
            return
        
        try:
            folder_id = user_state['folder_id']
            
            # Handle different types of content
            if message.document:
                file_info = bot.get_file(message.document.file_id)
                file_name = message.document.file_name
            elif message.photo:
                file_info = bot.get_file(message.photo[-1].file_id)
                file_name = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            elif message.video:
                file_info = bot.get_file(message.video.file_id)
                file_name = message.video.file_name or f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            elif message.audio:
                file_info = bot.get_file(message.audio.file_id)
                file_name = message.audio.file_name or f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            
            # Download file
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Upload to Google Drive
            file = drive_service.upload_file(downloaded_file, file_name, folder_id)
            
            bot.reply_to(
                message,
                f"✅ File '{file_name}' uploaded successfully!"
            )
            
            # Log action
            log_action(
                ActionType.FILE_UPLOADED,
                user_id,
                metadata={
                    'file_name': file_name,
                    'file_id': file['id'],
                    'folder_id': folder_id
                }
            )
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error uploading file: {str(e)}")
            log_action(
                ActionType.UPLOAD_FAILED,
                user_id,
                error_message=str(e)
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('upload_'))
    def handle_upload_action(call: CallbackQuery):
        user_id = call.from_user.id
        action = call.data.split('_')[1]
        
        if action == 'done':
            state_manager.clear_state(user_id)
            bot.edit_message_text(
                "✅ Upload session completed. Thank you!",
                call.message.chat.id,
                call.message.message_id
            )
        
        elif action == 'cancel':
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
