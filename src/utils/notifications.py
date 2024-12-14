from enum import Enum
from typing import Optional
from telebot import TeleBot
from src.database.roles import Role

class NotificationType(Enum):
    # Role changes
    PROMOTION_TO_ADMIN = "promotion_to_admin"
    DEMOTION_TO_MEMBER = "demotion_to_member"
    
    # Registration
    REGISTRATION_APPROVED = "registration_approved"
    REGISTRATION_REJECTED = "registration_rejected"
    
    # Access
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"
    
    # Warnings
    WARNING_ISSUED = "warning_issued"
    WARNING_RESOLVED = "warning_resolved"
    
    # Account
    ACCOUNT_SUSPENDED = "account_suspended"
    ACCOUNT_REACTIVATED = "account_reactivated"
    
    # Events
    EVENT_ROLE_ADDED = "event_role_added"
    EVENT_ROLE_REMOVED = "event_role_removed"

def notify_user(
    bot: TeleBot,
    notification_type: NotificationType,
    receiver_id: int,
    issuer_id: Optional[int] = None,
    additional_data: Optional[dict] = None
) -> bool:
    """
    Send notification to user about changes in their status/role/access
    
    Args:
        bot: Telegram bot instance
        notification_type: Type of notification to send
        receiver_id: User ID of the notification receiver
        issuer_id: User ID of the person who initiated the change (optional)
        additional_data: Any additional data needed for the notification (optional)
    
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    try:
        notification_messages = {
            # Role changes
            NotificationType.PROMOTION_TO_ADMIN: (
                "🎉 *Congratulations!* You have been promoted to admin.\n"
                "Use /adminhelp to see available admin commands."
            ),
            NotificationType.DEMOTION_TO_MEMBER: (
                "ℹ️ Your admin privileges have been revoked.\n"
                "You now have regular member access."
            ),
            
            # Registration
            NotificationType.REGISTRATION_APPROVED: (
                "🎉 *Congratulations!* Your registration has been approved!\n"
                "You now have access to all bot features. Use /help to see available commands."
            ),
            NotificationType.REGISTRATION_REJECTED: (
                "❌ Your registration request has been rejected.\n"
                "Please contact an administrator for more information."
            ),
            
            # Access
            NotificationType.ACCESS_GRANTED: (
                "✅ You have been granted access to: {resource}\n"
                "You can now access this resource."
            ),
            NotificationType.ACCESS_REVOKED: (
                "⚠️ Your access to {resource} has been revoked.\n"
                "Please contact an administrator if you think this is a mistake."
            ),
            
            # Warnings
            NotificationType.WARNING_ISSUED: (
                "⚠️ *Warning Notice*\n"
                "Reason: {reason}\n"
                "Please ensure compliance with our guidelines."
            ),
            NotificationType.WARNING_RESOLVED: (
                "✅ Your previous warning has been resolved.\n"
                "Thank you for addressing the issue."
            ),
            
            # Account
            NotificationType.ACCOUNT_SUSPENDED: (
                "🚫 Your account has been suspended.\n"
                "Reason: {reason}\n"
                "Duration: {duration}\n"
                "Contact the administrator for more information."
            ),
            NotificationType.ACCOUNT_REACTIVATED: (
                "✅ Your account has been reactivated.\n"
                "You now have full access to all features."
            ),
            
            # Events
            NotificationType.EVENT_ROLE_ADDED: (
                "✨ You have been assigned a new role in the event: {event_name}\n"
                "Role: {role}\n"
                "Use /help to see your available commands."
            ),
            NotificationType.EVENT_ROLE_REMOVED: (
                "ℹ️ Your role has been removed from the event: {event_name}\n"
                "Previous role: {role}"
            )
        }
        
        # Get base message
        message = notification_messages[notification_type]
        
        # Format message with additional data if provided
        if additional_data:
            message = message.format(**additional_data)
        
        # Send notification
        bot.send_message(
            receiver_id,
            message,
            parse_mode="Markdown"
        )
        
        # Log notification
        print(f"✅ Notification sent: {notification_type.value} to user {receiver_id}")
        if issuer_id:
            print(f"Issued by: {issuer_id}")
            
        return True
        
    except Exception as e:
        print(f"❌ Failed to send notification: {str(e)}")
        print(f"Type: {notification_type.value}")
        print(f"Receiver: {receiver_id}")
        if issuer_id:
            print(f"Issuer: {issuer_id}")
        return False