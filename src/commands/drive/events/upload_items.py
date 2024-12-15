from datetime import datetime, timedelta
from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from src.database.mongo_db import MongoDB
from src.services.google.drive_service import GoogleDriveService
from src.utils.user_actions import log_action, ActionType
from src.utils.state_management import UserStateManager
from src.utils.file_helpers import get_file_info
from telebot.handler_backends import State, StatesGroup
from typing import Dict, List
import time

def register_upload_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
    # Store media groups temporarily with a timeout
    media_groups: Dict[str, Dict] = {}
    MEDIA_GROUP_TIMEOUT = 2.0  # seconds to wait for all media group messages
    
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

    def handle_media_group(messages: List[Message], folder_id: str, user_id: int):
        """Handle a group of media files"""
        print(f"[DEBUG] Processing media group with {len(messages)} items")
        
        # Sort messages by message_id to maintain order
        messages.sort(key=lambda x: x.message_id)
        
        # Send initial status
        status_msg = bot.reply_to(
            messages[0],
            f"📤 Uploading {len(messages)} files from group...\n"
            "Please wait..."
        )
        
        uploaded_files = []
        failed_files = []
        
        for msg in messages:
            try:
                file_type, file_name, file_size = get_file_info(msg)
                print(f"[DEBUG] Processing group file: {file_name}")
                
                # Get file info based on type
                if msg.photo:
                    file_info = bot.get_file(msg.photo[-1].file_id)
                elif msg.video:
                    file_info = bot.get_file(msg.video.file_id)
                else:
                    continue  # Skip unsupported types in groups
                
                # Download and upload file
                downloaded_file = bot.download_file(file_info.file_path)
                file = drive_service.upload_file(downloaded_file, file_name, folder_id)
                
                uploaded_files.append({
                    'name': file_name,
                    'size': file_size,
                    'link': file.get('webViewLink', 'Not available')
                })
                
                # Log successful upload
                log_action(
                    ActionType.FILE_UPLOADED,
                    user_id,
                    metadata={
                        'file_name': file_name,
                        'file_id': file['id'],
                        'folder_id': folder_id,
                        'file_type': file_type,
                        'file_size': file_size,
                        'media_group': True
                    }
                )
                
            except Exception as e:
                print(f"[DEBUG] Error uploading file in media group: {str(e)}")
                failed_files.append(file_name)
                log_action(
                    ActionType.UPLOAD_FAILED,
                    user_id,
                    error_message=str(e)
                )
        
        # Update status message with results
        response = f"✅ Media group upload completed\n\n"
        
        if uploaded_files:
            response += "📥 *Successfully uploaded:*\n"
            for file in uploaded_files:
                response += f"• [{file['name']}]({file['link']}) ({file['size']})\n"
        
        if failed_files:
            response += "\n❌ *Failed to upload:*\n"
            for name in failed_files:
                response += f"• {name}\n"
        
        bot.edit_message_text(
            response,
            status_msg.chat.id,
            status_msg.message_id,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    @bot.message_handler(content_types=['photo', 'video', 'document', 'audio'])
    def handle_file_upload(message: Message):
        user_id = message.from_user.id
        print(f"\n[DEBUG] File upload attempt from user {user_id}")
        
        # Check user state
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
        
        folder_id = user_state['folder_id']
        
        # Handle media groups
        if message.media_group_id:
            print(f"[DEBUG] Detected media group: {message.media_group_id}")
            
            # Store message in media group
            if message.media_group_id not in media_groups:
                media_groups[message.media_group_id] = {
                    'messages': [],
                    'timestamp': time.time(),
                    'last_update': time.time()
                }
            
            media_groups[message.media_group_id]['messages'].append(message)
            media_groups[message.media_group_id]['last_update'] = time.time()
            
            # Process media group after timeout or when we have collected enough messages
            current_time = time.time()
            group_data = media_groups[message.media_group_id]
            
            # Wait a short time to collect more messages
            time.sleep(0.1)
            
            # Check if we should process the group
            should_process = (
                current_time - group_data['last_update'] >= MEDIA_GROUP_TIMEOUT or
                len(group_data['messages']) >= 10  # Maximum media group size in Telegram
            )
            
            if should_process:
                print(f"[DEBUG] Processing media group after collecting {len(group_data['messages'])} messages")
                handle_media_group(group_data['messages'], folder_id, user_id)
                del media_groups[message.media_group_id]
            else:
                print(f"[DEBUG] Waiting for more media group messages. Current count: {len(group_data['messages'])}")
                # Schedule processing after timeout
                def process_delayed():
                    time.sleep(MEDIA_GROUP_TIMEOUT)
                    if message.media_group_id in media_groups:
                        print(f"[DEBUG] Processing media group after timeout")
                        group_data = media_groups[message.media_group_id]
                        handle_media_group(group_data['messages'], folder_id, user_id)
                        del media_groups[message.media_group_id]
                
                # Start processing in a separate thread
                import threading
                threading.Thread(target=process_delayed).start()
            
            return
        
        # Handle single file upload
        try:
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
                status_msg.message_id,
                disable_web_page_preview=True
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

    # Clean up old media groups periodically
    def cleanup_media_groups():
        current_time = time.time()
        to_remove = []
        for group_id, group_data in media_groups.items():
            # Remove groups older than 1 minute or not updated in MEDIA_GROUP_TIMEOUT seconds
            if (current_time - group_data['timestamp'] > 60 or 
                current_time - group_data['last_update'] >= MEDIA_GROUP_TIMEOUT):
                print(f"[DEBUG] Cleaning up media group: {group_id}")
                to_remove.append(group_id)
        
        for group_id in to_remove:
            group_data = media_groups[group_id]
            if group_data['messages']:
                # Process any remaining messages in the group
                user_id = group_data['messages'][0].from_user.id
                user_state = state_manager.get_state(user_id)
                if user_state.get('upload_mode'):
                    handle_media_group(group_data['messages'], user_state['folder_id'], user_id)
            del media_groups[group_id]

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
        'handle_upload_action': handle_upload_action,
        'cleanup_media_groups': cleanup_media_groups
    }
