class UserStateManager:
    def __init__(self):
        self._states = {}
        print("[DEBUG] UserStateManager initialized")
    
    def set_state(self, user_id: int, data: dict):
        print(f"[DEBUG] Setting state for user {user_id}")
        print(f"[DEBUG] State data: {data}")
        self._states[user_id] = data
        print(f"[DEBUG] Current states: {self._states}")
    
    def get_state(self, user_id: int) -> dict:
        state = self._states.get(user_id, {})
        print(f"[DEBUG] Getting state for user {user_id}")
        print(f"[DEBUG] Retrieved state: {state}")
        return state
    
    def clear_state(self, user_id: int):
        print(f"[DEBUG] Clearing state for user {user_id}")
        print(f"[DEBUG] State before clearing: {self._states.get(user_id, {})}")
        self._states.pop(user_id, None)
        print(f"[DEBUG] Current states after clearing: {self._states}") 