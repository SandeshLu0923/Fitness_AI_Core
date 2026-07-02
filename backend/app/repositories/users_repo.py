"""
Repository Layer: Users Data Access
Handles all MongoDB interactions for user authentication and profiles.
"""

import datetime
from typing import Optional, Dict, Any
from pymongo.errors import PyMongoError


class UsersRepository:
    """Repository for user authentication and profile management."""

    def __init__(self):
        # Defer database access to method level
        self._users_col = None

    @property
    def users_col(self):
        """Get users collection (lazy-loaded)."""
        if self._users_col is None:
            from app.database import db as database_instance
            if isinstance(database_instance, dict):
                # If db was initialized as a dict, use it directly
                self._users_col = database_instance.users
            else:
                # If it's a LazyDB object, access the users property
                self._users_col = database_instance.users
        return self._users_col

    async def create_user(self, name: str, email: str, password_hash: str) -> str:
        """Create a new user account."""
        try:
            user_doc = {
                "name": name,
                "email": email,
                "password_hash": password_hash,
                "age": None,
                "weight_kg": None,
                "height_cm": None,
                "latitude": 0.0,
                "longitude": 0.0,
                "profile_completed": False,
                "created_at": datetime.datetime.utcnow(),
                "updated_at": datetime.datetime.utcnow()
            }
            result = await self.users_col.insert_one(user_doc)
            return str(result.inserted_id)
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to create user: {e}")
            raise

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieve user by email address."""
        try:
            user = await self.users_col.find_one({"email": email})
            return user
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to query user by email: {e}")
            raise

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user by ID."""
        try:
            from bson import ObjectId
            user = await self.users_col.find_one({"_id": ObjectId(user_id)})
            return user
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to query user by ID: {e}")
            raise

    async def update_user_profile(
        self,
        user_id: str,
        age: int,
        weight_kg: float,
        height_cm: float,
        latitude: float = 0.0,
        longitude: float = 0.0
    ) -> None:
        """Update user profile information."""
        try:
            from bson import ObjectId
            await self.users_col.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "age": age,
                        "weight_kg": weight_kg,
                        "height_cm": height_cm,
                        "latitude": latitude,
                        "longitude": longitude,
                        "profile_completed": True,
                        "updated_at": datetime.datetime.utcnow()
                    }
                }
            )
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to update user profile: {e}")
            raise
