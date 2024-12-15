# Standard library imports
from collections import namedtuple

# Local application imports
from src.database.roles import Role

# Type definitions
BotCommand = namedtuple('BotCommand', ['command', 'description'])

# Command constants
CMD_START = 'start'
CMD_HELP = 'help'
CMD_REGISTER = 'register'
CMD_NEWEVENTFOLDER = 'neweventfolder'
CMD_LISTFOLDERS = 'listfolders'
CMD_GETLINK = 'getlink'
CMD_CAT = 'cat'
CMD_DOG = 'dog'
CMD_SPACE = 'space'
CMD_MEME = 'meme'
CMD_FUNNY = 'funny'
CMD_MYID = 'myid'
CMD_LISTMEMBERS = 'listmembers'
CMD_REMOVEMEMBER = 'removemember'
CMD_PENDING = 'pending'
CMD_ADMINHELP = 'adminhelp'
CMD_ADDADMIN = 'addadmin'
CMD_REMOVEADMIN = 'removeadmin'
CMD_LISTADMINS = 'listadmins'
CMD_OWNERHELP = 'ownerhelp'
CMD_LISTDRIVE = 'listdrive'
CMD_DRIVEINFO = 'driveinfo'

# Public commands (available to all users)
PUBLIC_COMMANDS = [
    BotCommand(CMD_START, "Start the bot"),
    BotCommand(CMD_HELP, "Show available commands"),
    BotCommand(CMD_REGISTER, "Register for bot access"),
    BotCommand(CMD_CAT, "Get a random cat GIF"),
    BotCommand(CMD_DOG, "Get a random dog GIF"),
    BotCommand(CMD_SPACE, "Get a random space GIF"),
    BotCommand(CMD_MEME, "Get a random meme GIF"),
    BotCommand(CMD_FUNNY, "Get a random funny GIF"),
    BotCommand(CMD_MYID, "Get your Telegram ID")
]

# Member commands
MEMBER_COMMANDS = PUBLIC_COMMANDS + [
    BotCommand(CMD_LISTFOLDERS, "List all folders"),
    BotCommand(CMD_GETLINK, "Get folder link")
]

# Admin commands
ADMIN_COMMANDS = MEMBER_COMMANDS + [
    BotCommand(CMD_NEWEVENTFOLDER, "Create a new event folder"),
    BotCommand(CMD_LISTMEMBERS, "List all registered members"),
    BotCommand(CMD_REMOVEMEMBER, "Remove a member from the system"),
    BotCommand(CMD_PENDING, "List pending registration requests"),
    BotCommand(CMD_ADMINHELP, "Show admin commands")
]

# Owner commands
OWNER_COMMANDS = ADMIN_COMMANDS + [
    BotCommand(CMD_ADDADMIN, "Add a new admin user"),
    BotCommand(CMD_REMOVEADMIN, "Remove an admin user"),
    BotCommand(CMD_LISTADMINS, "List all admin users"),
    BotCommand(CMD_OWNERHELP, "Show owner commands"),
    BotCommand(CMD_LISTDRIVE, "List files in Team Drive"),
    BotCommand(CMD_DRIVEINFO, "Get Drive access information")
]

# Bot commands list
BOT_COMMANDS = PUBLIC_COMMANDS