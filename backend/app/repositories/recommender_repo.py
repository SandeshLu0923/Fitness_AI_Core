"""
Repository Layer: Recommender Data Access
Handles MongoDB interactions for gym data retrieval and website caching.
"""

from typing import List, Optional, Dict, Any
from pymongo.errors import PyMongoError
from app.database import gyms_col


class RecommenderRepository:
    """Repository for gym data access and persistence."""

    @staticmethod
    async def get_all_gyms(limit: int = 10000) -> List[Dict[str, Any]]:
        """
        Retrieve all gyms from database with limit.
        
        Args:
            limit: Maximum number of gyms to retrieve (prevents memory overload)
            
        Returns:
            List of gym documents
        """
        try:
            # Use to_list() instead of async for to handle large collections safely
            cursor = gyms_col.find({})
            gyms = await cursor.to_list(length=limit)
            print(f"[RECOMMENDER] Retrieved {len(gyms)} gyms from database")
            return gyms
        except Exception as e:
            print(f"[DB_WARNING] Failed to retrieve gyms, returning empty list: {e}")
            # Return empty list as fallback
            return []

    @staticmethod
    async def update_gym_website(gym_id: Any, website: str) -> None:
        """Update gym website in cache."""
        try:
            await gyms_col.update_one(
                {"_id": gym_id},
                {"$set": {"website": website}}
            )
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to cache website for gym: {e}")
            raise

    @staticmethod
    async def get_gym_by_id(gym_id: Any) -> Optional[Dict[str, Any]]:
        """Retrieve a single gym by ID."""
        try:
            return await gyms_col.find_one({"_id": gym_id})
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to retrieve gym: {e}")
            raise
