import os
import pymongo
from datetime import datetime, UTC
from typing import Optional, List, Dict
import threading
from src.database.roles import Role, Permissions
from bson.objectid import ObjectId

class MongoDB:
    _instance = None
    _local = threading.local()

    def __init__(self):
        """Initialize MongoDB connection"""
        # Get MongoDB configuration from environment
        host = os.getenv('MONGODB_HOST', 'mongodb://localhost:27017')
        db_name = os.getenv('MONGODB_DB_NAME', 'ddl_bot_db')
        
        # Validate configuration
        if not host:
            raise ValueError("MONGODB_HOST not set in environment variables")
        if not db_name:
            raise ValueError("MONGODB_DB_NAME not set in environment variables")
            
        self.host = host
        self.db_name = db_name
        
        # Initialize connection
        self._create_connection()
        self.init_db()
        self.init_admin()

    def _create_connection(self):
        """Create MongoDB connection"""
        if not hasattr(self._local, 'client'):
            self._local.client = pymongo.MongoClient(self.host)
            self._local.db = self._local.client[self.db_name]

    @property
    def client(self):
        if not hasattr(self._local, 'client'):
            self._create_connection()
        return self._local.client

    @property
    def db(self):
        if not hasattr(self._local, 'db'):
            self._create_connection()
        return self._local.db

    @property
    def users(self):
        return self.db.users

    @property
    def registration_requests(self):
        return self.db.registration_requests

    @property
    def user_actions(self):
        return self.db.user_actions

    @property
    def folders(self):
        return self.db.folders

    def init_db(self):
        """Initialize database collections and indexes"""
        # Create indexes for users collection
        self.users.create_index('user_id', unique=True)
        self.users.create_index('username')
        self.users.create_index('email')

        # Create indexes for registration_requests collection
        self.registration_requests.create_index('user_id')
        self.registration_requests.create_index('status')

        # Create indexes for user_actions collection
        self.user_actions.create_index('user_id')
        self.user_actions.create_index('timestamp')

    def init_admin(self):
        """Initialize owner user with complete details"""
        owner_id = os.getenv("OWNER_ID")
        if not owner_id:
            raise ValueError("OWNER_ID not set in environment variables")
        
        try:
            # Split owner name into first and last name
            full_name = os.getenv("OWNER_NAME", "Rahul Bansal")
            name_parts = full_name.split(maxsplit=1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            self.users.update_one(
                {'user_id': int(owner_id)},
                {
                    '$set': {
                        'user_id': int(owner_id),
                        'username': os.getenv("OWNER_USERNAME", "rbansal42"),
                        'email': os.getenv("OWNER_EMAIL", "rtrrahulbansal@gmail.com"),
                        'first_name': first_name,
                        'last_name': last_name,
                        'registration_status': 'approved',
                        'role': Role.OWNER.name.lower(),
                        'approved_by': int(owner_id),
                        'created_at': datetime.now(UTC),
                        'approved_at': datetime.now(UTC)
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"Error initializing owner: {e}")

    def close(self):
        """Close MongoDB connection"""
        if hasattr(self._local, 'client'):
            self._local.client.close()
            del self._local.client
            del self._local.db

    def add_user(self, user_id: int, username: str, first_name: str, last_name: str) -> bool:
        """Add a new user or update existing user"""
        try:
            result = self.users.update_one(
                {'user_id': user_id},
                {
                    '$set': {
                        'user_id': user_id,
                        'username': username,
                        'first_name': first_name,
                        'last_name': last_name,
                        'registration_status': 'pending',
                        'created_at': datetime.now(UTC)
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            print(f"Error adding user: {e}")
            return False

    def create_registration_request(self, user_id: int, username: str, first_name: str, last_name: str, email: str) -> bool:
        """Create a new registration request"""
        try:
            # Check if there's already a pending request
            existing = self.registration_requests.find_one({
                'user_id': user_id,
                'status': 'pending'
            })
            if existing:
                return False

            # Create new request
            request = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'status': 'pending',
                'created_at': datetime.now(UTC)
            }
            result = self.registration_requests.insert_one(request)
            return bool(result.inserted_id)
            
        except Exception as e:
            print(f"Error creating registration request: {e}")
            return False

    def get_pending_registrations(self):
        """Get all pending registration requests"""
        try:
            # Simpler query without join since all data is in registration_requests
            results = list(self.registration_requests.find({'status': 'pending'}))
            pending = []
            
            for doc in results:
                pending.append((
                    doc['user_id'],
                    doc['username'],
                    doc['first_name'],
                    doc['last_name'],
                    doc['email'],
                    doc['status'],
                    str(doc['_id'])
                ))
            return pending
        except Exception as e:
            print(f"Error getting pending registrations: {e}")
            return []

    def process_registration(self, request_id: str, admin_id: int, approved: bool, response: str) -> tuple[bool, int]:
        """Process a registration request (approve/reject)
        Returns: (success: bool, user_id: int)"""
        try:
            request = self.registration_requests.find_one({'_id': ObjectId(request_id)})
            if not request:
                return False, 0
            
            user_id = request['user_id']
            
            # Update request status
            self.registration_requests.update_one(
                {'_id': ObjectId(request_id)},
                {
                    '$set': {
                        'status': 'approved' if approved else 'rejected',
                        'response': response,
                        'processed_by': admin_id,
                        'processed_at': datetime.now(UTC)
                    }
                }
            )
            
            # If approved, create user in users collection
            if approved:
                self.users.insert_one({
                    'user_id': request['user_id'],
                    'username': request['username'],
                    'first_name': request['first_name'],
                    'last_name': request['last_name'],
                    'email': request['email'],
                    'registration_status': 'approved',
                    'role': 'member',
                    'approved_by': {
                        'user_id': admin_id,
                        'username': os.getenv("ADMIN_USERNAME", "admin"),
                        'first_name': os.getenv("ADMIN_NAME", "Admin"),
                        'email': os.getenv("ADMIN_EMAIL", "admin@example.com")
                    },
                    'approved_at': datetime.now(UTC),
                    'created_at': datetime.now(UTC)
                })
            
            return True, user_id
            
        except Exception as e:
            print(f"Error processing registration: {e}")
            return False, 0

    def is_user_registered(self, user_id: int) -> bool:
        """Check if a user is registered and approved"""
        user = self.users.find_one({'user_id': user_id})
        return bool(user and user.get('registration_status') == 'approved')

    def log_action(self, user_id: int, action_type: str, action_data: str) -> bool:
        """Log user action"""
        try:
            self.user_actions.insert_one({
                'user_id': user_id,
                'action_type': action_type,
                'action_data': action_data,
                'timestamp': datetime.now(UTC)
            })
            return True
        except Exception as e:
            print(f"Error logging action: {e}")
            return False
