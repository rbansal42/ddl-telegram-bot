# Standard library imports
import pytest
from unittest.mock import Mock

# Local application imports
from src.middleware.auth import check_registration
from src.database.roles import Role
from src.utils.user_actions import ActionType

def test_public_commands(test_db):
    """Test access to public commands"""
    # Mock bot and message
    bot = Mock()
    message = Mock()
    message.text = '/start'
    
    # Create decorator
    decorator = check_registration(bot, test_db)
    
    # Create mock handler
    handler = Mock()
    wrapped_handler = decorator(handler)
    
    # Call wrapped handler
    wrapped_handler(message)
    
    # Assert original handler was called
    handler.assert_called_once_with(message)
    # Assert no reply was sent
    bot.reply_to.assert_not_called()

def test_protected_command_unregistered_user(test_db):
    """Test access to protected commands by unregistered user"""
    # Mock bot and message
    bot = Mock()
    message = Mock()
    message.text = '/protected'
    message.from_user.id = 123456789
    
    # Add unregistered user
    test_db.add_user(
        user_id=message.from_user.id,
        username='testuser',
        first_name='Test',
        last_name='User'
    )
    
    # Create decorator
    decorator = check_registration(bot, test_db)
    
    # Create mock handler
    handler = Mock()
    wrapped_handler = decorator(handler)
    
    # Call wrapped handler
    wrapped_handler(message)
    
    # Assert original handler was not called
    handler.assert_not_called()
    # Assert warning message was sent
    bot.reply_to.assert_called_once()
    assert "need to register" in bot.reply_to.call_args[0][1]

def test_protected_command_registered_user(test_db):
    """Test access to protected commands by registered user"""
    # Mock bot and message
    bot = Mock()
    message = Mock()
    message.text = '/protected'
    message.from_user.id = 123456789
    
    # Add registered user
    test_db.add_user(
        user_id=message.from_user.id,
        username='testuser',
        first_name='Test',
        last_name='User'
    )
    test_db.cursor.execute(
        'UPDATE users SET registration_status = ? WHERE user_id = ?',
        ('approved', message.from_user.id)
    )
    test_db.conn.commit()
    
    # Create decorator
    decorator = check_registration(bot, test_db)
    
    # Create mock handler
    handler = Mock()
    wrapped_handler = decorator(handler)
    
    # Call wrapped handler
    wrapped_handler(message)
    
    # Assert original handler was called
    handler.assert_called_once_with(message)
    # Assert no warning message was sent
    bot.reply_to.assert_not_called() 