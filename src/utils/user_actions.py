# Standard library imports
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

# Local application imports
from src.database.mongo_db import MongoDB

class ActionType(Enum):
    # User Management
    USER_REGISTERED = "user_registered"
    USER_APPROVED = "user_approved"
    USER_REJECTED = "user_rejected"
    USER_PROMOTED = "user_promoted"
    USER_DEMOTED = "user_demoted"
    ADMIN_PROMOTION = "admin_promotion"
    ADMIN_DEMOTION = "admin_demotion"
    MEMBER_REMOVAL = "member_removal"
    
    # Access Control
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    
    # Content Management
    FOLDER_CREATED = "folder_created"
    FOLDER_DELETED = "folder_deleted"
    FOLDER_UPDATED = "folder_updated"
    FILE_UPLOADED = "file_uploaded"
    FILE_DELETED = "file_deleted"
    
    # Event Management
    EVENT_CREATED = "event_created"
    EVENT_UPDATED = "event_updated"
    EVENT_DELETED = "event_deleted"
    EVENT_JOINED = "event_joined"
    EVENT_LEFT = "event_left"
    
    # System Actions
    SYSTEM_ERROR = "system_error"
    CONFIG_UPDATED = "config_updated"
    BACKUP_CREATED = "backup_created"
    COMMAND_REFRESH = "command_refresh"
    
    # Administrative Actions
    ADMIN_COMMAND = "admin_command"
    SETTINGS_CHANGED = "settings_changed"
    USER_WARNED = "user_warned"
    USER_BANNED = "user_banned"
    
    # Basic Commands
    COMMAND_START = "command_start"
    COMMAND_HELP = "command_help"
    COMMAND_MYID = "command_myid"
    
    # Fun Commands
    COMMAND_CAT = "command_cat"
    COMMAND_DOG = "command_dog"
    COMMAND_SPACE = "command_space"
    COMMAND_MEME = "command_meme"
    COMMAND_FUNNY = "command_funny"
    
    # Command Status
    COMMAND_SUCCESS = "command_success"
    COMMAND_FAILED = "command_failed"
    COMMAND_UNAUTHORIZED = "command_unauthorized"
    COMMAND_INVALID = "command_invalid"
    
    # Rate Limiting
    RATE_LIMIT_HIT = "rate_limit_hit"
    RATE_LIMIT_WARNING = "rate_limit_warning"

def log_action(
    action_type: ActionType,
    user_id: int,
    target_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    status: str = "success",
    error_message: Optional[str] = None
) -> bool:
    """
    Log a user action to the database
    
    Args:
        action_type: Type of action being performed
        user_id: ID of user performing the action
        target_id: ID of target user/resource (optional)
        metadata: Additional data about the action (optional)
        status: Status of the action (success/failed)
        error_message: Error message if action failed (optional)
    
    Returns:
        bool: True if action was logged successfully, False otherwise
    """
    try:
        db = MongoDB()
        
        action_data = {
            'action_type': action_type.value,
            'user_id': user_id,
            'timestamp': datetime.utcnow(),
            'status': status
        }
        
        if target_id:
            action_data['target_id'] = target_id
            
        if metadata:
            action_data['metadata'] = metadata
            
        if error_message:
            action_data['error_message'] = error_message
            
        # Insert action into database
        db.user_actions.insert_one(action_data)
        
        # Print log message
        print(f"✅ Action logged: {action_type.value}")
        print(f"User: {user_id}")
        if target_id:
            print(f"Target: {target_id}")
        if metadata:
            print(f"Metadata: {metadata}")
        if error_message:
            print(f"Error: {error_message}")
            
        return True
        
    except Exception as e:
        print(f"❌ Failed to log action: {str(e)}")
        print(f"Action Type: {action_type.value}")
        print(f"User ID: {user_id}")
        return False

def get_user_actions(
    user_id: Optional[int] = None,
    action_type: Optional[ActionType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100
) -> list:
    """
    Retrieve user actions from database with optional filters
    
    Args:
        user_id: Filter by specific user (optional)
        action_type: Filter by action type (optional)
        start_date: Filter by start date (optional)
        end_date: Filter by end date (optional)
        limit: Maximum number of actions to return
        
    Returns:
        list: List of matching action records
    """
    try:
        db = MongoDB()
        query = {}
        
        if user_id:
            query['user_id'] = user_id
            
        if action_type:
            query['action_type'] = action_type.value
            
        if start_date or end_date:
            query['timestamp'] = {}
            if start_date:
                query['timestamp']['$gte'] = start_date
            if end_date:
                query['timestamp']['$lte'] = end_date
                
        return list(db.user_actions.find(
            query,
            limit=limit,
            sort=[('timestamp', -1)]
        ))
        
    except Exception as e:
        print(f"❌ Failed to retrieve actions: {str(e)}")
        return [] 