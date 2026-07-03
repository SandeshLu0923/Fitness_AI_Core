import datetime
import threading
from copy import deepcopy
from typing import Any, Dict, Optional


_lock = threading.Lock()
_live_stats_by_user: Dict[str, Dict[str, Any]] = {}


def update_live_stats(payload: Dict[str, Any]) -> None:
    user_id = str(payload.get("user_id") or "").strip()
    if not user_id:
        return
    next_payload = deepcopy(payload)
    next_payload.setdefault("timestamp", datetime.datetime.utcnow())
    with _lock:
        _live_stats_by_user[user_id] = next_payload


def get_latest_live_stats(user_id: str, max_age_minutes: int = 45) -> Optional[Dict[str, Any]]:
    key = str(user_id or "").strip()
    if not key:
        return None
    with _lock:
        payload = deepcopy(_live_stats_by_user.get(key))
    if not payload:
        return None

    timestamp = payload.get("timestamp")
    if isinstance(timestamp, datetime.datetime):
        age = datetime.datetime.utcnow() - timestamp
        if age > datetime.timedelta(minutes=max_age_minutes):
            return None
    return payload
