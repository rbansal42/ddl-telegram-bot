from typing import Optional
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.database.mongo_db import MongoDB
from src.services.drive_service import GoogleDriveService
from src.utils.state_management import UserStateManager
from src.commands.constants import CMD_COPYMEDIA
import re
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Disable connection logs
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
logging.getLogger('pymongo.topology').setLevel(logging.WARNING)
logging.getLogger('telebot').setLevel(logging.WARNING)

def register_media_copy_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
    """Register handlers for media copying functionality"""

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

    @bot.message_handler(commands=[CMD_COPYMEDIA])
    def handle_copy_media(message: Message):
        """Handle the copymedia command"""
        try:
            logger.info(f"Processing copy media command from user {message.from_user.id}")
            
            # Get available events and sort them by latest first (limited to 5)
            events = drive_service.list_events()
            if not events:
                logger.warning("No events found")
                bot.reply_to(message, "❌ No events found. Please create an event first.")
                return

            # Sort events by name in reverse order (latest first) and limit to 5
            events = sorted(events, key=lambda x: x['name'], reverse=True)[:5]
            logger.debug(f"Sorted and limited events: {events}")

            # Create event selection markup
            markup = InlineKeyboardMarkup()
            for event in events:
                event_name = event['name']
                logger.debug(f"Adding event to markup: {event_name} (ID: {event['id']})")
                markup.add(InlineKeyboardButton(
                    event_name,
                    callback_data=f"copy_to_{event['id']}"
                ))

            # Store user's state
            state_manager.set_state(message.from_user.id, "waiting_for_event_selection")
            logger.debug(f"Set user {message.from_user.id} state to waiting_for_event_selection")
            
            bot.reply_to(
                message,
                "📁 Select the event folder where you want to copy media files (showing 5 most recent events):",
                reply_markup=markup
            )

        except Exception as e:
            logger.error(f"Error in handle_copy_media: {str(e)}", exc_info=True)
            bot.reply_to(message, f"❌ An error occurred: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('copy_to_'))
    def handle_event_selection(call: CallbackQuery):
        """Handle event selection for media copying"""
        try:
            logger.info(f"Processing event selection from user {call.from_user.id}")
            
            # Extract event folder ID
            _, folder_id = call.data.split('_to_')
            logger.debug(f"Selected target folder ID: {folder_id}")
            
            # Store the selected folder ID and state in a dictionary
            state_data = {
                'state': 'waiting_for_source_folder',
                'target_folder_id': folder_id
            }
            state_manager.set_state(call.from_user.id, state_data)
            logger.debug(f"Stored state data for user {call.from_user.id}: {state_data}")
            
            # Ask for source folder
            bot.edit_message_text(
                "🔗 Please send the Google Drive link of the folder containing media files you want to copy.",
                call.message.chat.id,
                call.message.message_id
            )
            
        except Exception as e:
            logger.error(f"Error in handle_event_selection: {str(e)}", exc_info=True)
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    @bot.message_handler(func=lambda message: state_manager.get_state(message.from_user.id).get('state') == "waiting_for_source_folder")
    def handle_source_folder(message: Message):
        """Handle source folder link input"""
        try:
            logger.info(f"Processing source folder link from user {message.from_user.id}")
            
            # Extract folder ID from URL
            source_folder_id = extract_folder_id(message.text)
            if not source_folder_id:
                logger.warning(f"Invalid folder link provided by user {message.from_user.id}: {message.text}")
                bot.reply_to(message, "❌ Invalid folder link. Please send a valid Google Drive folder link.")
                return

            # Get target folder ID from state
            user_state = state_manager.get_state(message.from_user.id)
            target_folder_id = user_state.get('target_folder_id')
            logger.debug(f"Retrieved target folder ID: {target_folder_id}")
            
            # Clear user state
            state_manager.clear_state(message.from_user.id)
            logger.debug(f"Cleared state for user {message.from_user.id}")
            
            # Send processing message
            status_message = bot.reply_to(message, "🔄 Processing... This may take a while.")
            
            # Copy media files
            logger.info(f"Starting media copy from {source_folder_id} to {target_folder_id}")
            result = drive_service.copy_media_files(source_folder_id, target_folder_id)
            
            # Update status message
            if result.get('success'):
                logger.info(f"Successfully copied {result.get('copied_files')} files")
                bot.edit_message_text(
                    f"✅ Successfully copied {result.get('copied_files', 0)} media files to the event folder.",
                    status_message.chat.id,
                    status_message.message_id
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Failed to copy files: {error_msg}")
                bot.edit_message_text(
                    f"❌ Error copying files: {error_msg}",
                    status_message.chat.id,
                    status_message.message_id
                )

        except Exception as e:
            logger.error(f"Error in handle_source_folder: {str(e)}", exc_info=True)
            bot.reply_to(message, f"❌ An error occurred: {str(e)}")
            state_manager.clear_state(message.from_user.id) 