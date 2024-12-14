import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
import threading
import os


class BotDB:
    _instance = None
    _local = threading.local()

    def __init__(self, db_file='bot.db'):
        self.db_file = db_file
        self._create_connection()
        self.init_db()
        self.init_admin()

    def _create_connection(self):
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self._local.cursor = self._local.conn.cursor()

    @property
    def conn(self):
        if not hasattr(self._local, 'conn'):
            self._create_connection()
        return self._local.conn

    @property
    def cursor(self):
        if not hasattr(self._local, 'cursor'):
            self._create_connection()
        return self._local.cursor
    def init_db(self):
        # Users table with registration status and role
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                registration_status TEXT DEFAULT 'pending',
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_by INTEGER,
                FOREIGN KEY (approved_by) REFERENCES users(user_id)
            )
        ''')

        # Registration requests table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS registration_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT DEFAULT 'pending',
                admin_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                processed_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (processed_by) REFERENCES users(user_id)
            )
        ''')

        # Folders table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                folder_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                drive_url TEXT NOT NULL,
                event_date DATE,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        ''')

        # User actions log table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_type TEXT,
                action_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        self.conn.commit()

    def init_admin(self):
        admin_id = os.getenv("ADMIN_ID")
        if not admin_id:
            raise ValueError("ADMIN_ID not set in environment variables")
        
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, registration_status, role, approved_by) 
                VALUES (?, 'approved', 'admin', ?)
            ''', (int(admin_id), int(admin_id)))
            self.conn.commit()
        except Exception as e:
            print(f"Error initializing admin: {e}")

    def close(self):
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn
            del self._local.cursor

    def __del__(self):
        self.close()

    def create_registration_request(self, user_id, email, full_name):
        try:
            # Split full name into first and last name
            name_parts = full_name.split(maxsplit=1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            self.cursor.execute('''
                INSERT INTO registration_requests (user_id, status)
                VALUES (?, 'pending')
            ''', (user_id,))
            
            self.cursor.execute('''
                UPDATE users 
                SET email = ?, first_name = ?, last_name = ?
                WHERE user_id = ?
            ''', (email, first_name, last_name, user_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error creating registration request: {e}")
            return False

    def get_pending_registrations(self):
        self.cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, u.last_name, 
                   u.email, u.organization, u.registration_reason, r.request_id
            FROM users u
            JOIN registration_requests r ON u.user_id = r.user_id
            WHERE r.status = 'pending'
        ''')
        return self.cursor.fetchall()

    def process_registration(self, request_id, admin_id, approved, response):
        try:
            status = 'approved' if approved else 'rejected'
            self.cursor.execute('''
                UPDATE registration_requests 
                SET status = ?, processed_by = ?, processed_at = CURRENT_TIMESTAMP,
                    admin_response = ?
                WHERE request_id = ?
            ''', (status, admin_id, response, request_id))
            
            if approved:
                self.cursor.execute('''
                    UPDATE users 
                    SET registration_status = 'approved', approved_by = ?
                    WHERE user_id = (
                        SELECT user_id FROM registration_requests WHERE request_id = ?
                    )
                ''', (admin_id, request_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error processing registration: {e}")
            return False

    def add_user(self, user_id: int, username: str, first_name: str, last_name: str) -> bool:
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding user: {e}")
            return False

    def log_folder_creation(self, folder_id: str, name: str, url: str, user_id: int, event_date: str = None) -> bool:
        try:
            self.cursor.execute('''
                INSERT INTO folders (folder_id, name, drive_url, created_by, event_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (folder_id, name, url, user_id, event_date))
            
            self.log_action(user_id, 'create_folder', f"Created folder: {name} for event date: {event_date}")
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error logging folder creation: {e}")
            return False

    def log_action(self, user_id: int, action_type: str, action_data: str) -> bool:
        try:
            self.cursor.execute('''
                INSERT INTO user_actions (user_id, action_type, action_data)
                VALUES (?, ?, ?)
            ''', (user_id, action_type, action_data))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error logging action: {e}")
            return False

    def is_user_registered(self, user_id: int) -> bool:
        try:
            self.cursor.execute('''
                SELECT registration_status 
                FROM users 
                WHERE user_id = ?
            ''', (user_id,))
            result = self.cursor.fetchone()
            return result is not None and result[0] == 'approved'
        except Exception as e:
            print(f"Error checking user registration: {e}")
            return False