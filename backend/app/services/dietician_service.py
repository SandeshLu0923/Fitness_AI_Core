"""
Service Layer: Dietician Business Logic
Orchestrates Groq API calls for meal analysis and grocery planning.
"""

import asyncio
import json
import time
from typing import Dict, Any
from pydantic import ValidationError
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.repositories.dietician_repo import DieticianRepository


class DieticianService:
    """Service for meal logging and grocery list generation."""

    def __init__(self):
        self.ai_client = Groq(api_key=GROQ_API_KEY)
        self.repo = DieticianRepository()
        self.model = GROQ_MODEL

    async def analyze_meal(self, user_id: str, user_input: str, response_model: Any) -> Dict[str, Any]:
        """
        Analyze meal log input using Groq.
        
        Args:
            user_id: User ID
            user_input: Raw meal description from user
            response_model: Pydantic model for validation (e.g., DietResponse)
            
        Returns:
            Validated meal analysis
        """
        start_time = time.perf_counter()
        try:
            # Retrieve user profile for personalized analysis
            user_profile = await self.repo.get_user_profile(user_id)
            if not user_profile:
                raise ValueError(f"Profile required for user {user_id}")

            goal = user_profile.get("fitness_goal", "Maintenance")
            weight = user_profile.get("weight_kg", "unknown")

            # Call Groq with meal analysis
            response = await asyncio.to_thread(
                self.ai_client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"Act as a dietician. Analyze the food log for a user aiming for {goal} "
                            f"at weight {weight}kg. Return only valid JSON with this exact shape: "
                            '{"extracted_foods":[{"food_name":"string","quantity":"string",'
                            '"estimated_calories":0,"protein_g":0,"carbs_g":0,"fats_g":0}],'
                            '"total_meal_calories":0,"nutritional_advice":"string"}. '
                            "Use reasonable estimates when quantities are approximate. Do not include markdown."
                        )
                    },
                    {"role": "user", "content": user_input}
                ],
                temperature=0.3,
                max_tokens=800
            )

            raw_json = response.choices[0].message.content.strip()
            
            # Extract JSON if wrapped in markdown code blocks
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.startswith("```"):
                raw_json = raw_json[3:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
            raw_json = raw_json.strip()

            data = json.loads(raw_json)
            validated_response = response_model.model_validate(data)

            # Persist to database
            await self.repo.save_meal_log(user_id, user_input, validated_response.model_dump())
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference(
                "diet_meal_analysis",
                user_id=user_id,
                success=True,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )

            return validated_response

        except json.JSONDecodeError as e:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference("diet_meal_analysis", user_id=user_id, success=False, latency_ms=(time.perf_counter() - start_time) * 1000)
            print(f"[JSON_ERROR] Failed to parse dietician response: {e}")
            raise
        except ValidationError as e:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference("diet_meal_analysis", user_id=user_id, success=False, latency_ms=(time.perf_counter() - start_time) * 1000)
            print(f"[VALIDATION_ERROR] Dietician output validation failed: {e}")
            raise

    async def generate_grocery_list(self, user_id: str, preferences_or_allergies: str, response_model: Any) -> Dict[str, Any]:
        """
        Generate weekly grocery list using Groq.
        
        Args:
            user_id: User ID
            preferences_or_allergies: Dietary preferences or allergies
            response_model: Pydantic model for validation (e.g., GroceryResponse)
            
        Returns:
            Validated grocery list
        """
        start_time = time.perf_counter()
        try:
            # Retrieve user profile for context
            user_profile = await self.repo.get_user_profile(user_id)
            if not user_profile:
                raise ValueError(f"Profile required for user {user_id}")

            fitness_goal = user_profile.get("fitness_goal", "Fitness")
            activity_level = user_profile.get("activity_level", "Moderate")

            prompt = (
                f"Weekly grocery setup for a {fitness_goal} goal. "
                f"Activity context: {activity_level}. "
                f"Restrictions: {preferences_or_allergies} "
                f"Return valid JSON matching the provided schema."
            )

            # Call Groq with grocery planning
            response = await asyncio.to_thread(
                self.ai_client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Act as a clean meal prep planner. Create structured macro-focused grocery breakdowns. Return only valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )

            raw_json = response.choices[0].message.content.strip()
            
            # Extract JSON if wrapped in markdown code blocks
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.startswith("```"):
                raw_json = raw_json[3:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
            raw_json = raw_json.strip()

            data = json.loads(raw_json)
            validated_response = response_model.model_validate(data)

            # Persist to database
            await self.repo.save_grocery_list(user_id, validated_response.model_dump())
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference(
                "diet_grocery_generation",
                user_id=user_id,
                success=True,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )

            return validated_response

        except json.JSONDecodeError as e:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference("diet_grocery_generation", user_id=user_id, success=False, latency_ms=(time.perf_counter() - start_time) * 1000)
            print(f"[JSON_ERROR] Failed to parse grocery response: {e}")
            raise
        except ValidationError as e:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference("diet_grocery_generation", user_id=user_id, success=False, latency_ms=(time.perf_counter() - start_time) * 1000)
            print(f"[VALIDATION_ERROR] Grocery response validation failed: {e}")
            raise


            # Persist to database
            await self.repo.save_grocery_list(user_id, validated_response.model_dump())

            return validated_response

        except json.JSONDecodeError as e:
            print(f"[JSON_ERROR] Failed to parse grocery response: {e}")
            raise
        except ValidationError as e:
            print(f"[VALIDATION_ERROR] Grocery response validation failed: {e}")
            raise
