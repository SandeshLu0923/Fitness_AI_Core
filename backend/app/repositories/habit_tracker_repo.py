"""
Repository Layer: Habit Tracker Data Access
Handles MongoDB interactions for macrocycle plans and completion tracking.
"""

import datetime
from typing import List, Optional, Dict, Any
from pymongo.errors import PyMongoError
from app.database import users_col, completed_challenges_col


class HabitTrackerRepository:
    """Repository for macrocycle and habit tracking persistence."""

    @staticmethod
    async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user profile for biometric context."""
        try:
            profile = await users_col.find_one({"user_id": user_id})
            if profile:
                return profile
            # Return default profile if not found
            return {
                "user_id": user_id,
                "age": 25,
                "weight_kg": 70.0,
                "height_cm": 175.0,
                "fitness_goal": "General Fitness"
            }
        except Exception as e:
            print(f"[DB_WARNING] Failed to retrieve user profile, using defaults: {e}")
            # Return default profile as fallback
            return {
                "user_id": user_id,
                "age": 25,
                "weight_kg": 70.0,
                "height_cm": 175.0,
                "fitness_goal": "General Fitness"
            }

    @staticmethod
    async def save_active_macrocycle(user_id: str, tracking_state: Dict[str, Any]) -> None:
        """Persist active macrocycle to user document."""
        try:
            await users_col.update_one(
                {"user_id": user_id},
                {"$set": {"active_macrocycle": tracking_state}},
                upsert=True
            )
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to save active macrocycle: {e}")
            raise

    @staticmethod
    async def get_active_macrocycle(user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve active macrocycle for user."""
        try:
            user = await users_col.find_one({"user_id": user_id})
            return user.get("active_macrocycle") if user else None
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to retrieve active macrocycle: {e}")
            raise

    @staticmethod
    async def increment_active_day(user_id: str) -> None:
        """Increment current_active_day counter."""
        try:
            await users_col.update_one(
                {"user_id": user_id},
                {"$inc": {"active_macrocycle.current_active_day": 1}}
            )
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to increment active day: {e}")
            raise

    @staticmethod
    async def mark_day_completed(user_id: str, day: int) -> None:
        """Mark a specific day as completed."""
        try:
            await users_col.update_one(
                {"user_id": user_id},
                {"$push": {"active_macrocycle.completed_days": day}}
            )
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to mark day completed: {e}")
            raise

    @staticmethod
    async def save_completed_challenge(user_id: str, challenge_data: Dict[str, Any]) -> None:
        """Persist completed challenge to completed_challenges_col."""
        try:
            await completed_challenges_col.insert_one({
                "user_id": user_id,
                "timestamp": datetime.datetime.utcnow(),
                **challenge_data
            })
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to save completed challenge: {e}")
            raise
