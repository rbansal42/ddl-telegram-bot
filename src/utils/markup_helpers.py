from telebot import types
from typing import List, Dict, Union, Tuple

def create_list_markup(
    items: Dict,
    display_fields: List[Tuple[str, str]],
    actions: List[Tuple[str, str, str]],
    item_id_field='user_id'
) -> types.InlineKeyboardMarkup:
    """
    Create a consistent markup for lists with action buttons.
    
    Args:
        items: Dictionary containing item data
        display_fields: List of tuples (field_name, emoji) for display
        actions: List of tuples (emoji, text, callback_prefix)
        item_id_field: Field name to use as ID in callback data
    
    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup()
    
    # Create info display buttons (non-functional)
    for field, emoji in display_fields:
        value = items.get(field, 'N/A')
        if isinstance(value, (list, dict)):
            continue
        info_button = types.InlineKeyboardButton(
            text=f"{emoji} {value}",
            callback_data=f"info_{items[item_id_field]}"  # Non-functional
        )
        markup.add(info_button)
    
    # Create action buttons row
    action_buttons = []
    for emoji, text, callback_prefix in actions:
        action_buttons.append(
            types.InlineKeyboardButton(
                f"{emoji} {text}",
                callback_data=f"{callback_prefix}_{items[item_id_field]}"
            )
        )
    markup.row(*action_buttons)
    
    return markup

def create_registration_markup(pending_request: Dict) -> types.InlineKeyboardMarkup:
    """Create markup for pending registration requests"""
    display_fields = [
        ('full_name', '👤'),
        ('email', '📧')
    ]
    actions = [
        ('✅', 'Approve', 'approve'),
        ('❌', 'Reject', 'reject')
    ]
    return create_list_markup(pending_request, display_fields, actions, 'request_id')

def create_member_list_markup(member: Dict, page: int, total_pages: int) -> types.InlineKeyboardMarkup:
    """Create markup for paginated member list"""
    display_fields = [
        ('username', '@'),
        ('full_name', '👤')
    ]
    
    # Create navigation buttons
    navigation_buttons = []
    if page > 1:
        navigation_buttons.append(('⬅️', 'Previous', f'members_{page-1}'))
    if page < total_pages:
        navigation_buttons.append(('➡️', 'Next', f'members_{page+1}'))
    
    return create_list_markup(member, display_fields, navigation_buttons)

def create_admin_list_markup(admin: Dict) -> types.InlineKeyboardMarkup:
    """Create markup for admin list"""
    # Format admin data for display
    formatted_admin = {
        'user_id': admin.get('user_id'),
        'username': admin.get('username', 'N/A'),
        'full_name': f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip() or 'N/A'
    }

    display_fields = [
        ('username', '@'),
        ('full_name', '👤'),
        ('user_id', '🆔')
    ]
    actions = [('⬇️', 'Demote', 'demote')]
    return create_list_markup(formatted_admin, display_fields, actions)

def create_promotion_markup(member: Dict) -> types.InlineKeyboardMarkup:
    """Create markup for member promotion list"""
    display_fields = [
        ('full_name', '👤'),
        ('user_id', '🆔')
    ]
    actions = [('⬆️', 'Promote', 'promote')]
    return create_list_markup(member, display_fields, actions, 'user_id') 