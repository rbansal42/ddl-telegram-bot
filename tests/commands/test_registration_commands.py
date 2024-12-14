import pytest
from unittest.mock import Mock, patch
from src.commands.registration_commands import register_registration_handlers
from src.commands import CMD_REGISTER, BotStates

def test_register_command_new_user(test_db):
    """Test /register command for a new user"""
    # Reset database state completely
    test_db.cursor.execute('DROP TABLE IF EXISTS users')
    test_db.cursor.execute('DROP TABLE IF EXISTS registration_requests')
    test_db.cursor.execute('DROP TABLE IF EXISTS user_actions')
    test_db.conn.commit()
    
    # Recreate tables
    test_db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registration_status TEXT DEFAULT 'pending',
            approved_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    test_db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS registration_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT,
            full_name TEXT,
            status TEXT DEFAULT 'pending',
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    test_db.conn.commit()
    
    bot = Mock()
    register_handler = None
    
    def message_handler_mock(*args, **kwargs):
        def decorator(func):
            nonlocal register_handler
            if kwargs.get('commands') == [CMD_REGISTER]:
                register_handler = func
            return func
        return decorator
    
    bot.message_handler = message_handler_mock
    bot.register_next_step_handler = Mock()
    
    # Mock message
    message = Mock()
    message.from_user.id = 123456789
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.chat.id = 123456789
    
    # Verify user doesn't exist
    result = test_db.cursor.execute('SELECT * FROM users WHERE user_id = ?', (message.from_user.id,)).fetchone()
    assert result is None, "User should not exist in database"
    
    # Register handlers with real database
    register_registration_handlers(bot)
    
    assert register_handler is not None, "Register handler not registered"
    
    # Call handler
    register_handler(message)
    
    # Assert response
    bot.reply_to.assert_called_once()
    response = bot.reply_to.call_args[0][1]
    assert "Registration process started" in response
    assert "Please enter your full name" in response
    
    # Assert next step handler was registered
    bot.register_next_step_handler.assert_called_once()
    
    # Verify user was added to database
    result = test_db.cursor.execute('SELECT registration_status FROM users WHERE user_id = ?', (message.from_user.id,)).fetchone()
    assert result is not None, "User should exist in database"
    assert result[0] == 'pending', "User should have pending status"

def test_register_command_existing_request(test_db):
    """Test /register command for user with existing request"""
    # Reset database state completely
    test_db.cursor.execute('DROP TABLE IF EXISTS users')
    test_db.cursor.execute('DROP TABLE IF EXISTS registration_requests')
    test_db.cursor.execute('DROP TABLE IF EXISTS user_actions')
    test_db.conn.commit()
    
    # Recreate tables (same as above)
    test_db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registration_status TEXT DEFAULT 'pending',
            approved_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    test_db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS registration_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT,
            full_name TEXT,
            status TEXT DEFAULT 'pending',
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    test_db.conn.commit()
    
    # Setup test data
    user_id = 123456789
    test_db.add_user(
        user_id=user_id,
        username='testuser',
        first_name='Test',
        last_name='User'
    )
    test_db.create_registration_request(
        user_id=user_id,
        email='test@example.com',
        full_name='Test User'
    )
    
    bot = Mock()
    register_handler = None
    
    def message_handler_mock(*args, **kwargs):
        def decorator(func):
            nonlocal register_handler
            if kwargs.get('commands') == [CMD_REGISTER]:
                register_handler = func
            return func
        return decorator
    
    bot.message_handler = message_handler_mock
    
    # Register handlers
    register_registration_handlers(bot)
    
    assert register_handler is not None, "Register handler not registered"
    
    # Mock message
    message = Mock()
    message.from_user.id = user_id
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.chat.id = user_id
    
    # Call handler
    register_handler(message)
    
    # Assert response
    bot.reply_to.assert_called_once()
    response = bot.reply_to.call_args[0][1]
    assert "🎉 Registration process started!\n\nPlease enter your full name:" in response
