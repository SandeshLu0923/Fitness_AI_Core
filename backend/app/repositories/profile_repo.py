"""
Repository Layer: Profile Data Access
Handles MongoDB interactions for user profile CRUD operations.
"""

from typing import Optional, Dict, Any
from pymongo.errors import PyMongoError
from app.database import users_col


class ProfileRepository:
    """Repository for user profile persistence and retrieval."""

    @staticmethod
    async def upsert_profile(user_id: str, profile_data: Dict[str, Any]) -> None:
        """Create or update user profile."""
        try:
            from bson import ObjectId
            await users_col.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": profile_data},
                upsert=True
            )
            print(f"[PROFILE] Updated profile for {user_id}")
        except Exception as e:
            print(f"[DB_WARNING] Failed to upsert profile (will not persist): {e}")
            # Continue without raising - profile data is still valid in memory

    @staticmethod
    async def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user profile by ID."""
        try:
            from bson import ObjectId
            profile = await users_col.find_one({"_id": ObjectId(user_id)})
            return profile if profile else None
        except Exception as e:
            print(f"[DB_WARNING] Failed to retrieve profile: {e}")
            # Return None to indicate profile not found/database unavailable
            return None
