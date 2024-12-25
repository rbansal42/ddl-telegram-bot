from typing import Optional
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.database.mongo_db import MongoDB
from src.services.drive_service import GoogleDriveService
from src.utils.state_management import UserStateManager
from src.commands.constants import CMD_COPYMEDIA
import re

def register_media_copy_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
    """Register handlers for media copying functionality"""

    def extract_folder_id(url: str) -> Optional[str]:
        """Extract Google Drive folder ID from URL"""
        patterns = [
            r'folders/([a-zA-Z0-9-_]+)',  # matches folders/FOLDER_ID
            r'id=([a-zA-Z0-9-_]+)',       # matches id=FOLDER_ID
            r'open\?id=([a-zA-Z0-9-_]+)'  # matches open?id=FOLDER_ID
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @bot.message_handler(commands=[CMD_COPYMEDIA])
    def handle_copy_media(message: Message):
        """Handle the copymedia command"""
        try:
            # Get available events
            events = drive_service.list_events()
            if not events:
                bot.reply_to(message, "❌ No events found. Please create an event first.")
                return

            # Create event selection markup
            markup = InlineKeyboardMarkup()
            for event in events:
                markup.add(InlineKeyboardButton(
                    event['name'],
                    callback_data=f"copy_to_{event['id']}"
                ))

            # Store user's state
            state_manager.set_state(message.from_user.id, "waiting_for_event_selection")
            
            bot.reply_to(
                message,
                "📁 Select the event folder where you want to copy media files:",
                reply_markup=markup
            )

        except Exception as e:
            bot.reply_to(message, f"❌ An error occurred: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('copy_to_'))
    def handle_event_selection(call: CallbackQuery):
        """Handle event selection for media copying"""
        try:
            # Extract event folder ID
            _, folder_id = call.data.split('_to_')
            
            # Store the selected folder ID
            state_manager.set_state(call.from_user.id, "waiting_for_source_folder")
            state_manager.set_data(call.from_user.id, "target_folder_id", folder_id)
            
            # Ask for source folder
            bot.edit_message_text(
                "🔗 Please send the Google Drive link of the folder containing media files you want to copy.",
                call.message.chat.id,
                call.message.message_id
            )
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    @bot.message_handler(func=lambda message: state_manager.get_state(message.from_user.id) == "waiting_for_source_folder")
    def handle_source_folder(message: Message):
        """Handle source folder link input"""
        try:
            # Extract folder ID from URL
            source_folder_id = extract_folder_id(message.text)
            if not source_folder_id:
                bot.reply_to(message, "❌ Invalid folder link. Please send a valid Google Drive folder link.")
                return

            # Get target folder ID from state
            target_folder_id = state_manager.get_data(message.from_user.id, "target_folder_id")
            
            # Clear user state
            state_manager.clear_state(message.from_user.id)
            
            # Send processing message
            status_message = bot.reply_to(message, "🔄 Processing... This may take a while.")
            
            # Copy media files
            result = drive_service.copy_media_files(source_folder_id, target_folder_id)
            
            # Update status message
            if result.get('success'):
                bot.edit_message_text(
                    f"✅ Successfully copied {result.get('copied_files', 0)} media files to the event folder.",
                    status_message.chat.id,
                    status_message.message_id
                )
            else:
                bot.edit_message_text(
                    f"❌ Error copying files: {result.get('error', 'Unknown error')}",
                    status_message.chat.id,
                    status_message.message_id
                )

        except Exception as e:
            bot.reply_to(message, f"❌ An error occurred: {str(e)}")
            state_manager.clear_state(message.from_user.id) 