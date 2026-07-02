"""
Repository Layer: Gym Trainer Data Access
Handles MongoDB interactions for exercise logs and workout statistics.
"""

from typing import List, Optional, Dict, Any
from pymongo.errors import PyMongoError
from app.database import exercise_logs_col


class GymTrainerRepository:
    """Repository for exercise logging and statistics retrieval."""

    @staticmethod
    async def get_latest_workout_stats(user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent exercise log for a user."""
        try:
            cursor = exercise_logs_col.find({"user_id": user_id}).sort("timestamp", -1).limit(1)
            logs = await cursor.to_list(length=1)
            return logs[0] if logs else None
        except Exception as e:
            print(f"[DB_WARNING] Failed to retrieve latest workout stats: {e}")
            # Return empty result instead of raising - user hasn't logged yet
            return None

    @staticmethod
    async def save_exercise_log(user_id: str, exercise_data: Dict[str, Any]) -> None:
        """Persist exercise log to database."""
        try:
            await exercise_logs_col.insert_one({
                "user_id": user_id,
                **exercise_data
            })
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to save exercise log: {e}")
            raise
