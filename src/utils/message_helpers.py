def escape_markdown(text):
    """
    Escape special characters for Telegram MarkdownV2 format
    Args:
        text (str): Text to escape
    Returns:
        str: Escaped text safe for MarkdownV2
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text 