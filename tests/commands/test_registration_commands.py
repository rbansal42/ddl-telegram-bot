import pytest
from unittest.mock import Mock, patch
from bson import ObjectId
from src.commands import CMD_REGISTER
from src.commands.registration_commands import register_registration_handlers
from src.database.roles import Role
from src.utils.notifications import NotificationType
from src.utils.user_actions import ActionType

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

def test_pending_command_non_admin(test_db):
    """Test /pending command access by non-admin user"""
    bot = Mock()
    pending_handler = None
    
    def message_handler_mock(*args, **kwargs):
        def decorator(func):
            nonlocal pending_handler
            if kwargs.get('commands') == ['pending']:
                pending_handler = func
            return func
        return decorator
    
    bot.message_handler = message_handler_mock
    
    # Mock message from non-admin user
    message = Mock()
    message.from_user.id = 123456789  # Non-admin ID
    
    with patch('src.middleware.auth.is_admin', return_value=False):
        register_registration_handlers(bot)
        
        assert pending_handler is not None, "Pending handler not registered"
        
        # Call handler
        pending_handler(message)
        
        # Assert response
        bot.reply_to.assert_called_once_with(
            message, 
            "❌ This command is only available to admins."
        )

def test_pending_command_no_requests(test_db):
    """Test /pending command with no pending requests"""
    # Reset database state
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
    pending_handler = None
    
    def message_handler_mock(*args, **kwargs):
        def decorator(func):
            nonlocal pending_handler
            if kwargs.get('commands') == ['pending']:
                pending_handler = func
            return func
        return decorator
    
    bot.message_handler = message_handler_mock
    
    # Mock message from admin user
    message = Mock()
    message.from_user.id = 123456789
    message.chat.id = 123456789
    
    with patch('src.commands.registration_commands.is_admin', return_value=True):
        register_registration_handlers(bot)
        
        assert pending_handler is not None, "Pending handler not registered"
        
        # Call handler
        pending_handler(message)
        
        # Assert response
        bot.reply_to.assert_called_once_with(message, "No pending registrations.")

def test_pending_command_with_requests(test_db):
    """Test /pending command with pending requests"""
    # Reset and recreate database
    test_db.cursor.execute('DROP TABLE IF EXISTS users')
    test_db.cursor.execute('DROP TABLE IF EXISTS registration_requests')
    test_db.cursor.execute('DROP TABLE IF EXISTS user_actions')
    test_db.conn.commit()
    
    # Recreate tables with correct structure
    test_db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registration_status TEXT DEFAULT 'pending',
            approved_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            email TEXT
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
    
    # Add test user and registration request
    test_db.add_user(
        user_id=123456789,
        username='testuser',
        first_name='Test',
        last_name='User'
    )
    
    # Update email in users table
    test_db.cursor.execute(
        'UPDATE users SET email = ? WHERE user_id = ?',
        ('test@example.com', 123456789)
    )
    
    test_db.create_registration_request(
        user_id=123456789,
        email='test@example.com',
        full_name='Test User'
    )
    test_db.conn.commit()
    
    bot = Mock()
    pending_handler = None
    
    def message_handler_mock(*args, **kwargs):
        def decorator(func):
            nonlocal pending_handler
            if kwargs.get('commands') == ['pending']:
                pending_handler = func
            return func
        return decorator
    
    bot.message_handler = message_handler_mock
    bot.send_message = Mock()
    
    # Mock message from admin user
    message = Mock()
    message.from_user.id = 123456789
    message.chat.id = 123456789
    
    with patch('src.commands.registration_commands.is_admin', return_value=True):
        register_registration_handlers(bot)
        
        assert pending_handler is not None, "Pending handler not registered"
        
        # Call handler
        pending_handler(message)
        
        # Assert response
        bot.send_message.assert_called_once()
        sent_message = bot.send_message.call_args[0]
        
        # Verify exact message format
        expected_text = (
            "📝 Registration Request #1\n"
            "User ID: 123456789\n"
            "Username: @testuser\n"
            "Name: Test User\n"
            "Email: test@example.com"
        )
        assert sent_message[1] == expected_text
        
        # Verify markup buttons
        markup = sent_message[2]['reply_markup']
        assert len(markup.keyboard) == 1
        row = markup.keyboard[0]
        assert len(row) == 2
        assert row[0].text == "�� Approve"
        assert row[1].text == "❌ Reject"
        assert row[0].callback_data == "approve_1"
        assert row[1].callback_data == "reject_1"
