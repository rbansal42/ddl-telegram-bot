# codebase/commands/__init__.py
from telebot.handler_backends import State, StatesGroup
from telebot.types import BotCommand

# List of available commands for the bot
BOT_COMMANDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("help", "Show available commands"),
    BotCommand("upload", "Upload a file to storage"),
    BotCommand("events", "List your stored files"),
    BotCommand("delete", "Delete a stored file"),
    BotCommand("cat", "Get a random cat GIF"),
    BotCommand("dog", "Get a random dog GIF"),
    BotCommand("space", "Get a random space GIF"),
    BotCommand("meme", "Get a random meme GIF"),
    BotCommand("funny", "Get a random funny GIF"),
    BotCommand("setphoto", "Change bot's profile picture"),
    BotCommand("neweventfolder", "Create a new editable folder in Google Drive"),
    BotCommand("listfolders", "List all folders with their indexes"),
    BotCommand("getlink", "Get a link to a folder using its index"),
    BotCommand("register", "Request access to the bot"),
]

# Command names as constants to avoid typos
CMD_START = "start"
CMD_HELP = "help"
CMD_UPLOAD = "upload"
CMD_LIST = "events"
CMD_DELETE = "delete"
CMD_CAT = "cat"
CMD_DOG = "dog"
CMD_SPACE = "space"
CMD_MEME = "meme"
CMD_FUNNY = "funny"
CMD_SET_PHOTO = "setphoto"
CMD_NEWEVENTFOLDER = "neweventfolder"
CMD_LISTFOLDERS = "listfolders"
CMD_GETLINK = "getlink"
# States for handling file operations
class BotStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_event_name = State()
    waiting_for_delete_confirmation = State()
    waiting_for_gdrive_url = State()
    waiting_for_link_index = State()