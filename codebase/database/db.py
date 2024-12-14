import sqlite3
from datetime import datetime
from typing import Optional, List, Dict

class BotDB:
    def __init__(self, db_file='bot.db'):
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        # Users table with registration status and role
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                organization TEXT,
                registration_reason TEXT,
                registration_status TEXT DEFAULT 'pending',  -- pending, approved, rejected
                role TEXT DEFAULT 'user',  -- admin, moderator, user
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
        self.conn.commit()

    def create_registration_request(self, user_id, email, organization, reason):
        try:
            self.cursor.execute('''
                INSERT INTO registration_requests (user_id, status)
                VALUES (?, 'pending')
            ''', (user_id,))
            
            self.cursor.execute('''
                UPDATE users 
                SET email = ?, organization = ?, registration_reason = ?
                WHERE user_id = ?
            ''', (email, organization, reason, user_id))
            
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

    def get_user_folders(self, user_id: int) -> List[Dict]:
        self.cursor.execute('''
            SELECT folder_id, name, drive_url, event_date, created_at 
            FROM folders 
            WHERE created_by = ?
            ORDER BY event_date DESC, created_at DESC
        ''', (user_id,))
        
        columns = ['folder_id', 'name', 'drive_url', 'event_date', 'created_at']
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def get_folders_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        self.cursor.execute('''
            SELECT folder_id, name, drive_url, event_date, created_at 
            FROM folders 
            WHERE event_date BETWEEN ? AND ?
            ORDER BY event_date ASC
        ''', (start_date, end_date))
        
        columns = ['folder_id', 'name', 'drive_url', 'event_date', 'created_at']
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def close(self):
        self.conn.close() 