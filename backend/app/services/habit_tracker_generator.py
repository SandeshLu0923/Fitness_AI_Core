"""
Service: Habit Tracker Generator
Generates macrocycle plans using Groq with biometric data.
"""

import asyncio
import json
import datetime
from typing import Dict, Any
from pydantic import ValidationError
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.modules.trainer_utils import WeeklyMacrocyclePlan
from app.repositories.habit_tracker_repo import HabitTrackerRepository
from app.services.habit_tracker_calculator import HabitTrackerCalculator

DEFAULT_MACROCYCLE_DAYS = 7


class HabitTrackerGenerator:
    """Generates personalized macrocycle plans using Groq."""

    def __init__(self):
        self.ai_client = Groq(api_key=GROQ_API_KEY)
        self.repo = HabitTrackerRepository()
        self.calculator = HabitTrackerCalculator()
        self.model = GROQ_MODEL

    async def generate_weekly_block(self, user_id: str) -> Dict[str, Any]:
        """
        Generate a personalized weekly macrocycle training block.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Validated WeeklyMacrocyclePlan with difficulty multiplier
        """
        try:
            user_id = user_id.strip()

            # Retrieve user profile
            user_profile = await self.repo.get_user_profile(user_id)
            if not user_profile:
                raise ValueError(f"User profile not found for {user_id}")

            # Calculate all biometric metrics
            biometrics = await self.calculator.calculate_user_biometrics(user_id, user_profile)

            # Build generation prompt
            prompt = self.calculator.build_generation_prompt(biometrics)

            # Call Groq with structured guidance
            response = await asyncio.to_thread(
                self.ai_client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an elite Certified Personal Trainer. Output strict structural periodized blocks as valid JSON. "
                            "Every daily challenge must be explicit, trackable, and metric-focused. "
                            "Return ONLY valid JSON that matches the schema provided."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=3000
            )

            # Validate response structure
            if not response.choices or len(response.choices) == 0:
                raise ValueError("Empty response from Groq API")

            choice = response.choices[0]
            if not choice.message or not hasattr(choice.message, 'content'):
                raise ValueError("Missing message content in Groq response")

            raw_json = choice.message.content.strip()

            if not raw_json:
                raise ValueError("Empty JSON content from Groq response")

            print(f"[HABIT_TRACKER] Generated macrocycle for {user_id}")
            
            # Extract JSON if wrapped in markdown code blocks
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.startswith("```"):
                raw_json = raw_json[3:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
            raw_json = raw_json.strip()

            result_payload = json.loads(raw_json)
            validated_plan = WeeklyMacrocyclePlan.model_validate(result_payload)
            validated_plan_dict = validated_plan.model_dump()
            validated_plan_dict["current_difficulty_multiplier"] = biometrics["current_tier_level"]

            return validated_plan_dict

        except json.JSONDecodeError as e:
            print(f"[JSON_ERROR] Failed to parse macrocycle output: {e}")
            raise
        except ValidationError as e:
            print(f"[VALIDATION_ERROR] Macrocycle validation failed: {e}")
            raise

    async def confirm_macrocycle(self, user_id: str, macrocycle_payload: WeeklyMacrocyclePlan) -> Dict[str, Any]:
        """
        Confirm and activate a macrocycle plan.
        
        Args:
            user_id: The user's ID
            macrocycle_payload: The WeeklyMacrocyclePlan object
            
        Returns:
            Success message and plan duration
        """
        try:
            user_id = user_id.strip()
            serialized_plan = macrocycle_payload.model_dump()
            start_date = datetime.date.today()
            weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            for index, day_block in enumerate(serialized_plan.get("schedule", [])):
                if not isinstance(day_block, dict):
                    continue
                current_date = start_date + datetime.timedelta(days=index)
                day_block["date"] = current_date.isoformat()
                day_block["day_name"] = weekday_names[current_date.weekday()]

            tracking_state = {
                "current_active_day": 1,
                "completed_days": [],
                "max_block_days": serialized_plan.get("block_duration_days", DEFAULT_MACROCYCLE_DAYS),
                "plan_metadata": serialized_plan,
                "created_at": datetime.datetime.utcnow(),
                "start_date": start_date.isoformat(),
                "is_fully_completed": False
            }

            await self.repo.save_active_macrocycle(user_id, tracking_state)

            return {
                "status": "success",
                "message": f"Your {serialized_plan.get('block_duration_days', DEFAULT_MACROCYCLE_DAYS)}-day training block is live!"
            }

        except Exception as e:
            print(f"[ERROR] Failed to confirm macrocycle: {e}")
            raise
