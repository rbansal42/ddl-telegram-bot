import pytest

def test_all_imports():
    """Test that all necessary imports work"""
    # Standard library imports
    import os
    import signal
    import sys

    # Third-party imports
    from dotenv import load_dotenv
    import telebot
    from telebot.handler_backends import State, StatesGroup
    from telebot.storage import StateMemoryStorage
    from telebot.types import BotCommand

    # Local application imports
    from src.commands import (
        BOT_COMMANDS,
        CMD_CAT,
        CMD_DOG,
        CMD_FUNNY,
        CMD_GETLINK,
        CMD_HELP,
        CMD_LISTFOLDERS,
        CMD_MEME,
        CMD_MYID,
        CMD_NEWEVENTFOLDER,
        CMD_REGISTER,
        CMD_SET_PHOTO,
        CMD_SPACE,
        CMD_START
    )
    from src.commands.basic_commands import register_basic_handlers
    from src.commands.fun_commands import register_fun_handlers
    from src.commands.google_drive_commands import register_google_drive_handlers
    from src.commands.registration_commands import register_registration_handlers
    from src.database.db import BotDB
    from src.database.mongo_db import MongoDB
    from src.middleware.auth import check_registration

    assert True, "All imports successful" 