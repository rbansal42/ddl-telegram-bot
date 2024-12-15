from typing import List, Dict
from src.utils.file_helpers import format_file_size

def format_drive_items(items: List[Dict], include_size: bool = True) -> str:
    """Format drive items (files/folders) into a readable message"""
    folders = [item for item in items if item['mimeType'] == 'application/vnd.google-apps.folder']
    files_only = [item for item in items if item['mimeType'] != 'application/vnd.google-apps.folder']
    
    response = ""
    if folders:
        response += "*Folders:*\n"
        for folder in folders:
            response += f"📁 [{folder['name']}]({folder['webViewLink']})\n"
        response += "\n"
    
    if files_only:
        response += "*Files:*\n"
        for file in files_only:
            file_info = f"📄 [{file['name']}]({file['webViewLink']})"
            if include_size:
                file_size = format_file_size(int(file.get('size', 0))) if 'size' in file else 'N/A'
                file_info += f" - {file_size}"
            response += f"{file_info}\n"
    
    return response 