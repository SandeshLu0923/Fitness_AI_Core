"""
Service Layer: Profile Business Logic
Handles user profile management and validation.
"""

from typing import Dict, Any
from pydantic import BaseModel
from app.repositories.profile_repo import ProfileRepository


class ProfileService:
    """Service for user profile operations."""

    def __init__(self):
        self.repo = ProfileRepository()

    async def create_or_update_profile(self, user_id: str, profile_model: BaseModel) -> Dict[str, Any]:
        """
        Create or update user profile.
        
        Args:
            user_id: User ID
            profile_model: Pydantic profile model
            
        Returns:
            Success message with user ID
        """
        try:
            profile_data = profile_model.model_dump()
            await self.repo.upsert_profile(user_id, profile_data)

            return {
                "status": "success",
                "message": f"Profile updated for {user_id}"
            }

        except Exception as e:
            print(f"[ERROR] Failed to update profile: {e}")
            raise

    async def get_profile(self, user_id: str, profile_model: BaseModel) -> BaseModel:
        """
        Retrieve user profile.
        
        Args:
            user_id: User ID
            profile_model: Pydantic profile model class for validation
            
        Returns:
            Validated profile object
        """
        try:
            profile_data = await self.repo.get_profile(user_id)

            if not profile_data:
                raise ValueError(f"User profile not found for {user_id}")
            
            # Remove MongoDB _id field and add user_id for validation
            if '_id' in profile_data:
                del profile_data['_id']
            profile_data['user_id'] = user_id

            return profile_model(**profile_data)

        except Exception as e:
            print(f"[ERROR] Failed to retrieve profile: {e}")
            raise
