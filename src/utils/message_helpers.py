from typing import Union, List, Dict, Any
from telebot.types import Message, CallbackQuery

def escape_markdown(text: Union[str, int, float, None]) -> str:
    """
    Escape special characters for Telegram MarkdownV2 format
    
    Args:
        text: Text to escape (can be string, number, or None)
    Returns:
        str: Escaped text safe for MarkdownV2
    """
    if text is None:
        return ''
    
    # Convert input to string
    text = str(text)
    
    # Characters that need escaping in MarkdownV2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Escape backslash first to prevent double escaping
    text = text.replace('\\', '\\\\')
    
    # Escape special characters
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
        
    return text

def format_message(template: str, **kwargs: Any) -> str:
    """
    Format a message template with escaped values for MarkdownV2
    
    Args:
        template: Message template with placeholders
        kwargs: Key-value pairs for template placeholders
    Returns:
        str: Formatted message with escaped values
    """
    # Escape all values in kwargs
    escaped_kwargs = {k: escape_markdown(v) for k, v in kwargs.items()}
    
    try:
        # Format the template with escaped values
        return template.format(**escaped_kwargs)
    except KeyError as e:
        raise KeyError(f"Missing template key: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error formatting message: {str(e)}")

def create_list_message(
    title: str,
    items: List[Dict[str, Any]],
    item_template: str,
    empty_message: str = "No items found."
) -> str:
    """
    Create a formatted list message with proper escaping
    
    Args:
        title: Message title
        items: List of dictionaries containing item data
        item_template: Template for each item
        empty_message: Message to show when items list is empty
    Returns:
        str: Formatted message with escaped values
    """
    if not items:
        return f"{escape_markdown(title)}\n\n{escape_markdown(empty_message)}"
    
    message = f"{escape_markdown(title)}\n\n"
    
    for item in items:
        try:
            # Escape all values in the item dictionary
            escaped_item = {k: escape_markdown(v) for k, v in item.items()}
            message += item_template.format(**escaped_item) + "\n"
        except Exception as e:
            print(f"Error formatting item: {str(e)}")
            continue
            
    return message 