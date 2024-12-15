class UserStateManager:
    def __init__(self):
        self._states = {}
    
    def set_state(self, user_id: int, data: dict):
        self._states[user_id] = data
    
    def get_state(self, user_id: int) -> dict:
        return self._states.get(user_id, {})
    
    def clear_state(self, user_id: int):
        self._states.pop(user_id, None) 