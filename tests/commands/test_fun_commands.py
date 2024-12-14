import pytest
from unittest.mock import Mock, patch
from src.commands.fun_commands import register_fun_handlers
from src.commands import CMD_CAT, CMD_DOG, CMD_SPACE, CMD_MEME, CMD_FUNNY

def test_cat_command():
    """Test /cat command"""
    # Mock bot
    bot = Mock()
    cat_handler = None
    
    # Mock message_handler to capture the handler function
    def message_handler_mock(*args, **kwargs):
        def decorator(func):
            nonlocal cat_handler
            if kwargs.get('commands') == [CMD_CAT]:
                cat_handler = func
            return func
        return decorator
    
    bot.message_handler = message_handler_mock
    
    # Register handlers
    with patch('requests.get') as mock_get:
        # Mock successful API response
        mock_get.return_value.json.return_value = {
            "data": {"images": {"original": {"url": "http://example.com/cat.gif"}}}
        }
        mock_get.return_value.raise_for_status = Mock()
        
        register_fun_handlers(bot)
        
        assert cat_handler is not None, "Cat handler not registered"
        
        # Mock message
        message = Mock()
        message.chat.id = 123456789
        
        # Call handler
        cat_handler(message)
        
        # Assert response
        bot.send_animation.assert_called_once_with(
            message.chat.id, 
            "http://example.com/cat.gif",
            caption="Here's your random cat GIF! 😺"
        )

def test_cat_command_api_error():
    """Test /cat command when API fails"""
    # Mock bot
    bot = Mock()
    cat_handler = None
    
    def message_handler_mock(*args, **kwargs):
        def decorator(func):
            nonlocal cat_handler
            if kwargs.get('commands') == [CMD_CAT]:
                cat_handler = func
            return func
        return decorator
    
    bot.message_handler = message_handler_mock
    
    # Register handlers
    with patch('requests.get') as mock_get:
        # Mock API error
        mock_get.side_effect = Exception("API Error")
        
        register_fun_handlers(bot)
        
        assert cat_handler is not None, "Cat handler not registered"
        
        # Mock message
        message = Mock()
        
        # Call handler
        cat_handler(message)
        
        # Assert error response
        bot.reply_to.assert_called_once_with(
            message, 
            "Sorry, couldn't fetch a cat GIF! 😿"
        ) 