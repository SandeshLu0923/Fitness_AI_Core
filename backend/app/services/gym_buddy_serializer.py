"""
Service: Gym Buddy Plan Serializer
Converts chat history into structured WeeklyMacrocyclePlan using Groq.
"""

import asyncio
import datetime
import json
from typing import Dict, Any
from pydantic import ValidationError
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.database import diet_plans_col, workout_plans_col, users_col
from app.modules.trainer_utils import WeeklyMacrocyclePlan
from app.repositories.gym_buddy_repo import GymBuddyRepository
from app.services.plan_date_service import align_weekly_plan_dates, build_tracking_state_from_workout_plan

MAX_APPROVED_PLAN_CHARS = 12000
MAX_SERIALIZER_PROFILE_CHARS = 800


class GymBuddySerializerService:
    """Handles chat-to-plan serialization."""

    def __init__(self):
        self.ai_client = Groq(api_key=GROQ_API_KEY)
        self.repo = GymBuddyRepository()
        self.model = GROQ_MODEL

    async def serialize_chat_to_workout_plan(self, user_id: str) -> Dict[str, Any]:
        """
        Convert recent chat history into a structured WeeklyMacrocyclePlan.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Success message or structured plan data
        """
        try:
            # Retrieve chat history for serialization
            chats = await self.repo.get_recent_chats_for_serialization(user_id)
            transcript = "\n".join([
                f"User: {c['user_message']}\nBuddy: {c['response']['motivational_reply']}"
                for c in chats
            ])

            # Retrieve user profile for context
            user_profile = await self.repo.get_user_profile(user_id)
            if not user_profile:
                raise ValueError(f"User profile not found for {user_id}")

            # Build serialization prompt with schema context
            schema_description = self._build_schema_description()
            prompt = (
                f"Read the following agreed conversation transcript context text:\n\"\"\"\n{transcript}\n\"\"\"\n\n"
                f"Task: Extract and translate this chat discussion text into a strict, highly detailed multi-day layout format "
                f"fitting the exact structural fields defined in this schema:\n{schema_description}\n\n"
                f"Return ONLY valid JSON that conforms to the schema above."
            )

            # Call Groq with structured response guidance
            structured_res = await asyncio.to_thread(
                self.ai_client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict data serialization parser. Transform conversation text details into structured plan items. Return only valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            raw_json = structured_res.choices[0].message.content.strip()
            
            # Extract JSON if wrapped in markdown code blocks
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.startswith("```"):
                raw_json = raw_json[3:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
            raw_json = raw_json.strip()
            
            parsed_plan = json.loads(raw_json)
            validated_plan = WeeklyMacrocyclePlan.model_validate(parsed_plan)

            return {
                "parsed_plan": parsed_plan,
                "validated_plan": validated_plan,
                "transcript": transcript
            }

        except json.JSONDecodeError as e:
            print(f"[JSON_ERROR] Failed to parse workout serialization: {e}")
            raise
        except ValidationError as e:
            print(f"[VALIDATION_ERROR] Workout serialization validation failed: {e}")
            raise

    async def extract_and_commit_approved_plan(
        self,
        user_id: str,
        approved_chat_plan: str
    ) -> Dict[str, Any]:
        """Parse one approved assistant plan message and persist the extracted plan data."""
        if not approved_chat_plan or not approved_chat_plan.strip():
            raise ValueError("approved_chat_plan is required")

        user_profile = await self.repo.get_user_profile(user_id)
        approved_plan_text = self._truncate_text(approved_chat_plan.strip(), MAX_APPROVED_PLAN_CHARS)
        prompt = self._build_plan_extraction_prompt(user_profile or {}, approved_plan_text)

        request_kwargs = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strict data extraction tool. Return raw JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 3000,
            "response_format": {"type": "json_object"}
        }

        try:
            structured_res = await asyncio.to_thread(
                self.ai_client.chat.completions.create,
                **request_kwargs
            )
        except TypeError:
            request_kwargs.pop("response_format", None)
            structured_res = await asyncio.to_thread(
                self.ai_client.chat.completions.create,
                **request_kwargs
            )

        raw_json = structured_res.choices[0].message.content.strip()
        parsed_plan = self._parse_json_response(raw_json)
        self._validate_extracted_plan(parsed_plan)
        save_result = await self._persist_extracted_plan(user_id, parsed_plan, user_profile or {})

        return {
            "status": "success",
            "message": "Approved plan extracted and saved successfully.",
            "parsed_plan": parsed_plan,
            **save_result
        }

    def _build_schema_description(self) -> str:
        """Build a human-readable schema description for Groq."""
        return """
{
  "week_number": number,
  "days": [
    {
      "day_number": number,
      "date": "YYYY-MM-DD",
      "focus": "string",
      "exercises": [
        {
          "exercise_name": "string",
          "sets": number,
          "reps": number,
          "intensity": "string",
          "notes": "string"
        }
      ],
      "nutrition": {
        "meal_type": "string",
        "macros": {
          "protein_g": number,
          "carbs_g": number,
          "fats_g": number
        }
      }
    }
  ]
}
        """

    def _build_plan_extraction_prompt(self, user_profile: Dict[str, Any], approved_chat_plan: str) -> str:
        profile_json = json.dumps(self._slim_profile(user_profile), default=str, ensure_ascii=True)
        profile_json = self._truncate_text(profile_json, MAX_SERIALIZER_PROFILE_CHARS)
        today = datetime.datetime.now().date()
        calendar_days = [
            f"day_{index + 1} = {(today + datetime.timedelta(days=index)).strftime('%A')} ({(today + datetime.timedelta(days=index)).isoformat()})"
            for index in range(7)
        ]
        calendar_sequence = "; ".join(calendar_days)
        return f"""You are a highly precise data extraction and parsing tool. Your sole task is to convert the raw 7-day conversational text plan below into a structured JSON payload for database storage.

INPUT VARIABLES TO ANALYZE:
1. User Profile context: {profile_json}
2. Approved Conversation text: {approved_chat_plan}
3. Calendar anchor: today is {today.strftime('%A')} ({today.isoformat()}). Use this 7-day sequence if the approved text does not include exact dates: {calendar_sequence}

CRITICAL RULES:
- Extract data strictly from the provided "Approved Conversation text". Do NOT invent generic placeholders.
- Map the data explicitly into a 7-day structural format ("day_1" through "day_7").
- DAY NAME RULE: Do not default day_1 to Monday. day_1 must be today's weekday/date from the calendar anchor unless the approved text explicitly contains another concrete start date. Use the real consecutive weekday names for day_2 through day_7.
- SETS & REPS EXTRACTION RULE: For every exercise, separate the sets and reps into individual text strings. If an exercise uses a time format (e.g., "15 mins Planks" or "15 mins run"), set BOTH the "sets" field and the "reps" field to that exact time string (e.g., "15 mins").
- PARTIAL PLANS RULE: If the text only contains a weekly workout plan, leave all "meals" arrays empty ([]) across all days, and leave the master "grocery_list" empty. If it only contains a diet plan, leave all "exercises" arrays empty ([]) across all days.
- Do NOT include any conversational responses, greetings, or friendly chat. Return raw JSON data only.

You must return your output strictly in JSON format matching this schema:
{{
  "plan_type": "diet_only | workout_only | diet_and_workout",
  "weekly_plan": {{
    "day_1": {{
      "day_name": "e.g., Wednesday",
      "custom_calories": "Calculated value for this day, or 'N/A'",
      "meals": [
        {{ "time": "Meal timing", "items": ["Item 1", "Item 2"] }}
      ],
      "exercises": [
        {{
          "exercise_name": "Exercise Name",
          "sets": "e.g., '3' or '15 mins'",
          "reps": "e.g., '12' or '15 mins'"
        }}
      ]
    }},
    "day_2": {{}}, "day_3": {{}}, "day_4": {{}}, "day_5": {{}}, "day_6": {{}}, "day_7": {{}}
  }},
  "master_grocery_list": ["Combined unique raw ingredients needed for the entire week's meals"]
}}"""

    def _parse_json_response(self, raw_json: str) -> Dict[str, Any]:
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:]
        if raw_json.startswith("```"):
            raw_json = raw_json[3:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]
        return json.loads(raw_json.strip())

    def _validate_extracted_plan(self, parsed_plan: Dict[str, Any]) -> None:
        plan_type = parsed_plan.get("plan_type")
        if plan_type not in {"diet_only", "workout_only", "diet_and_workout"}:
            raise ValueError("Invalid plan_type in extracted plan")

        weekly_plan = parsed_plan.get("weekly_plan")
        if not isinstance(weekly_plan, dict):
            raise ValueError("weekly_plan must be an object")

        for index in range(1, 8):
            day_key = f"day_{index}"
            day = weekly_plan.get(day_key)
            if not isinstance(day, dict):
                raise ValueError(f"{day_key} must be an object")
            day.setdefault("day_name", f"Day {index}")
            day.setdefault("custom_calories", "N/A")
            day.setdefault("meals", [])
            day.setdefault("exercises", [])
            if not isinstance(day["meals"], list) or not isinstance(day["exercises"], list):
                raise ValueError(f"{day_key} meals and exercises must be arrays")
            day["exercises"] = [self._normalize_exercise(exercise) for exercise in day["exercises"]]

        if not isinstance(parsed_plan.get("master_grocery_list"), list):
            raise ValueError("master_grocery_list must be an array")

    def _normalize_exercise(self, exercise: Any) -> Dict[str, str]:
        if isinstance(exercise, str):
            return {"exercise_name": exercise, "sets": "N/A", "reps": "N/A"}
        if not isinstance(exercise, dict):
            return {"exercise_name": "Unknown Exercise", "sets": "N/A", "reps": "N/A"}

        sets_reps = str(exercise.get("sets_reps", "")).strip()
        return {
            "exercise_name": str(exercise.get("exercise_name") or exercise.get("exercise") or exercise.get("name") or "Unknown Exercise"),
            "sets": str(exercise.get("sets") or self._split_sets_reps(sets_reps)[0] or "N/A"),
            "reps": str(exercise.get("reps") or self._split_sets_reps(sets_reps)[1] or "N/A")
        }

    def _split_sets_reps(self, sets_reps: str) -> tuple[str, str]:
        if not sets_reps:
            return "", ""
        lower_value = sets_reps.lower()
        if "min" in lower_value or "sec" in lower_value:
            return sets_reps, sets_reps
        parts = sets_reps.replace("sets of", "x").replace("set of", "x").split("x", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].replace("reps", "").strip()
        return sets_reps, sets_reps

    async def _persist_extracted_plan(
        self,
        user_id: str,
        parsed_plan: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        now = datetime.datetime.utcnow()
        plan_type = parsed_plan["plan_type"]
        weekly_plan = align_weekly_plan_dates(parsed_plan["weekly_plan"])
        grocery_list = parsed_plan.get("master_grocery_list", [])
        result: Dict[str, Any] = {"diet_plan_id": None, "workout_plan_id": None}

        if plan_type in {"diet_only", "diet_and_workout"}:
            existing_diet = await diet_plans_col.find_one({"user_id": user_id}, sort=[("updated_at", -1), ("created_at", -1)])
            diet_document = {
                "user_id": user_id,
                "diet_plan": weekly_plan,
                "grocery_list": grocery_list,
                "notes": "Generated from approved AI coach chat plan.",
                "updated_at": now,
                "start_date": now.date().isoformat(),
                "is_active": True,
            }
            if existing_diet:
                await diet_plans_col.update_one(
                    {"_id": existing_diet["_id"]},
                    {"$set": diet_document}
                )
                await diet_plans_col.delete_many({"user_id": user_id, "_id": {"$ne": existing_diet["_id"]}})
                result["diet_plan_id"] = str(existing_diet["_id"])
            else:
                diet_document["created_at"] = now
                diet_insert = await diet_plans_col.insert_one(diet_document)
                result["diet_plan_id"] = str(diet_insert.inserted_id)

        if plan_type in {"workout_only", "diet_and_workout"}:
            daily_challenges = await self._generate_daily_challenges(weekly_plan, user_profile)
            existing_workout = await workout_plans_col.find_one({"user_id": user_id}, sort=[("updated_at", -1), ("created_at", -1)])
            workout_document = {
                "user_id": user_id,
                "workout_plan": weekly_plan,
                "daily_challenges": daily_challenges,
                "archetype": "AI Coach Weekly Plan",
                "difficulty_multiplier": "profile_based",
                "updated_at": now,
                "start_date": now.date().isoformat(),
                "is_active": True,
                "total_days": 7
            }
            if existing_workout:
                await workout_plans_col.update_one(
                    {"_id": existing_workout["_id"]},
                    {"$set": workout_document}
                )
                await workout_plans_col.delete_many({"user_id": user_id, "_id": {"$ne": existing_workout["_id"]}})
                result["workout_plan_id"] = str(existing_workout["_id"])
            else:
                workout_document["created_at"] = now
                workout_insert = await workout_plans_col.insert_one(workout_document)
                result["workout_plan_id"] = str(workout_insert.inserted_id)

            tracking_state = build_tracking_state_from_workout_plan(
                weekly_plan,
                difficulty_multiplier="profile_based",
                max_days=7,
            )
            await users_col.update_one(
                {"user_id": user_id},
                {"$set": {"active_macrocycle": tracking_state}},
                upsert=True,
            )

        return result

    async def _generate_daily_challenges(
        self,
        extracted_weekly_plan: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> list[Dict[str, Any]]:
        profile_json = json.dumps(self._slim_profile(user_profile), default=str, ensure_ascii=True)
        plan_json = json.dumps(extracted_weekly_plan, default=str, ensure_ascii=True)
        plan_json = self._truncate_text(plan_json, 4000)
        prompt = f"""You are a creative, behavioral fitness assistant. Your sole task is to generate 7 highly engaging daily health challenges tailored directly to complement the user's weekly workout plan.

INPUT VARIABLES TO ANALYZE:
1. Extracted Weekly Plan: {plan_json}
2. User Profile: {profile_json}

CRITICAL RULES:
- Generate an array containing exactly 7 objects, matching days 1 through 7 sequentially.
- Align the challenge with the theme of that workout day. Include a concrete action description along with specific target sets and reps.
- TIME-BASED METRIC RULE: If a challenge is timed (e.g., a 15-minute walk or a 5-minute stretch), populate BOTH the "sets" and "reps" fields with that exact time string (e.g., "15 mins").
- Keep the challenge text field concise and direct. Do not write a paragraph.
- Return a raw JSON array matching your database scheme exactly. No conversational text wrappers.

You must return your output strictly in JSON format matching this schema:
{{
  "daily_challenges": [
    {{
      "day": 1,
      "challenge": "Short challenge summary title",
      "description": "Clear action instruction text",
      "sets": "e.g., '3' or '5 mins'",
      "reps": "e.g., '10' or '5 mins'"
    }},
    {{ "day": 2, "challenge": "", "description": "", "sets": "", "reps": "" }},
    {{ "day": 3, "challenge": "", "description": "", "sets": "", "reps": "" }},
    {{ "day": 4, "challenge": "", "description": "", "sets": "", "reps": "" }},
    {{ "day": 5, "challenge": "", "description": "", "sets": "", "reps": "" }},
    {{ "day": 6, "challenge": "", "description": "", "sets": "", "reps": "" }},
    {{ "day": 7, "challenge": "", "description": "", "sets": "", "reps": "" }}
  ]
}}"""

        try:
            response = await asyncio.to_thread(
                self.ai_client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1200,
                response_format={"type": "json_object"}
            )
            parsed = self._parse_json_response(response.choices[0].message.content.strip())
            challenges = parsed.get("daily_challenges", [])
            if isinstance(challenges, list) and len(challenges) == 7:
                return [self._normalize_challenge(item, index + 1) for index, item in enumerate(challenges)]
        except Exception as e:
            print(f"[CHALLENGE_GENERATION_WARNING] Falling back to deterministic challenges: {e}")

        return [self._fallback_challenge(extracted_weekly_plan, index) for index in range(1, 8)]

    def _normalize_challenge(self, challenge: Any, day: int) -> Dict[str, Any]:
        if not isinstance(challenge, dict):
            return self._fallback_challenge({}, day)
        return {
            "day": int(challenge.get("day") or day),
            "challenge": str(challenge.get("challenge") or f"Day {day} Challenge"),
            "description": str(challenge.get("description") or "Complete the assigned movement with controlled form."),
            "sets": str(challenge.get("sets") or "3"),
            "reps": str(challenge.get("reps") or "10")
        }

    def _fallback_challenge(self, weekly_plan: Dict[str, Any], day: int) -> Dict[str, Any]:
        day_plan = weekly_plan.get(f"day_{day}", {})
        exercises = day_plan.get("exercises", []) if isinstance(day_plan, dict) else []
        exercise_name = "Mobility Flow"
        sets = "5 mins"
        reps = "5 mins"
        if exercises:
            first = self._normalize_exercise(exercises[0])
            exercise_name = first["exercise_name"]
            sets = first["sets"]
            reps = first["reps"]
        return {
            "day": day,
            "challenge": f"{exercise_name} Focus",
            "description": f"Complete {exercise_name} with strict form.",
            "sets": sets,
            "reps": reps
        }

    def _slim_profile(self, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        allowed_keys = (
            "user_id",
            "name",
            "fitness_goal",
            "activity_level",
            "age",
            "weight_kg",
            "height_cm",
            "daily_calorie_target",
            "dietary_restrictions",
            "preferences",
        )
        return {key: user_profile.get(key) for key in allowed_keys if user_profile.get(key) is not None}

    def _truncate_text(self, text: str, max_chars: int) -> str:
        if not text or len(text) <= max_chars:
            return text or ""
        return text[-max_chars:]
