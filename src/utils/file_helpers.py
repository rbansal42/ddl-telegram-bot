from datetime import datetime
from typing import Union

def format_file_size(size_bytes: int) -> str:
    """Format file size from bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

def format_timestamp(timestamp: Union[str, datetime]) -> str:
    """Format timestamp to human readable format"""
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") 