# Standard library imports
import os
from datetime import datetime
from typing import Optional, List, Union, Tuple

# Third-party imports
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from telebot.types import Message

# Local application imports
from src.utils.user_actions import log_action, ActionType

def format_file_size(size_in_bytes: int) -> str:
    """Convert file size to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.1f} GB"

def format_timestamp(timestamp: Union[str, datetime]) -> str:
    """Format timestamp to human readable format"""
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") 

def get_file_info(message: Message) -> Tuple[str, str, Optional[str]]:
    """
    Get file information based on message type
    Returns: (file_type, file_name, file_size)
    """
    if message.document:
        file_type = "document"
        file_name = message.document.file_name
        file_size = format_file_size(message.document.file_size)
    elif message.photo:
        file_type = "photo"
        file_name = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_size = format_file_size(message.photo[-1].file_size)
    elif message.video:
        file_type = "video"
        file_name = message.video.file_name or f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        file_size = format_file_size(message.video.file_size)
    elif message.audio:
        file_type = "audio"
        file_name = message.audio.file_name or f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        file_size = format_file_size(message.audio.file_size)
    else:
        raise ValueError("Unsupported file type")
        
    return file_type, file_name, file_size