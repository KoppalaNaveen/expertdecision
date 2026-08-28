import time
from typing import Set, Dict, Optional

class PresenceService:
    """
    Real-Time Online Presence Tracker.
    Users are marked as 'Online' when they log in and maintain an active heartbeat.
    Users inactive for longer than `timeout_seconds` (default 60s) automatically transition to 'Offline'.
    """
    _online_users: Dict[int, float] = {}  # user_id -> last_ping_timestamp

    @classmethod
    def heartbeat(cls, user_id: int):
        if user_id:
            try:
                cls._online_users[int(user_id)] = time.time()
            except (ValueError, TypeError):
                pass

    @classmethod
    def set_offline(cls, user_id: int):
        if user_id:
            try:
                uid = int(user_id)
                if uid in cls._online_users:
                    del cls._online_users[uid]
            except (ValueError, TypeError):
                pass

    @classmethod
    def is_online(cls, user_id: int, timeout_seconds: int = 65) -> bool:
        if not user_id:
            return False
        try:
            uid = int(user_id)
            last_seen = cls._online_users.get(uid)
            if last_seen and (time.time() - last_seen <= timeout_seconds):
                return True
        except (ValueError, TypeError):
            pass
        return False

    @classmethod
    def get_online_user_ids(cls, timeout_seconds: int = 65) -> Set[int]:
        now = time.time()
        return {uid for uid, ts in cls._online_users.items() if (now - ts <= timeout_seconds)}
