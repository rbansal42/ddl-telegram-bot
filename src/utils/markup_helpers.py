from telebot import types
from typing import List, Dict, Union, Tuple

def create_list_markup(
    items: List[Dict],
    display_fields: List[Tuple[str, str]],
    actions: List[Tuple[str, str, str]],
    item_id_field: str = 'id'
) -> Tuple[types.InlineKeyboardMarkup, str]:
    """
    Create a consistent markup for lists with action buttons.
    
    Args:
        items: List of dictionaries containing item data
        display_fields: List of tuples (field_name, emoji) for display
        actions: List of tuples (emoji, text, callback_prefix)
        item_id_field: Field name to use as ID in callback data
    
    Returns:
        Tuple of (InlineKeyboardMarkup, formatted_text)
    """
    markup = types.InlineKeyboardMarkup()
    
    for item in items:
        # Create info display buttons (non-functional)
        for field, emoji in display_fields:
            value = item.get(field, 'N/A')
            if isinstance(value, (list, dict)):
                continue
            info_button = types.InlineKeyboardButton(
                text=f"{emoji} {value}",
                callback_data=f"info_{item[item_id_field]}"  # Non-functional
            )
            markup.add(info_button)
        
        # Create action buttons row
        action_buttons = []
        for emoji, text, callback_prefix in actions:
            action_buttons.append(
                types.InlineKeyboardButton(
                    f"{emoji} {text}",
                    callback_data=f"{callback_prefix}_{item[item_id_field]}"
                )
            )
        markup.row(*action_buttons)
        
        # Add separator between items (if not last item)
        if item != items[-1]:
            separator = types.InlineKeyboardButton(
                "➖" * 10,
                callback_data=f"separator_{item[item_id_field]}"
            )
            markup.add(separator)
    
    return markup

# Example usage for different scenarios:
def create_registration_markup(pending_requests: List[Dict]) -> Tuple[types.InlineKeyboardMarkup, str]:
    """Create markup for pending registration requests"""
    display_fields = [
        ('full_name', '👤'),
        ('email', '📧')
    ]
    actions = [
        ('✅', 'Approve', 'approve'),
        ('❌', 'Reject', 'reject')
    ]
    return create_list_markup(pending_requests, display_fields, actions, 'request_id')

def create_member_list_markup(members: List[Dict], page: int, total_pages: int) -> Tuple[types.InlineKeyboardMarkup, str]:
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
    
    return create_list_markup(members, display_fields, navigation_buttons)

def create_admin_list_markup(admins: List[Dict]) -> Tuple[types.InlineKeyboardMarkup, str]:
    """Create markup for admin list"""
    # Format admin data for display
    formatted_admins = []
    for admin in admins:
        formatted_admins.append({
            'user_id': admin.get('user_id'),
            'username': admin.get('username', 'N/A'),
            'full_name': f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip() or 'N/A'
        })

    display_fields = [
        ('username', '@'),
        ('full_name', '👤'),
        ('user_id', '🆔')
    ]
    actions = [('⬇️', 'Demote', 'demote')]
    markup, _ = create_list_markup(formatted_admins, display_fields, actions)
    return markup

def create_promotion_markup(members: List[Dict]) -> Tuple[types.InlineKeyboardMarkup, str]:
    """Create markup for member promotion list"""
    display_fields = [
        ('full_name', '👤'),
        ('user_id', '🆔')
    ]
    actions = [('⬆️', 'Promote', 'promote')]
    return create_list_markup(members, display_fields, actions) 