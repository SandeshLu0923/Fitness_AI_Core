"""
Service Layer: Gym Buddy Orchestration
Delegates to specialized sub-services for chat generation and plan serialization.
"""

from typing import Dict, Any
from app.services.gym_buddy_chat import GymBuddyChatService
from app.services.gym_buddy_serializer import GymBuddySerializerService


class GymBuddyService:
    """Service for gym buddy chat and serialization operations."""

    def __init__(self):
        self.chat_service = GymBuddyChatService()
        self.serializer_service = GymBuddySerializerService()

    async def generate_casual_chat_response(
        self,
        user_id: str,
        user_message: str,
        session_id: str | None = None,
        is_diet_trigger: bool = False,
        is_workout_trigger: bool = False
    ) -> Dict[str, Any]:
        """Delegate to chat service."""
        return await self.chat_service.generate_casual_chat_response(
            user_id=user_id,
            user_message=user_message,
            session_id=session_id,
            is_diet_trigger=is_diet_trigger,
            is_workout_trigger=is_workout_trigger
        )

    async def serialize_chat_to_workout_plan(self, user_id: str) -> Dict[str, Any]:
        """Delegate to serializer service."""
        return await self.serializer_service.serialize_chat_to_workout_plan(user_id)

    async def extract_and_commit_approved_plan(
        self,
        user_id: str,
        approved_chat_plan: str
    ) -> Dict[str, Any]:
        """Delegate approved-message plan extraction and persistence."""
        return await self.serializer_service.extract_and_commit_approved_plan(
            user_id, approved_chat_plan
        )
