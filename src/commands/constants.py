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
    BotCommand(CMD_NEWEVENTFOLDER, "Create a new event folder"),
    BotCommand(CMD_LISTFOLDERS, "List all folders"),
    BotCommand(CMD_GETLINK, "Get folder link")
]

# Admin commands
ADMIN_COMMANDS = MEMBER_COMMANDS + [
    BotCommand('listmembers', "List all registered members"),
    BotCommand('removemember', "Remove a member from the system"),
    BotCommand('pending', "List pending registration requests"),
    BotCommand('adminhelp', "Show admin commands")
]

# Owner commands
OWNER_COMMANDS = ADMIN_COMMANDS + [
    BotCommand('addadmin', "Add a new admin user"),
    BotCommand('removeadmin', "Remove an admin user"),
    BotCommand('listadmins', "List all admin users"),
    BotCommand('ownerhelp', "Show owner commands"),
    BotCommand('listdrive', "List files in Team Drive"),
    BotCommand('driveinfo', "Get Drive access information")
]

# Bot commands list
BOT_COMMANDS = PUBLIC_COMMANDS