# Standard library imports
from datetime import datetime

# Third-party imports
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Local application imports
from src.database.mongo_db import MongoDB
from src.middleware.auth import check_event_permission
from src.services.google.drive_service import GoogleDriveService
from src.utils.user_actions import log_action, ActionType
from src.utils.message_helpers import escape_markdown

def register_event_handlers(bot: TeleBot):
    """Register event-related command handlers"""
    db = MongoDB()
    drive_service = GoogleDriveService()

    @bot.message_handler(commands=['addevent'])
    @check_event_permission(bot, db)
    def add_event(message):
        """Start the process of adding a new event folder"""
        try:
            # Ask for event name
            msg = bot.reply_to(message, "📝 Please enter the name of the event:")
            bot.register_next_step_handler(msg, process_event_name)
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'addevent'}
            )

    def process_event_name(message):
        """Process the event name and ask for date options"""
        try:
            # Store event name in user data
            user_data = {}
            user_data['event_name'] = message.text.strip()
            
            # Create markup for date options
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📅 Custom Date", callback_data="date_custom"),
                InlineKeyboardButton("📆 Today", callback_data="date_today")
            )
            
            # Ask for date preference
            bot.reply_to(
                message,
                "Choose date option:",
                reply_markup=markup
            )
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

    def process_event_date(message, user_data):
        """Process the event date and create the folder"""
        try:
            # Parse and validate date
            try:
                date = datetime.strptime(message.text.strip(), '%d/%m/%Y')
                formatted_date = date.strftime('%Y-%m-%d')
            except ValueError:
                bot.reply_to(message, "❌ Invalid date format. Please use DD/MM/YYYY")
                return

            # Create folder name
            folder_name = f"{formatted_date}; {user_data['event_name']}"
            
            # Create folder in Drive
            folder = drive_service.create_folder(folder_name)
            
            # Set sharing permissions
            sharing_url = drive_service.set_folder_sharing_permissions(folder['id'])
            
            # Escape the texts using the helper function
            escaped_name = escape_markdown(user_data['event_name'])
            escaped_url = escape_markdown(sharing_url)
            
            # Format response
            response = (
                f"✅ Event folder created successfully\\!\n\n"
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
            option = call.data.split('_')[1]
            user_data = {}
            user_data['event_name'] = call.message.reply_to_message.text.strip()
            
            if option == 'today':
                # Use current date
                date = datetime.now()
                formatted_date = date.strftime('%Y-%m-%d')
                
                # Create folder directly
                folder_name = f"{formatted_date}; {user_data['event_name']}"
                folder = drive_service.create_folder(folder_name)
                sharing_url = drive_service.set_folder_sharing_permissions(folder['id'])
                
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
                
            else:  # custom date
                msg = bot.edit_message_text(
                    "📅 Please enter the event date in format DD/MM/YYYY:",
                    call.message.chat.id,
                    call.message.message_id
                )
                bot.register_next_step_handler(msg, process_event_date, user_data)
                
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    return {
        'add_event': add_event,
        'handle_date_option': handle_date_option
    }
