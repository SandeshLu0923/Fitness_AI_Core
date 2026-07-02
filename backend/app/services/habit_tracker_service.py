"""
Service Layer: Habit Tracker Orchestration
Delegates to specialized sub-services for generation and calculation.
"""

from typing import Dict, Any
from app.services.habit_tracker_generator import HabitTrackerGenerator


class HabitTrackerService:
    """Service for macrocycle generation and habit tracking."""

    def __init__(self):
        self.generator = HabitTrackerGenerator()

    async def generate_weekly_block(self, user_id: str) -> Dict[str, Any]:
        """Delegate to generator service."""
        return await self.generator.generate_weekly_block(user_id)

    async def confirm_macrocycle(self, user_id: str, macrocycle_payload) -> Dict[str, Any]:
        """Delegate to generator service."""
        return await self.generator.confirm_macrocycle(user_id, macrocycle_payload)

