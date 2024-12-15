import os
from pathlib import Path
import tempfile
from typing import Tuple
from datetime import datetime
import shutil

class TempFileHandler:
    def __init__(self):
        self.base_temp_dir = Path(tempfile.gettempdir()) / "telegram_drive_bot"
        self.base_temp_dir.mkdir(exist_ok=True)
    
    def get_user_temp_dir(self, user_id: int) -> str:
        """Get user-specific temporary directory"""
        user_dir = self.base_temp_dir / str(user_id)
        user_dir.mkdir(exist_ok=True)
        return str(user_dir)
    
    def save_telegram_file(self, bot, file_info, file_name: str, user_id: int) -> str:
        """Save telegram file to user's temporary directory"""
        user_dir = Path(self.get_user_temp_dir(user_id))
        temp_path = user_dir / file_name
        
        # Download and save file
        downloaded_file = bot.download_file(file_info.file_path)
        with open(temp_path, 'wb') as f:
            f.write(downloaded_file)
            
        return str(temp_path)
    
    def cleanup_session(self, user_id: int):
        """Clean up all files for a user session"""
        user_dir = Path(self.get_user_temp_dir(user_id))
        if user_dir.exists():
            shutil.rmtree(user_dir)