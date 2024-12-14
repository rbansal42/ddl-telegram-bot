# codebase/commands/__init__.py
from telebot.types import BotCommand

# List of available commands for the bot
BOT_COMMANDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("help", "Show available commands"),
    BotCommand("register", "Request access to the bot"),
    BotCommand("neweventfolder", "Create a new editable folder in Google Drive"),
    BotCommand("listfolders", "List all folders with their indexes"),
    BotCommand("getlink", "Get a link to a folder using its index"),
    BotCommand("cat", "Get a random cat GIF"),
    BotCommand("dog", "Get a random dog GIF"),
    BotCommand("space", "Get a random space GIF"),
    BotCommand("meme", "Get a random meme GIF"),
    BotCommand("funny", "Get a random funny GIF"),
    BotCommand("setphoto", "Change bot's profile picture"),
]


# Command names as constants to avoid typos
CMD_START = "start"
CMD_HELP = "help"
CMD_REGISTER = "register"
CMD_NEWEVENTFOLDER = "neweventfolder"
CMD_LISTFOLDERS = "listfolders"
CMD_GETLINK = "getlink"
CMD_CAT = "cat"
CMD_DOG = "dog"
CMD_SPACE = "space"
CMD_MEME = "meme"
CMD_FUNNY = "funny"
CMD_SET_PHOTO = "setphoto"
CMD_MYID = "myid"

BotStates = {
    "waiting_for_name": "waiting_for_name",
    "waiting_for_email": "waiting_for_email"
}