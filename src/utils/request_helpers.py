import time
from functools import wraps
from requests.exceptions import ReadTimeout, ConnectionError
from telebot.apihelper import ApiException

def retry_on_timeout(max_retries=3, initial_delay=11):
    """
    Decorator to retry functions on timeout with exponential backoff
    
    Args:
        max_retries (int): Maximum number of retry attempts
        initial_delay (int): Initial delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ReadTimeout, ConnectionError, ApiException) as e:
                    last_exception = e
                    if attempt == max_retries - 1:  # Last attempt
                        raise last_exception
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
            
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator 