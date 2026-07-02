"""
Repository Layer: Dietician Data Access
Handles MongoDB interactions for meal logs and grocery tracking.
"""

import datetime
from typing import List, Optional, Dict, Any
from pymongo.errors import PyMongoError
from app.database import users_col, meals_col


class DieticianRepository:
    """Repository for dietician meal and grocery data persistence."""

    @staticmethod
    async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user profile for dietary context."""
        try:
            user = await users_col.find_one({"user_id": user_id})
            if user:
                return user

            try:
                from bson import ObjectId
                if ObjectId.is_valid(user_id):
                    return await users_col.find_one({"_id": ObjectId(user_id)})
            except Exception:
                return None

            return await users_col.find_one({"_id": user_id})
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to retrieve user profile: {e}")
            raise

    @staticmethod
    async def save_meal_log(user_id: str, raw_input: str, metrics: Dict[str, Any]) -> None:
        """Persist meal analysis to meals_col."""
        try:
            await meals_col.insert_one({
                "user_id": user_id,
                "timestamp": datetime.datetime.utcnow(),
                "raw_input": raw_input,
                "metrics": metrics
            })
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to save meal log: {e}")
            raise

    @staticmethod
    async def save_grocery_list(user_id: str, grocery_data: Dict[str, Any]) -> None:
        """Persist generated grocery list to meals_col."""
        try:
            await meals_col.insert_one({
                "user_id": user_id,
                "timestamp": datetime.datetime.utcnow(),
                "type": "grocery_list",
                "data": grocery_data
            })
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to save grocery list: {e}")
            raise
