import pytest

def test_all_imports():
    """Test that all necessary imports work"""
    # Test basic imports
    from src.database.db import BotDB
    from src.database.mongo_db import MongoDB
    
    # Test command imports
    from src.commands import (
        CMD_START, CMD_HELP, CMD_REGISTER,
        CMD_NEWEVENTFOLDER, CMD_LISTFOLDERS, CMD_GETLINK,
        CMD_CAT, CMD_DOG, CMD_SPACE, CMD_MEME, CMD_FUNNY,
        CMD_SET_PHOTO, CMD_MYID, BOT_COMMANDS
    )
    
    # Test handler imports
    from src.commands.basic_commands import register_basic_handlers
    from src.commands.registration_commands import register_registration_handlers
    from src.commands.google_drive_commands import register_google_drive_handlers
    from src.commands.fun_commands import register_fun_handlers
    
    # Test middleware imports
    from src.middleware.auth import check_registration
    
    assert True, "All imports successful" 