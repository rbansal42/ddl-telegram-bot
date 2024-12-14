from collections import namedtuple

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

# Bot commands list
BOT_COMMANDS = [
    BotCommand(CMD_START, "Start the bot"),
    BotCommand(CMD_HELP, "Show available commands"),
    BotCommand(CMD_REGISTER, "Register for bot access"),
    BotCommand(CMD_NEWEVENTFOLDER, "Create a new event folder"),
    BotCommand(CMD_LISTFOLDERS, "List all folders"),
    BotCommand(CMD_GETLINK, "Get folder link"),
    BotCommand(CMD_CAT, "Get a random cat GIF"),
    BotCommand(CMD_DOG, "Get a random dog GIF"),
    BotCommand(CMD_SPACE, "Get a random space GIF"),
    BotCommand(CMD_MEME, "Get a random meme GIF"),
    BotCommand(CMD_FUNNY, "Get a random funny GIF"),
    BotCommand(CMD_MYID, "Get your Telegram ID")
] 