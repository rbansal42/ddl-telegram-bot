class UserStateManager:
    def __init__(self):
        self._states = {}
        print("[DEBUG] UserStateManager initialized")
    
    def set_state(self, user_id: int, data: dict):
        print(f"[DEBUG] Setting state for user {user_id}")
        if 'pending_uploads' not in data and self._states.get(user_id, {}).get('pending_uploads') is not None:
            data['pending_uploads'] = self._states[user_id]['pending_uploads']
            data['total_size'] = self._states[user_id].get('total_size', 0)
            data['status_message_id'] = self._states[user_id].get('status_message_id')
        self._states[user_id] = data
    
    def get_state(self, user_id: int) -> dict:
        state = self._states.get(user_id, {})
        print(f"[DEBUG] Getting state for user {user_id}")
        return state
    
    def add_pending_upload(self, user_id: int, file_info: dict):
        if user_id not in self._states:
            self._states[user_id] = {}
        if 'pending_uploads' not in self._states[user_id]:
            self._states[user_id]['pending_uploads'] = []
            self._states[user_id]['total_size'] = 0
        self._states[user_id]['pending_uploads'].append(file_info)
        self._states[user_id]['total_size'] += int(file_info.get('size_bytes', 0))
    
    def get_pending_uploads(self, user_id: int) -> list:
        return self._states.get(user_id, {}).get('pending_uploads', [])
    
    def clear_pending_uploads(self, user_id: int):
        if user_id in self._states and 'pending_uploads' in self._states[user_id]:
            del self._states[user_id]['pending_uploads']
    
    def clear_state(self, user_id: int):
        print(f"[DEBUG] Clearing state for user {user_id}")
        self._states.pop(user_id, None) 
    
    def get_upload_stats(self, user_id: int) -> tuple:
        state = self._states.get(user_id, {})
        return (
            len(state.get('pending_uploads', [])),
            state.get('total_size', 0)
        )