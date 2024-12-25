# Standard library imports
from datetime import datetime, timedelta

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Local application imports
from src.database.mongo_db import MongoDB
from src.middleware.auth import check_event_permission
from src.services.drive_service import GoogleDriveService
from src.utils.user_actions import log_action, ActionType
from src.utils.message_helpers import escape_markdown
from src.utils.state_management import UserStateManager
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Disable connection logs
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
logging.getLogger('pymongo.topology').setLevel(logging.WARNING)
logging.getLogger('telebot').setLevel(logging.WARNING)

def register_event_handlers(bot: TeleBot, db: MongoDB, drive_service: GoogleDriveService, state_manager: UserStateManager):
    """Register event-related command handlers"""
    logger.info("Registering event handlers...")
    
    @bot.message_handler(commands=['addevent', 'newevent'])
    @check_event_permission(bot, db)
    def add_event(message):
        logger.info(f"Add event command received from user {message.from_user.id}")
        try:
            # Check if event name was provided with command
            command_parts = message.text.split(maxsplit=1)
            if len(command_parts) > 1:
                # Name provided with command, go directly to date selection
                event_name = command_parts[1].strip()
                logger.debug(f"Event name provided with command: {event_name}")
                ask_for_date(message, event_name)
            else:
                # Create markup with cancel button
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("❌ Cancel", callback_data="cancel_event"))
                
                # Ask for event name
                msg = bot.reply_to(
                    message, 
                    "📝 Please enter the name of the event:",
                    reply_markup=markup
                )
                bot.register_next_step_handler(msg, process_event_name)
                logger.debug(f"Registered next step handler for event name for user {message.from_user.id}")
                
        except Exception as e:
            logger.error(f"Error in add_event: {str(e)}", exc_info=True)
            bot.reply_to(message, f"❌ Error: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'addevent'}
            )

    def ask_for_date(message, event_name):
        """Ask user to select date option"""
        try:
            # Create markup for date options
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📅 Custom Date", callback_data="date_custom"),
                InlineKeyboardButton("📆 Today", callback_data="date_today")
            )
            markup.row(InlineKeyboardButton("❌ Cancel", callback_data="cancel_event"))
            
            # Store event name in user data and ask for date
            user_data = {'event_name': event_name}
            bot.reply_to(
                message,
                f"Event Name: *{escape_markdown(event_name)}*\n\nChoose date option:",
                parse_mode="MarkdownV2",
                reply_markup=markup
            )
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

    def process_event_name(message):
        """Process the event name and ask for date options"""
        try:
            if message.text.startswith('/'):
                bot.reply_to(message, "❌ Event creation cancelled due to new command.")
                return
                
            event_name = message.text.strip()
            if not event_name:
                msg = bot.reply_to(message, "❌ Event name cannot be empty. Please enter a valid name:")
                bot.register_next_step_handler(msg, process_event_name)
                return
                
            ask_for_date(message, event_name)
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

    @bot.message_handler(commands=['testaddevent'])
    @check_event_permission(bot, db)
    def test_add_event(message):
        print(f"[DEBUG] Add event test command received from user {message.from_user.id}")
        try:
            # Use test event name and today's date
            event_name = "Test Event"
            date = datetime.now()
            formatted_date = date.strftime('%Y-%m-%d')
            
            # Create folder name and check if it exists
            folder_name = f"{formatted_date}; {event_name}"
            if drive_service.folder_exists(folder_name):
                bot.reply_to(
                    message,
                    "❌ An event folder with this name already exists for today.\n"
                    "Please use a different event name or check existing folders."
                )
                return
            
            # Create folder in Drive
            folder = drive_service.create_folder(folder_name)
            sharing_url = drive_service.set_folder_sharing_permissions(folder['id'])
            
            # Escape the texts
            escaped_name = escape_markdown(event_name)
            escaped_url = escape_markdown(sharing_url)
            
            # Send response
            response = (
                f"✅ Test event folder created successfully\\!\n\n"
                f"*Event:* {escaped_name}\n"
                f"*Link:* {escaped_url}"
            )
            
            bot.reply_to(
                message,
                response,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )
            
            # Log action
            log_action(
                ActionType.FOLDER_CREATED,
                message.from_user.id,
                metadata={
                    'folder_name': folder_name,
                    'folder_id': folder['id']
                }
            )
            
            # Set upload state
            state_manager.set_state(message.from_user.id, {
                'upload_mode': True,
                'folder_id': folder['id'],
                'folder_name': folder['name'],
                'upload_expires_at': datetime.now() + timedelta(minutes=60)
            })
            
            send_upload_instructions(bot, message.chat.id, folder['id'])
            
        except Exception as e:
            print(f"[DEBUG] Error in add_event_test: {str(e)}")
            bot.reply_to(message, f"❌ Error: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'addeventtest'}
            )

    def process_event_date(message, user_data):
        """Process the event date and create the folder"""
        print(f"\n[DEBUG] Processing event date for user {message.from_user.id}")
        try:
            # Parse and validate date
            try:
                print(f"[DEBUG] Parsing date: {message.text.strip()}")
                date = datetime.strptime(message.text.strip(), '%d/%m/%Y')
                formatted_date = date.strftime('%Y-%m-%d')
                print(f"[DEBUG] Formatted date: {formatted_date}")
            except ValueError:
                print("[DEBUG] Invalid date format provided")
                bot.reply_to(message, "❌ Invalid date format. Please use DD/MM/YYYY")
                return

            # Create folder name
            folder_name = f"{formatted_date}; {user_data['event_name']}"
            print(f"[DEBUG] Creating folder: {folder_name}")
            
            # Check if folder already exists
            if drive_service.folder_exists(folder_name):
                bot.reply_to(
                    message,
                    "❌ An event folder with this name already exists for the selected date.\n"
                    "Please use a different event name or date."
                )
                return
            
            # Create folder in Drive
            folder = drive_service.create_folder(folder_name)
            print(f"[DEBUG] Folder created with ID: {folder['id']}")
            
            # Set sharing permissions
            print("[DEBUG] Setting folder permissions")
            sharing_url = drive_service.set_folder_sharing_permissions(folder['id'])
            print(f"[DEBUG] Sharing URL generated: {sharing_url}")
            
            # Set upload state
            print(f"[DEBUG] Setting upload state for user {message.from_user.id}")
            state_manager.set_state(message.from_user.id, {
                'upload_mode': True,
                'folder_id': folder['id'],
                'folder_name': folder['name'],
                'upload_expires_at': datetime.now() + timedelta(minutes=60)
            })
            
            print("[DEBUG] Sending upload instructions")
            send_upload_instructions(bot, message.chat.id, folder['id'])
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error creating event folder: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'addevent'}
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('date_'))
    def handle_date_option(call):
        """Handle date option selection"""
        try:
            logger.info(f"Processing date option selection from user {call.from_user.id}")
            option = call.data.split('_')[1]
            user_data = {}
            user_data['event_name'] = call.message.reply_to_message.text.strip()
            logger.debug(f"Date option: {option}, Event name: {user_data['event_name']}")
            
            if option == 'today':
                # Use current date
                date = datetime.now()
                formatted_date = date.strftime('%Y-%m-%d')
                logger.debug(f"Using today's date: {formatted_date}")
                
                # Create folder name and check if exists
                folder_name = f"{formatted_date}; {user_data['event_name']}"
                logger.debug(f"Checking if folder exists: {folder_name}")
                if drive_service.folder_exists(folder_name):
                    logger.warning(f"Folder already exists: {folder_name}")
                    bot.edit_message_text(
                        "❌ An event folder with this name already exists for today.\n"
                        "Please use a different event name or date.",
                        call.message.chat.id,
                        call.message.message_id
                    )
                    return
                
                # Create folder directly
                logger.info(f"Creating folder: {folder_name}")
                folder = drive_service.create_folder(folder_name)
                logger.debug(f"Folder created with ID: {folder['id']}")
                
                sharing_url = drive_service.set_folder_sharing_permissions(folder['id'])
                logger.debug(f"Sharing URL generated: {sharing_url}")
                
                # Escape the texts using the helper function
                escaped_name = escape_markdown(user_data['event_name'])
                escaped_url = escape_markdown(sharing_url)
                
                # Format response
                response = (
                    f"✅ Event folder created successfully\\!\n\n"
                    f"*Event:* {escaped_name}\n"
                    f"*Link:* {escaped_url}"
                )
                
                bot.edit_message_text(
                    response,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True
                )
                
                # Log action
                log_action(
                    ActionType.FOLDER_CREATED,
                    call.from_user.id,
                    metadata={
                        'folder_name': folder_name,
                        'folder_id': folder['id']
                    }
                )
                logger.info(f"Event folder created successfully: {folder_name}")
                
                # Set upload state
                state_data = {
                    'state': 'upload_mode',
                    'folder_id': folder['id'],
                    'folder_name': folder['name'],
                    'upload_expires_at': datetime.now() + timedelta(minutes=60)
                }
                state_manager.set_state(call.from_user.id, state_data)
                logger.debug(f"Upload state set for user {call.from_user.id}: {state_data}")
                
                send_upload_instructions(bot, call.message.chat.id, folder['id'])
                
            else:  # custom date
                logger.debug("User selected custom date option")
                msg = bot.edit_message_text(
                    "📅 Please enter the event date in format DD/MM/YYYY:",
                    call.message.chat.id,
                    call.message.message_id
                )
                bot.register_next_step_handler(msg, process_event_date, user_data)
                
        except Exception as e:
            logger.error(f"Error in handle_date_option: {str(e)}", exc_info=True)
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data == "cancel_event")
    def handle_cancel_event(call):
        """Handle event creation cancellation"""
        try:
            # Edit the message to show cancellation
            bot.edit_message_text(
                "❌ Event creation cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            
            # Log the cancellation
            log_action(
                ActionType.COMMAND_CANCELLED,
                call.from_user.id,
                metadata={'command': 'addevent'}
            )
            
            # Clear any registered next step handlers for this user
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    return {
        'add_event': add_event,
        'test_add_event': test_add_event,
        'handle_date_option': handle_date_option,
        'handle_cancel_event': handle_cancel_event
    }

def create_upload_markup():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Done", callback_data="upload_done"),
        InlineKeyboardButton("❌ Cancel Upload", callback_data="upload_cancel")
    )
    return markup

def send_upload_instructions(bot, chat_id, folder_id):
    print(f"[DEBUG] Starting upload session for folder: {folder_id}")
    return bot.send_message(
        chat_id,
        "📤 *File Upload Session Started*\n\n"
        "You can now upload files to this folder:\n"
        "• Send any documents, photos, videos, or audio files\n"
        "• Multiple files can be uploaded\n"
        "• Session expires in 60 minutes\n\n"
        "Press *Done* when finished or *Cancel* to stop uploading.",
        parse_mode="Markdown",
        reply_markup=create_upload_markup()
    )
