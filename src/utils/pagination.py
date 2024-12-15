from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def paginate_items(items, page: int, page_size: int = 5):
    """Handle pagination calculations and return current page items"""
    total_items = len(items)
    total_pages = (total_items + page_size - 1) // page_size
    
    # Validate page number
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    current_items = items[start_idx:end_idx]
    
    return {
        'current_items': current_items,
        'page': page,
        'total_pages': total_pages,
        'has_previous': page > 1,
        'has_next': page < total_pages
    }