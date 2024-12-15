from .events import register_event_handlers
from .core import register_core_handlers

def register_drive_handlers(bot):
    """Register all drive-related handlers"""
    event_handlers = register_event_handlers(bot)
    core_handlers = register_core_handlers(bot)
    
    return {
        **event_handlers,
        **core_handlers
    }

__all__ = ['register_drive_handlers']
