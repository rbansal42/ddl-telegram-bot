# Third-party imports
from telebot.types import BotCommand

# Local application imports
from src.database.roles import Role

# Bot commands configuration
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
    BotCommand("ownerhelp", "Show all owner-level commands"),
    BotCommand("listdrive", "List files in Team Drive folder"),
    BotCommand("driveinfo", "Get Drive access information"),
]

# Command name constants
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
CMD_MYID = "myid"
CMD_OWNERHELP = "ownerhelp"
CMD_LISTDRIVE = "listdrive"
CMD_DRIVEINFO = "driveinfo"
BotStates = {
    "waiting_for_name": "waiting_for_name",
    "waiting_for_email": "waiting_for_email"
}