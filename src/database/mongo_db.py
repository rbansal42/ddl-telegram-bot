import os
from datetime import datetime
from typing import Optional, List, Dict
from pymongo import MongoClient
from dotenv import load_dotenv

class MongoDB:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDB, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        load_dotenv()
        
        # Get MongoDB URI from environment variables
        mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        
        # Connect to MongoDB
        self.client = MongoClient(mongodb_uri)
        self.db = self.client.telegram_bot_db
        
        # Initialize collections
        self.users = self.db.users
        self.registration_requests = self.db.registration_requests
        self.folders = self.db.folders
        self.user_actions = self.db.user_actions
        
        # Create indexes
        self.users.create_index('user_id', unique=True)
        self.registration_requests.create_index('user_id')
        self.folders.create_index('folder_id', unique=True)
        
    def close(self):
        if hasattr(self, 'client'):
            self.client.close() 