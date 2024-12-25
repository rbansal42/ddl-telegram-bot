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
    def handle_copy_media(message: Message | CallbackQuery, page: int = 0):
        """Handle the copymedia command"""
        try:
            # Determine if this is a new command or pagination
            is_new_command = isinstance(message, Message)
            user_id = message.from_user.id
            logger.info(f"Processing copy media command from user {user_id}")
            
            # Get available events
            events = drive_service.list_events()
            if not events:
                logger.warning("No events found")
                if is_new_command:
                    bot.reply_to(message, "❌ No events found. Please create an event first.")
                else:
                    bot.edit_message_text(
                        "❌ No events found. Please create an event first.",
                        message.message.chat.id,
                        message.message.message_id
                    )
                return

            # Sort events by name in reverse order (latest first)
            events = sorted(events, key=lambda x: x['name'], reverse=True)
            
            # Calculate pagination
            ITEMS_PER_PAGE = 5
            total_pages = (len(events) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            
            # Get events for current page
            start_idx = page * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            current_events = events[start_idx:end_idx]
            
            logger.debug(f"Showing events {start_idx+1}-{min(end_idx, len(events))} of {len(events)}")

            # Create event selection markup
            markup = InlineKeyboardMarkup(row_width=1)  # Set row_width to 1 for better layout
            
            # Add event buttons
            for event in current_events:
                event_name = event['name']
                logger.debug(f"Adding event to markup: {event_name} (ID: {event['id']})")
                markup.add(InlineKeyboardButton(
                    event_name,
                    callback_data=f"copy_to_{event['id']}"
                ))
            
            # Add navigation buttons if needed
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"copy_page_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"copy_page_{page+1}"))
            
            if nav_buttons:
                markup.row(*nav_buttons)
            
            # Add cancel button
            markup.add(InlineKeyboardButton("❌ Cancel", callback_data="copy_cancel"))

            # Store user's state as a dictionary
            state_data = {
                'state': 'waiting_for_event_selection',
                'current_page': page,
                'total_events': len(events)
            }
            state_manager.set_state(user_id, state_data)
            logger.debug(f"Set user {user_id} state to {state_data}")
            
            # Create message text with pagination info
            message_text = (
                "📁 Select the event folder where you want to copy media files:\n"
                f"(Showing {start_idx+1}-{min(end_idx, len(events))} of {len(events)} events)"
            )
            
            # Send or edit message based on context
            if is_new_command:
                bot.reply_to(message, message_text, reply_markup=markup)
            else:
                # For pagination, edit the existing message
                bot.edit_message_text(
                    message_text,
                    message.message.chat.id,
                    message.message.message_id,
                    reply_markup=markup
                )

        except Exception as e:
            logger.error(f"Error in handle_copy_media: {str(e)}", exc_info=True)
            error_message = f"❌ An error occurred: {str(e)}"
            if is_new_command:
                bot.reply_to(message, error_message)
            else:
                bot.edit_message_text(
                    error_message,
                    message.message.chat.id,
                    message.message.message_id
                )

    @bot.callback_query_handler(func=lambda call: call.data == "copy_cancel")
    def handle_copy_cancel(call: CallbackQuery):
        """Handle cancellation of media copy process"""
        try:
            logger.info(f"User {call.from_user.id} cancelled the media copy process")
            
            # Set cancelled state to trigger immediate stop
            state_manager.set_state(call.from_user.id, {'state': 'cancelled'})
            
            # Update message
            bot.edit_message_text(
                "❌ Media copy process cancelled. Cleaning up...",
                call.message.chat.id,
                call.message.message_id
            )
            
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"Error in handle_copy_cancel: {str(e)}", exc_info=True)
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    def check_if_cancelled(user_id: int) -> bool:
        """Check if the process has been cancelled"""
        current_state = state_manager.get_state(user_id)
        return isinstance(current_state, dict) and current_state.get('state') == 'cancelled'

    @bot.callback_query_handler(func=lambda call: call.data.startswith('copy_to_'))
    def handle_event_selection(call: CallbackQuery):
        """Handle event selection for media copying"""
        try:
            logger.info(f"Processing event selection from user {call.from_user.id}")
            
            # Get current state to verify we're in the right state
            current_state = state_manager.get_state(call.from_user.id)
            if not isinstance(current_state, dict) or current_state.get('state') != 'waiting_for_event_selection':
                logger.error(f"Invalid state for user {call.from_user.id}: {current_state}")
                bot.answer_callback_query(call.id, "❌ Session expired. Please start over.")
                bot.edit_message_text(
                    "❌ Session expired. Please start over.",
                    call.message.chat.id,
                    call.message.message_id
                )
                state_manager.clear_state(call.from_user.id)
                return
            
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
            
            # Create markup with cancel button
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Cancel", callback_data="copy_cancel"))
            
            # Ask for source folder
            bot.edit_message_text(
                "🔗 Please send the Google Drive link of the folder containing media files you want to copy.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"Error in handle_event_selection: {str(e)}", exc_info=True)
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    @bot.message_handler(func=lambda message: isinstance(state_manager.get_state(message.from_user.id), dict) and 
                                                     state_manager.get_state(message.from_user.id).get('state') == "waiting_for_source_folder")
    def handle_source_folder(message: Message):
        """Handle source folder link input"""
        try:
            logger.info(f"Processing source folder link from user {message.from_user.id}")
            
            # Extract folder ID from URL
            source_folder_id = extract_folder_id(message.text)
            if not source_folder_id:
                logger.warning(f"Invalid folder link provided by user {message.from_user.id}: {message.text}")
                
                # Create markup with cancel button
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("❌ Cancel", callback_data="copy_cancel"))
                
                bot.reply_to(
                    message, 
                    "❌ Invalid folder link. Please send a valid Google Drive folder link.",
                    reply_markup=markup
                )
                return

            # Get target folder ID from state
            user_state = state_manager.get_state(message.from_user.id)
            if not isinstance(user_state, dict):
                logger.error(f"Invalid state type for user {message.from_user.id}: {type(user_state)}")
                bot.reply_to(message, "❌ Session expired. Please start over.")
                state_manager.clear_state(message.from_user.id)
                return
                
            target_folder_id = user_state.get('target_folder_id')
            if not target_folder_id:
                logger.error(f"No target folder ID in state for user {message.from_user.id}")
                bot.reply_to(message, "❌ Session expired. Please start over.")
                state_manager.clear_state(message.from_user.id)
                return
                
            logger.debug(f"Retrieved target folder ID: {target_folder_id}")
            
            # Get folder statistics
            status_message = bot.reply_to(message, "🔍 Analyzing folder contents...")
            
            folder_stats = drive_service.get_folder_stats(source_folder_id)
            if not folder_stats.get('success'):
                error_msg = folder_stats.get('error', 'Unknown error')
                logger.error(f"Failed to get folder stats: {error_msg}")
                bot.edit_message_text(
                    f"❌ Error analyzing folder: {error_msg}",
                    status_message.chat.id,
                    status_message.message_id
                )
                return
                
            total_files = folder_stats['total_files']
            total_size = folder_stats['total_size']
            
            # Format size for display
            size_str = ""
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size/1024:.1f} KB"
            elif total_size < 1024 * 1024 * 1024:
                size_str = f"{total_size/(1024*1024):.1f} MB"
            else:
                size_str = f"{total_size/(1024*1024*1024):.1f} GB"
            
            if total_files == 0:
                bot.edit_message_text(
                    "❌ No media files found in the source folder.",
                    status_message.chat.id,
                    status_message.message_id
                )
                return
                
            # Create markup with cancel button
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Cancel", callback_data="copy_cancel"))
            
            # Update message with folder stats
            bot.edit_message_text(
                f"📊 Found {total_files} media files (Total size: {size_str})\n\n"
                "🔄 Starting copy process...\n"
                "⬜️ Progress: 0%",
                status_message.chat.id,
                status_message.message_id,
                reply_markup=markup
            )
            
            def update_progress(copied_files: int, total_files: int, progress: float):
                """Callback function to update progress message"""
                # Check if cancelled and raise exception to trigger cleanup
                if state_manager.get_state(message.from_user.id).get('state') == 'cancelled':
                    raise Exception("Process cancelled by user")
                    
                progress_bar = "▓" * int(progress/5) + "░" * (20 - int(progress/5))
                bot.edit_message_text(
                    f"📊 Copying {total_files} media files (Total size: {size_str})\n\n"
                    f"🔄 Progress: {progress:.1f}%\n"
                    f"[{progress_bar}] {copied_files}/{total_files} files",
                    status_message.chat.id,
                    status_message.message_id,
                    reply_markup=markup  # Keep the cancel button
                )
            
            # Copy media files
            logger.info(f"Starting media copy from {source_folder_id} to {target_folder_id}")
            result = drive_service.copy_media_files(source_folder_id, target_folder_id, update_progress)
            
            # Clear state
            state_manager.clear_state(message.from_user.id)
            
            # Update status message
            if result.get('success'):
                logger.info(f"Successfully copied {result.get('copied_files')} files")
                bot.edit_message_text(
                    f"✅ Successfully copied {result.get('copied_files', 0)} media files to the event folder.\n"
                    f"📊 Total size: {size_str}",
                    status_message.chat.id,
                    status_message.message_id
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Failed to copy files: {error_msg}")
                
                if error_msg == 'Process cancelled by user':
                    bot.edit_message_text(
                        "❌ Media copy process cancelled and cleaned up.",
                        status_message.chat.id,
                        status_message.message_id
                    )
                else:
                    bot.edit_message_text(
                        f"❌ Error copying files: {error_msg}",
                        status_message.chat.id,
                        status_message.message_id
                    )

        except Exception as e:
            if str(e) == "Process cancelled by user":
                return
                
            logger.error(f"Error in handle_source_folder: {str(e)}", exc_info=True)
            bot.reply_to(message, f"❌ An error occurred: {str(e)}")
            state_manager.clear_state(message.from_user.id) 

    @bot.callback_query_handler(func=lambda call: call.data.startswith('copy_page_'))
    def handle_copy_pagination(call: CallbackQuery):
        """Handle pagination for event selection"""
        try:
            logger.info(f"Processing pagination request from user {call.from_user.id}")
            
            # Get current state to verify we're in the right state
            current_state = state_manager.get_state(call.from_user.id)
            if not isinstance(current_state, dict) or current_state.get('state') != 'waiting_for_event_selection':
                logger.error(f"Invalid state for user {call.from_user.id}: {current_state}")
                bot.answer_callback_query(call.id, "❌ Session expired. Please start over.")
                bot.edit_message_text(
                    "❌ Session expired. Please start over.",
                    call.message.chat.id,
                    call.message.message_id
                )
                state_manager.clear_state(call.from_user.id)
                return
            
            # Extract page number
            _, page = call.data.split('copy_page_')
            page = int(page)
            
            # Handle the copy media command with the new page
            handle_copy_media(call, page)
            
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"Error in handle_copy_pagination: {str(e)}", exc_info=True)
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}") 