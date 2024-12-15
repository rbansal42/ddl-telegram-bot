# Standard library imports
import pytest
from unittest.mock import Mock, patch

# Local application imports
from src.commands.basic_commands import register_basic_handlers
from src.commands.constants import CMD_START, CMD_HELP
from src.database.roles import Role
from src.utils.user_actions import ActionType

def test_start_command(test_db):
    """Test /start command"""
    # Mock bot
    bot = Mock()
    # Store the decorated function
    start_handler = None
    
    # Mock message_handler to capture the handler function
    def message_handler_mock(*args, **kwargs):
        def decorator(func):
            nonlocal start_handler
            if kwargs.get('commands') == [CMD_START]:
                start_handler = func
            return func
        return decorator
    
    bot.message_handler = message_handler_mock
    
    # Register handlers
    register_basic_handlers(bot, test_db)
    
    assert start_handler is not None, "Start handler not registered"
    
    # Mock message
    message = Mock()
    
    # Call handler
    start_handler(message)
    
    # Assert response
    bot.reply_to.assert_called_once()
    assert "Hello" in bot.reply_to.call_args[0][1]

def test_help_command_unregistered(test_db):
    """Test /help command for unregistered user"""
    # Mock bot
    bot = Mock()
    # Store the decorated function
    help_handler = None
    
    # Mock message_handler to capture the handler function
    def message_handler_mock(*args, **kwargs):
        def decorator(func):
            nonlocal help_handler
            if kwargs.get('commands') == [CMD_HELP]:
                help_handler = func
            return func
        return decorator
    
    bot.message_handler = message_handler_mock
    
    # Mock message
    message = Mock()
    message.from_user.id = 123456789
    
    # Add unregistered user
    test_db.add_user(
        user_id=message.from_user.id,
        username='testuser',
        first_name='Test',
        last_name='User'
    )
    
    # Register handlers
    register_basic_handlers(bot, test_db)
    
    assert help_handler is not None, "Help handler not registered"
    
    # Call handler
    help_handler(message)
    
    # Assert response
    bot.reply_to.assert_called_once()
    response = bot.reply_to.call_args[0][1]
    assert "Available Commands" in response
    assert "Additional commands will be available" in response 