import os
import re
from telebot import TeleBot
from telebot import types
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from commands import CMD_NEWEVENTFOLDER, CMD_LISTFOLDERS, CMD_GETLINK
from commands.__init__ import BotStates
from database.db import BotDB

# Define the scope for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

# Get the absolute path to the service account file
current_dir = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(current_dir), 'credentials', 'service_account.json')

if not os.path.isfile(SERVICE_ACCOUNT_FILE):
    raise FileNotFoundError(f"Service account file not found at: {SERVICE_ACCOUNT_FILE}")

# Parent folder ID (the only folder the bot can access)
PARENT_FOLDER_ID = '1AsDYNKYc6LwRzCqnnhjeEj0ZT7qWlNv'  # Hardcoded folder ID

# Authenticate and build the service
try:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
except Exception as e:
    raise ConnectionError(f"Failed to authenticate with Google Drive: {e}")

def register_google_drive_handlers(bot: TeleBot):
    db = BotDB()

    @bot.message_handler(commands=[CMD_NEWEVENTFOLDER])
    def handle_gdrive_command(message):
        # Log user if not exists
        db.add_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        msg = bot.reply_to(message, "Please enter the event date (YYYY-MM-DD):")
        bot.register_next_step_handler(msg, process_event_date)

    def process_event_date(message):
        try:
            event_date = datetime.strptime(message.text.strip(), '%Y-%m-%d').date()
            msg = bot.reply_to(message, "Please send me the Google Drive folder URL.")
            # Store the event date in bot's user_data
            bot.user_data = {'event_date': event_date}
            bot.register_next_step_handler(msg, process_gdrive_url)
        except ValueError:
            bot.reply_to(message, "Invalid date format. Please use YYYY-MM-DD format.")
            return

    def process_gdrive_url(message):
        url = message.text.strip()
        folder_id = extract_folder_id(url)
        if not folder_id:
            bot.reply_to(message, "Invalid Google Drive URL. Please make sure it's a valid folder URL.")
            return

        if folder_id != PARENT_FOLDER_ID:
            bot.reply_to(message, "You do not have permission to access this folder.")
            return

        event_date = bot.user_data.get('event_date')
        folder_name = f"Event {event_date.strftime('%Y-%m-%d')}"
        new_folder = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [PARENT_FOLDER_ID]
        }

        try:
            file = drive_service.files().create(body=new_folder, fields='id, name, webViewLink').execute()
            new_folder_id = file.get('id')
            new_folder_url = file.get('webViewLink')

            # Log to database with event date
            db.log_folder_creation(
                new_folder_id,
                folder_name,
                new_folder_url,
                message.from_user.id,
                event_date.isoformat()
            )

            permission = {
                'type': 'anyone',
                'role': 'writer'
            }
            drive_service.permissions().create(
                fileId=new_folder_id,
                body=permission,
                fields='id',
            ).execute()

            bot.reply_to(message, f"Event folder created for {event_date}:\n{new_folder_url}")
        except Exception as e:
            db.log_action(message.from_user.id, 'error', f"Folder creation failed: {str(e)}")
            bot.reply_to(message, f"An error occurred while creating the folder: {str(e)}")

    def extract_folder_id(url):
        # Regular expressions to extract folder ID from Google Drive URLs
        patterns = [
            r"https?://drive\.google\.com/drive/folders/([a-zA-Z0-9_-]+)",
            r"https?://drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
            r"https?://drive\.google\.com/uc\?id=([a-zA-Z0-9_-]+)"
        ]
        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                return match.group(1)
        return None

    @bot.message_handler(commands=[CMD_LISTFOLDERS])
    def list_folders(message):
        try:
            folders = db.get_user_folders(message.from_user.id)
            
            if not folders:
                bot.reply_to(message, "No folders found.")
                return

            response = "Your event folders:\n"
            for idx, folder in enumerate(folders, start=1):
                event_date = folder.get('event_date', 'No date')
                response += f"{idx}. {folder['name']} (Event: {event_date})\n"

            response += "\nSend `/getlink <index>` to get the link of the folder."
            
            db.log_action(message.from_user.id, 'list_folders', 'Listed all folders')
            bot.reply_to(message, response)
        except Exception as e:
            db.log_action(message.from_user.id, 'error', f"Listing folders failed: {str(e)}")
            bot.reply_to(message, f"An error occurred while listing folders: {str(e)}")

    @bot.message_handler(commands=[CMD_GETLINK])
    def get_link_command(message):
        args = message.text.split()
        if len(args) != 2 or not args[1].isdigit():
            bot.reply_to(message, "Please provide a valid folder index. Usage: /getlink <index>")
            return

        index = int(args[1])
        try:
            query = f"'{PARENT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = drive_service.files().list(
                q=query,
                fields="files(id, name, webViewLink)",
                orderBy="name"
            ).execute()
            folders = results.get('files', [])

            if not (1 <= index <= len(folders)):
                bot.reply_to(message, f"Please provide an index between 1 and {len(folders)}.")
                return

            selected_folder = folders[index - 1]
            folder_url = selected_folder.get('webViewLink')

            # Optionally, you can specify the type of link (view-only or editable)
            bot.reply_to(message, f"Link to **{selected_folder.get('name')}**:\n{folder_url}")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while retrieving the link: {str(e)}") 