import pytest
from datetime import datetime
from src.database.db import BotDB
import os

def test_init_db(test_db):
    """Test database initialization"""
    # Check if tables exist
    tables = test_db.cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table'
    """).fetchall()
    
    table_names = [table[0] for table in tables]
    
    assert 'users' in table_names
    assert 'registration_requests' in table_names
    assert 'user_actions' in table_names

def test_add_user(test_db):
    """Test adding a new user"""
    test_user = {
        'user_id': 123456789,
        'username': 'testuser',
        'first_name': 'Test',
        'last_name': 'User'
    }
    
    # Add user
    success = test_db.add_user(**test_user)
    assert success is True
    
    # Verify user was added
    user = test_db.cursor.execute(
        'SELECT * FROM users WHERE user_id = ?', 
        (test_user['user_id'],)
    ).fetchone()
    
    assert user is not None
    assert user[0] == test_user['user_id']
    assert user[1] == test_user['username']
    assert user[2] == test_user['first_name']
    assert user[3] == test_user['last_name']

def test_create_registration_request(test_db):
    """Test creating a registration request"""
    # First add a user
    test_user = {
        'user_id': 123456789,
        'username': 'testuser',
        'first_name': 'Test',
        'last_name': 'User'
    }
    test_db.add_user(**test_user)
    
    # Create registration request
    success = test_db.create_registration_request(
        user_id=test_user['user_id'],
        email='test@example.com',
        full_name='Test User'
    )
    
    assert success is True
    
    # Verify request was created
    request = test_db.cursor.execute('''
        SELECT status FROM registration_requests 
        WHERE user_id = ?
    ''', (test_user['user_id'],)).fetchone()
    
    assert request is not None
    assert request[0] == 'pending'

def test_get_pending_registrations(test_db):
    """Test retrieving pending registration requests"""
    # Add test users and their registration requests
    test_users = [
        {
            'user_id': 123456789,
            'username': 'testuser1',
            'first_name': 'Test1',
            'last_name': 'User1',
            'email': 'test1@example.com'
        },
        {
            'user_id': 987654321,
            'username': 'testuser2',
            'first_name': 'Test2',
            'last_name': 'User2',
            'email': 'test2@example.com'
        }
    ]
    
    for user in test_users:
        test_db.add_user(
            user_id=user['user_id'],
            username=user['username'],
            first_name=user['first_name'],
            last_name=user['last_name']
        )
        test_db.create_registration_request(
            user_id=user['user_id'],
            email=user['email'],
            full_name=f"{user['first_name']} {user['last_name']}"
        )
    
    # Get pending registrations
    pending = test_db.get_pending_registrations()
    
    assert len(pending) == 2
    for i, registration in enumerate(pending):
        user = test_users[i]
        assert registration[0] == user['user_id']      # user_id
        assert registration[1] == user['username']     # username
        assert registration[2] == user['first_name']   # first_name
        assert registration[3] == user['last_name']    # last_name
        assert registration[4] == user['email']        # email
        assert registration[5] == 'pending'            # status
        assert registration[6] is not None             # request_id

def test_process_registration(test_db):
    """Test processing (approving/rejecting) registration requests"""
    # Setup test user and registration request
    user_id = 123456789
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    admin_id = int(admin_ids_str.split(',')[0])  # Use first admin ID
    
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
    
    # Test approval
    success = test_db.process_registration(
        request_id=1,  # First request
        admin_id=admin_id,
        approved=True,
        response="Approved by admin"
    )
    assert success is True
    
    # Verify user status was updated
    user_status = test_db.cursor.execute(
        'SELECT registration_status FROM users WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    assert user_status[0] == 'approved'

def test_is_user_registered(test_db):
    """Test checking user registration status"""
    # Setup test user
    user_id = 123456789
    test_db.add_user(
        user_id=user_id,
        username='testuser',
        first_name='Test',
        last_name='User'
    )
    
    # Initially should be unregistered
    assert test_db.is_user_registered(user_id) is False
    
    # After approval should be registered
    test_db.cursor.execute(
        'UPDATE users SET registration_status = ? WHERE user_id = ?',
        ('approved', user_id)
    )
    test_db.conn.commit()
    
    assert test_db.is_user_registered(user_id) is True