"""
Service: Gym Buddy Chat Generation
Handles casual chat responses from Groq with profile-aware personalization.
"""

import asyncio
import datetime
import json
import logging
import time
from typing import Dict, Any, Optional, List
from groq import Groq
from groq import APIStatusError
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.database import diet_plans_col, workout_plans_col
from app.repositories.gym_buddy_repo import GymBuddyRepository
from app.repositories.habit_tracker_repo import HabitTrackerRepository
from app.services.habit_tracker_calculator import HabitTrackerCalculator
from app.services.workout_summary_service import WorkoutSummaryService
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)
PLAN_ACTION_TRIGGER = "[TRIGGER_PLAN_ACTIONS]"
MAX_HISTORY_CHARS = 1500
MAX_PROFILE_CHARS = 800
MAX_REPLY_SNIPPET_CHARS = 250
MAX_HISTORY_MESSAGES = 4


class GymBuddyChatService:
    """Handles casual chat generation and context management."""

    def __init__(self):
        self.ai_client = Groq(api_key=GROQ_API_KEY)
        self.repo = GymBuddyRepository()
        self.habit_repo = HabitTrackerRepository()
        self.habit_calculator = HabitTrackerCalculator()
        self.summary_service = WorkoutSummaryService()
        self.model = GROQ_MODEL
        logger.info(f"[GYM_BUDDY_SERVICE] Initialized with model: {self.model}")

    async def generate_casual_chat_response(
        self,
        user_id: str,
        user_message: str,
        session_id: Optional[str] = None,
        is_diet_trigger: bool = False,
        is_workout_trigger: bool = False
    ) -> Dict[str, Any]:
        """Generate a casual chat response from Groq, save to DB, and return response payload."""
        logger.info(f"[CHAT_SERVICE] Starting response generation for {user_id}")
        start_time = time.perf_counter()
        
        adjusted_message = user_message
        user_profile: Dict[str, Any] = {}

        try:
            # Retrieve chat history for context
            history_docs = await self.repo.get_chat_history(
                user_id,
                session_id=session_id,
                limit=MAX_HISTORY_MESSAGES
            )
            history_text = self._build_history_context(history_docs)

            # Retrieve user profile for personalization
            user_profile = await self.repo.get_user_profile(user_id)
            user_profile = user_profile or {}
            is_plan_lookup_request = self._is_saved_plan_lookup_request(user_message)
            is_new_plan_request = self._is_new_plan_request(user_message, is_diet_trigger, is_workout_trigger)
            should_include_plan_context = self._should_include_plan_context(
                user_message,
                is_diet_trigger,
                is_workout_trigger,
                is_plan_lookup_request,
                is_new_plan_request,
            )
            should_include_report_context = self._should_include_report_context(user_message)
            companion_context = await self._build_companion_context(
                user_id,
                user_profile,
                user_message,
                include_plan_context=should_include_plan_context,
                include_report_context=should_include_report_context,
            )
            await self._persist_mood_signal(user_id, user_message, companion_context.get("detected_mood", "neutral"))

            if is_plan_lookup_request:
                response_payload = await self._get_saved_plan_lookup_response(user_id, user_message)
                await self.repo.save_chat_exchange(user_id, user_message, response_payload, session_id=session_id)
                await AnalyticsService.log_ai_inference(
                    "chat_saved_plan_lookup",
                    user_id=user_id,
                    success=True,
                    latency_ms=(time.perf_counter() - start_time) * 1000,
                )
                return response_payload

            # Construct dynamic system instructions based on context
            system_instruction = self._get_system_instruction(
                is_diet_trigger, is_workout_trigger, user_profile, history_text, companion_context
            )

            # Adjust user message if triggering a specialized plan
            adjusted_message = self._adjust_user_message(
                user_message,
                is_diet_trigger,
                is_workout_trigger,
                companion_context,
            )

            # Build full prompt with history
            full_prompt = f"Latest User Message: {adjusted_message}"

            # Call Groq in thread-safe manner
            response = await asyncio.to_thread(
                self.ai_client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.35,
                max_tokens=1500
            )
            
            # Validate Groq response structure
            if not response.choices or len(response.choices) == 0:
                raise ValueError("Empty response from Groq API")

            choice = response.choices[0]
            if not choice.message or not hasattr(choice.message, 'content'):
                raise ValueError("Missing message content in Groq response")

            raw_text_reply = choice.message.content.strip()

            if not raw_text_reply:
                raise ValueError("Empty content in Groq response")

            print(f"[GYM_BUDDY] Generated response for {user_id} ({len(raw_text_reply)} chars)")

            # Determine if confirmation buttons are needed
            requires_buttons = PLAN_ACTION_TRIGGER in raw_text_reply and is_new_plan_request
            action_type = self._extract_action_type(raw_text_reply) if requires_buttons else None

            response_payload = {
                "motivational_reply": raw_text_reply,
                "requires_confirmation_buttons": requires_buttons,
                "confirmation_action_type": action_type,
                "plan_action_trigger": PLAN_ACTION_TRIGGER
            }

            # Persist the exchange
            await self.repo.save_chat_exchange(user_id, adjusted_message, response_payload, session_id=session_id)
            await AnalyticsService.log_ai_inference(
                "chat_companion",
                user_id=user_id,
                success=True,
                latency_ms=(time.perf_counter() - start_time) * 1000,
                metadata={
                    "intent": companion_context.get("latest_user_intent"),
                    "mood": companion_context.get("detected_mood"),
                },
            )

            return response_payload

        except APIStatusError as e:
            status_code = getattr(e, "status_code", None)
            if status_code == 413:
                logger.error(
                    "[CHAT_413] Groq rejected the request because the prompt payload was too large. "
                    "History/profile context has been reduced automatically; retrying with minimal context.",
                    exc_info=True,
                )
                return await self._generate_with_minimal_context(
                    user_id=user_id,
                    adjusted_message=adjusted_message,
                    session_id=session_id,
                    is_diet_trigger=is_diet_trigger,
                    is_workout_trigger=is_workout_trigger,
                    user_profile=user_profile,
                )
            logger.error(f"[WARNING] Groq API error: {type(e).__name__}: {e}", exc_info=True)
            await AnalyticsService.log_ai_inference("chat_companion", user_id=user_id, success=False, latency_ms=(time.perf_counter() - start_time) * 1000)
            return self._fallback_response()
        except Exception as e:
            logger.error(f"[WARNING] Failed to generate chat response: {type(e).__name__}: {e}", exc_info=True)
            await AnalyticsService.log_ai_inference("chat_companion", user_id=user_id, success=False, latency_ms=(time.perf_counter() - start_time) * 1000)
            
            # Return thoughtful fallback response instead of raising
            return self._fallback_response()

    async def _persist_mood_signal(self, user_id: str, message: str, mood: str) -> None:
        score_map = {
            "stressed": -0.7,
            "tired": -0.5,
            "demotivated": -0.6,
            "positive": 0.7,
            "neutral": 0.0,
        }
        await AnalyticsService.log_mood(user_id, mood or "neutral", score_map.get(mood or "neutral", 0.0), message)

    async def _generate_with_minimal_context(
        self,
        user_id: str,
        adjusted_message: str,
        session_id: Optional[str],
        is_diet_trigger: bool,
        is_workout_trigger: bool,
        user_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Retry chat generation with the smallest safe prompt payload."""
        try:
            system_instruction = self._get_system_instruction(
                is_diet_trigger,
                is_workout_trigger,
                user_profile,
                "No previous conversation.",
                self._build_minimal_companion_context(adjusted_message),
                minimal=True,
            )
            full_prompt = f"Latest User Message: {adjusted_message}"

            response = await asyncio.to_thread(
                self.ai_client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": full_prompt},
                ],
                temperature=0.35,
                max_tokens=1500,
            )

            raw_text_reply = response.choices[0].message.content.strip()
            is_new_plan_request = self._is_new_plan_request(adjusted_message, is_diet_trigger, is_workout_trigger)
            requires_buttons = PLAN_ACTION_TRIGGER in raw_text_reply and is_new_plan_request
            action_type = self._extract_action_type(raw_text_reply) if requires_buttons else None
            response_payload = {
                "motivational_reply": raw_text_reply,
                "requires_confirmation_buttons": requires_buttons,
                "confirmation_action_type": action_type,
                "plan_action_trigger": PLAN_ACTION_TRIGGER,
            }
            await self.repo.save_chat_exchange(user_id, adjusted_message, response_payload, session_id=session_id)
            return response_payload
        except Exception as retry_error:
            logger.error(f"[CHAT_MINIMAL_RETRY_FAILED] {type(retry_error).__name__}: {retry_error}", exc_info=True)
            return self._fallback_response()

    def _fallback_response(self) -> Dict[str, Any]:
        return {
            "motivational_reply": "I'm here to support your fitness goals! Let me refocus and give you the best coaching. Share what's on your mind!",
            "requires_confirmation_buttons": False,
            "confirmation_action_type": None,
        }

    def _build_history_context(self, history_docs: List[Dict[str, Any]]) -> str:
        if not history_docs:
            return ""

        snippets = []
        for doc in history_docs:
            user_message = str(doc.get("user_message", ""))
            if "__trigger_" in user_message:
                continue

            buddy_reply = str(doc.get("response", {}).get("motivational_reply", ""))
            if PLAN_ACTION_TRIGGER in buddy_reply or len(buddy_reply) > 1200:
                buddy_reply = "[Previous finalized weekly plan omitted to keep chat context compact.]"

            snippets.append(
                f"User: {self._truncate_text(user_message, MAX_REPLY_SNIPPET_CHARS)}\n"
                f"Buddy: {self._truncate_text(buddy_reply, MAX_REPLY_SNIPPET_CHARS)}"
            )

        return self._truncate_text("\n".join(snippets), MAX_HISTORY_CHARS)

    def _get_system_instruction(
        self,
        is_diet_trigger: bool,
        is_workout_trigger: bool,
        user_profile: Dict[str, Any],
        chat_history: str,
        companion_context: Dict[str, Any],
        minimal: bool = False,
    ) -> str:
        """Generate context-aware system instruction."""
        profile_json = json.dumps(self._slim_profile(user_profile), default=str, ensure_ascii=True)
        profile_json = self._truncate_text(profile_json, MAX_PROFILE_CHARS if not minimal else 500)
        companion_json = json.dumps(companion_context, default=str, ensure_ascii=True)
        companion_json = self._truncate_text(companion_json, 900 if not minimal else 500)
        trigger_focus = ""
        if is_diet_trigger:
            trigger_focus = "The user explicitly requested a finalized 7-day diet plan and grocery list."
        elif is_workout_trigger:
            trigger_focus = "The user explicitly requested a finalized 7-day workout plan."

        history_block = "No previous conversation." if minimal else (chat_history or "No previous conversation.")
        history_block = self._truncate_text(history_block, 800 if minimal else MAX_HISTORY_CHARS)
        today = datetime.datetime.now().date()
        calendar_days = [
            f"Day {index + 1}: {(today + datetime.timedelta(days=index)).strftime('%A')} ({(today + datetime.timedelta(days=index)).isoformat()})"
            for index in range(7)
        ]
        calendar_sequence = "; ".join(calendar_days)

        return f"""You are the AI Gym Assistant's Virtual Gym Buddy, AI Dietician, Calorie Coach, and workout-plan assistant. Chat naturally, but behave like a product feature inside a fitness app, not a generic chatbot.

INPUT VARIABLES TO ANALYZE:
1. User Profile context: {profile_json}
2. Conversation History: {history_block}
3. Companion, habit, and mood context: {companion_json}
4. Calendar anchor for new plans: today is {today.strftime('%A')} ({today.isoformat()}). The next 7 days are: {calendar_sequence}

CRITICAL RULES:
- Operate as one unified AI Gym & Fitness Assistant ecosystem: professional assistant, supportive gym companion, dietician, calorie coach, and behavioral habit coach.
- Tailor all conversations specifically to the user's goals, daily calorie targets, preferences, and dietary restrictions/allergies provided in their profile.
- Never suggest generic or static placeholder data.
- Do not over-focus on workout plans or diet plans. Match the user's intent: motivation, emotional support, accountability, nutrition, habit tracking, recovery, exercise form, gym guidance, or plan creation.
- For workout questions: provide practical exercise guidance, form notes, sets/reps/rest, progression, and safety cues.
- For diet questions: provide personalized meal guidance, calories/macros when possible, hydration, grocery items, and restriction-aware substitutions.
- For calorie coaching: explain intake targets and meal tradeoffs using the profile. Do not pretend to log meals unless the user explicitly says they logged something.
- For habit tracking: use skip risk, completed challenge count, active macrocycle day, and engagement context to send short motivational nudges, suggest schedule adjustments, and reduce friction when the user sounds likely to skip.
- For emotional support: infer mood from the latest message and conversation context. If the user sounds stressed, tired, guilty, anxious, or demotivated, respond with calm encouragement and one manageable next action. Do not diagnose mental health.
- For smart gym assistance: explain how to use training, form tracking, gym discovery, challenges, and saved plans when relevant.
- For existing plan lookups such as "today plan", "current diet", "latest workout", or "show my plan": answer from the stored plan context supplied by the app. Do not propose updating or saving that plan.
- If plan_request_context is present, use it as the only source of existing workout/diet-plan and completion status. Do not ask for old plan details already summarized there.
- If the user asks to change or regenerate an existing workout plan, preserve completed days and produce a plan only for remaining_days starting at next_plan_start_date. Do not rewrite already completed days.
- DATE ALIGNMENT RULE: For every newly generated 7-day workout or diet plan, Day 1 must start on the supplied calendar anchor, not Monday by default. Use the exact weekday sequence from the calendar anchor. Day headings must include both weekday and date, for example **Wednesday (2026-07-01)**.
- DATE ALIGNMENT RULE FOR REMAINING PLANS: If next_plan_start_date is supplied in plan_request_context, start the remaining workout plan from that date and use its real weekday/date sequence.
- If is_fully_completed is true, suggest starting the next 7-day workout block and refreshing the diet plan for the next week.
- UNIVERSAL FORMATTING RULE: Whenever you present ANY kind of list (workout plans, diet meal structures, grocery items, or health tips), format it cleanly using Markdown. Use bold subheaders for sections/days (e.g., **Wednesday (2026-07-01)**) and put each item on its own line using numbered lists (1., 2.) or bullets (-). Do not put multiple exercises, meals, sets, reps, or grocery items in one paragraph.
- PLAN FORMAT RULE: If you create a 7-day plan, each day must be separated by a blank line. Each meal or exercise must be its own bullet with sets/reps/time on the same bullet.
- Always include clear numeric metrics (e.g., 3 sets of 10 reps, or 15 mins) whenever suggesting exercises or fitness challenges.
- TRIGGER RULE: Append the exact tag {PLAN_ACTION_TRIGGER} only when the user explicitly requests a new finalized 7-Day Workout Plan, Diet Plan, or Grocery List. Do not append the tag when answering questions, explaining a plan, or retrieving an existing saved plan.
- Do not ask the user to press Save/Update in normal chat. The app decides whether buttons are shown.

{trigger_focus}""".strip()

    async def _build_companion_context(
        self,
        user_id: str,
        user_profile: Dict[str, Any],
        user_message: str,
        include_plan_context: bool = False,
        include_report_context: bool = False,
    ) -> Dict[str, Any]:
        """Collect behavioral and mood signals for the virtual gym buddy prompt."""
        latest_intent = self._detect_intent(user_message)
        context: Dict[str, Any] = {
            "detected_mood": self._detect_mood_signal(user_message),
            "latest_user_intent": latest_intent,
        }

        if latest_intent == "habit_tracking_or_motivation" or include_plan_context:
            try:
                biometrics = await self.habit_calculator.calculate_user_biometrics(user_id, user_profile)
                context["habit_tracker"] = {
                    "bmi": biometrics.get("bmi"),
                    "maintenance_calories": biometrics.get("predicted_maintenance_calories"),
                    "skip_probability": round(float(biometrics.get("skip_probability", 0.0)), 2),
                    "completed_challenges": biometrics.get("completed_count"),
                    "fitness_level": biometrics.get("current_tier_level"),
                }
            except Exception as e:
                logger.debug(f"[CHAT_CONTEXT] Habit biometrics unavailable: {e}")

        if include_plan_context:
            context["plan_request_context"] = await self._build_plan_request_context(user_id)

        if include_report_context and not include_plan_context:
            try:
                context["progress_report_context"] = await self.summary_service.get_latest_compact_context(user_id)
            except Exception as e:
                logger.debug(f"[CHAT_CONTEXT] Progress report summary unavailable: {e}")

        return context

    def _build_minimal_companion_context(self, user_message: str) -> Dict[str, Any]:
        return {
            "detected_mood": self._detect_mood_signal(user_message),
            "latest_user_intent": self._detect_intent(user_message),
        }

    async def _build_plan_request_context(self, user_id: str) -> Dict[str, Any]:
        """Fetch compact plan context only for plan requests to avoid oversized prompts."""
        context: Dict[str, Any] = {}

        try:
            active_macrocycle = await self.habit_repo.get_active_macrocycle(user_id)
            context["workout_completion"] = self._summarize_completion_status(active_macrocycle)
        except Exception as e:
            logger.debug(f"[CHAT_CONTEXT] Completion summary unavailable: {e}")
            context["workout_completion"] = self._summarize_completion_status(None)

        try:
            workout_plan = await workout_plans_col.find_one({"user_id": user_id}, sort=[("created_at", -1)])
            if workout_plan:
                context["existing_workout_plan_summary"] = self._summarize_plan_document(
                    workout_plan,
                    "workout_plan",
                    context.get("workout_completion", {}),
                )
        except Exception as e:
            logger.debug(f"[CHAT_CONTEXT] Workout plan summary unavailable: {e}")

        try:
            diet_plan = await diet_plans_col.find_one({"user_id": user_id, "is_active": True}, sort=[("updated_at", -1), ("created_at", -1)])
            if not diet_plan:
                diet_plan = await diet_plans_col.find_one({"user_id": user_id}, sort=[("updated_at", -1), ("created_at", -1)])
            if diet_plan:
                context["existing_diet_plan_summary"] = self._summarize_plan_document(diet_plan, "diet_plan", {})
        except Exception as e:
            logger.debug(f"[CHAT_CONTEXT] Diet plan summary unavailable: {e}")

        try:
            context["progress_report_context"] = await self.summary_service.get_latest_compact_context(user_id)
        except Exception as e:
            logger.debug(f"[CHAT_CONTEXT] Progress report summary unavailable: {e}")

        return context

    def _summarize_completion_status(self, active_macrocycle: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not active_macrocycle:
            return {
                "has_active_workout_plan": False,
                "completed_days": [],
                "current_active_day": 1,
                "max_block_days": 7,
                "remaining_days": 7,
                "is_fully_completed": False,
                "next_plan_start_date": datetime.datetime.utcnow().date().isoformat(),
            }

        completed_days = sorted(set(int(day) for day in active_macrocycle.get("completed_days", []) if str(day).isdigit()))
        max_block_days = int(active_macrocycle.get("max_block_days") or 7)
        is_fully_completed = bool(active_macrocycle.get("is_fully_completed", False))
        remaining_days = 0 if is_fully_completed else max(max_block_days - len(completed_days), 1)
        start_offset_days = len(completed_days)
        next_plan_start_date = (datetime.datetime.utcnow().date() + datetime.timedelta(days=start_offset_days)).isoformat()

        return {
            "has_active_workout_plan": True,
            "completed_days": completed_days,
            "current_active_day": active_macrocycle.get("current_active_day", len(completed_days) + 1),
            "max_block_days": max_block_days,
            "remaining_days": remaining_days,
            "is_fully_completed": is_fully_completed,
            "difficulty_multiplier": active_macrocycle.get("plan_metadata", {}).get("current_difficulty_multiplier"),
            "next_plan_start_date": next_plan_start_date,
        }

    def _summarize_plan_document(
        self,
        plan_doc: Dict[str, Any],
        plan_field: str,
        completion_status: Dict[str, Any],
    ) -> Dict[str, Any]:
        plan_data = plan_doc.get(plan_field, {})
        summary: Dict[str, Any] = {
            "created_at": self._serialize_date(plan_doc.get("created_at")),
            "updated_at": self._serialize_date(plan_doc.get("updated_at")),
            "total_days": plan_doc.get("total_days") or self._count_plan_days(plan_data),
        }

        if plan_field == "workout_plan":
            completed_days = set(completion_status.get("completed_days", []))
            summary["completed_days"] = sorted(completed_days)
            summary["remaining_day_keys"] = self._remaining_day_keys(plan_data, completed_days)
            summary["remaining_day_preview"] = self._preview_plan_days(plan_data, completed_days)
            summary["instruction"] = (
                "If the user asks to change the current workout plan, preserve completed days and generate only "
                "the remaining days from next_plan_start_date."
            )
        else:
            summary["active"] = plan_doc.get("is_active", True)
            summary["diet_day_keys"] = self._all_day_keys(plan_data)[:7]
            summary["grocery_count"] = len(plan_doc.get("grocery_list", [])) if isinstance(plan_doc.get("grocery_list"), list) else 0

        return summary

    def _count_plan_days(self, plan_data: Any) -> int:
        if not isinstance(plan_data, dict):
            return 0
        return len(self._all_day_keys(plan_data))

    def _all_day_keys(self, plan_data: Any) -> List[str]:
        if not isinstance(plan_data, dict):
            return []
        source = plan_data.get("weekly_plan") if isinstance(plan_data.get("weekly_plan"), dict) else plan_data
        return [key for key in source.keys() if str(key).lower().startswith("day")]

    def _remaining_day_keys(self, plan_data: Any, completed_days: set[int]) -> List[str]:
        keys = self._all_day_keys(plan_data)
        remaining = []
        for key in keys:
            day_number = self._extract_day_number(key)
            if day_number is None or day_number not in completed_days:
                remaining.append(key)
        return remaining[:7]

    def _preview_plan_days(self, plan_data: Any, completed_days: set[int]) -> List[Dict[str, Any]]:
        if not isinstance(plan_data, dict):
            return []
        source = plan_data.get("weekly_plan") if isinstance(plan_data.get("weekly_plan"), dict) else plan_data
        previews = []
        for key in self._remaining_day_keys(plan_data, completed_days)[:3]:
            day = source.get(key, {})
            if not isinstance(day, dict):
                continue
            previews.append({
                "day_key": key,
                "focus": day.get("focus") or day.get("focus_area") or day.get("target_muscle_split") or day.get("day_name"),
                "exercise_count": len(day.get("exercises", [])) if isinstance(day.get("exercises"), list) else 0,
                "meal_count": len(day.get("meals", [])) if isinstance(day.get("meals"), list) else 0,
            })
        return previews

    def _extract_day_number(self, day_key: str) -> Optional[int]:
        digits = "".join(char for char in str(day_key) if char.isdigit())
        return int(digits) if digits else None

    def _serialize_date(self, value: Any) -> Optional[str]:
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        return str(value) if value else None

    def _detect_mood_signal(self, message: str) -> str:
        lower_message = message.lower()
        tired_terms = ("tired", "exhausted", "sore", "fatigued", "sleepy", "drained")
        stressed_terms = ("stressed", "anxious", "overwhelmed", "sad", "bad mood", "depressed", "upset")
        skip_terms = ("skip", "missed", "can't workout", "cannot workout", "no motivation", "lazy", "give up")
        positive_terms = ("great", "good", "motivated", "ready", "excited", "strong", "completed", "done")

        if any(term in lower_message for term in skip_terms):
            return "skip_risk_or_low_motivation"
        if any(term in lower_message for term in stressed_terms):
            return "stressed_or_negative"
        if any(term in lower_message for term in tired_terms):
            return "tired_or_recovery_needed"
        if any(term in lower_message for term in positive_terms):
            return "positive_or_motivated"
        return "neutral"

    def _detect_intent(self, message: str) -> str:
        lower_message = message.lower()
        if any(term in lower_message for term in ("calorie", "macro", "protein", "carb", "fat", "meal", "food", "diet")):
            return "nutrition_or_calorie_coaching"
        if any(term in lower_message for term in ("skip", "habit", "motivation", "streak", "challenge", "schedule")):
            return "habit_tracking_or_motivation"
        if any(term in lower_message for term in ("form", "rep", "posture", "squat", "pushup", "exercise", "workout")):
            return "workout_guidance"
        if any(term in lower_message for term in ("gym", "nearby", "facility", "location")):
            return "gym_discovery"
        return "general_companion_chat"

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

    def _adjust_user_message(
        self,
        message: str,
        is_diet_trigger: bool,
        is_workout_trigger: bool,
        companion_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Adjust user message based on context triggers."""
        plan_context = (companion_context or {}).get("plan_request_context", {})
        completion = plan_context.get("workout_completion", {}) if isinstance(plan_context, dict) else {}
        remaining_days = completion.get("remaining_days", 7)
        next_start = completion.get("next_plan_start_date", datetime.datetime.utcnow().date().isoformat())
        completed_days = completion.get("completed_days", [])
        today = datetime.datetime.now().date()
        today_label = f"{today.strftime('%A')} ({today.isoformat()})"
        try:
            start_date = datetime.datetime.fromisoformat(str(next_start).split("T")[0]).date()
        except ValueError:
            start_date = today
        workout_start_label = f"{start_date.strftime('%A')} ({start_date.isoformat()})"

        if is_diet_trigger:
            return (
                f"Create my finalized 7-day diet plan starting today, {today_label}, with meal timings and a weekly grocery list. "
                "Use real weekday/date headings for each day, starting from today rather than Monday by default. "
                "If an active diet plan summary exists in context, update it for the next 7 days instead of duplicating old details."
            )
        elif is_workout_trigger:
            return (
                f"Create my finalized workout plan starting {workout_start_label}. "
                f"If this is a change to an existing plan, preserve completed days {completed_days} and generate only "
                f"{remaining_days} remaining day(s). If no active plan exists, generate a full 7-day plan. "
                "Use real weekday/date headings for each day from the start date rather than Monday by default. "
                "Include day-by-day exercises with sets, reps, rest, and recovery notes."
            )
        else:
            return message

    def _extract_action_type(self, response_text: str) -> Optional[str]:
        """Extract action type from response text."""
        lower_text = response_text.lower()
        if "diet plan" in lower_text and "workout plan" in lower_text:
            return "plan"
        if "diet plan" in lower_text or "grocery list" in lower_text:
            return "diet"
        elif "workout plan" in lower_text:
            return "workout"
        return None

    def _truncate_text(self, text: str, max_chars: int) -> str:
        """Keep Groq requests below the model's request/token budget."""
        if not text or len(text) <= max_chars:
            return text or ""
        return text[-max_chars:]

    def _is_new_plan_request(self, message: str, is_diet_trigger: bool, is_workout_trigger: bool) -> bool:
        """Return true only when the user is asking to create a new plan."""
        if is_diet_trigger or is_workout_trigger:
            return True

        lower_message = message.lower()
        create_terms = ("create", "generate", "make", "build", "prepare", "design", "new")
        plan_terms = ("plan", "routine", "schedule", "grocery list", "meal plan", "diet plan", "workout plan")
        lookup_terms = ("today", "current", "saved", "existing", "latest", "show", "fetch", "get", "view")

        return (
            any(term in lower_message for term in create_terms)
            and any(term in lower_message for term in plan_terms)
            and not lower_message.strip().startswith(lookup_terms)
        )

    def _should_include_plan_context(
        self,
        message: str,
        is_diet_trigger: bool,
        is_workout_trigger: bool,
        is_plan_lookup_request: bool,
        is_new_plan_request: bool,
    ) -> bool:
        """Include saved plans only when the user is acting on plans."""
        if is_diet_trigger or is_workout_trigger or is_plan_lookup_request or is_new_plan_request:
            return True

        lower_message = message.lower()
        plan_terms = ("workout plan", "diet plan", "meal plan", "routine", "schedule", "grocery list")
        action_terms = ("change", "update", "modify", "replace", "regenerate", "continue", "next week")
        return any(term in lower_message for term in plan_terms) and any(term in lower_message for term in action_terms)

    def _should_include_report_context(self, message: str) -> bool:
        """Include only compact summaries for progress/report/trend questions."""
        lower_message = message.lower()
        report_terms = ("progress", "report", "trend", "weekly stats", "monthly stats", "history", "summary", "completion", "streak")
        return any(term in lower_message for term in report_terms)

    def _is_saved_plan_lookup_request(self, message: str) -> bool:
        """Detect requests that should fetch stored plan data instead of generating a new plan."""
        lower_message = message.lower()
        lookup_terms = ("today", "current", "saved", "existing", "latest", "show", "fetch", "get", "view")
        plan_terms = ("plan", "routine", "schedule", "meal", "diet", "workout")
        create_terms = ("create", "generate", "make", "build", "prepare", "design", "new")

        return (
            any(term in lower_message for term in lookup_terms)
            and any(term in lower_message for term in plan_terms)
            and not any(term in lower_message for term in create_terms)
        )

    async def _get_saved_plan_lookup_response(self, user_id: str, user_message: str) -> Dict[str, Any]:
        """Fetch the latest stored diet/workout plan and format a direct chat answer."""
        lower_message = user_message.lower()
        wants_diet = any(term in lower_message for term in ("diet", "meal", "food", "nutrition"))
        wants_workout = any(term in lower_message for term in ("workout", "exercise", "routine", "training"))

        if not wants_diet and not wants_workout:
            wants_diet = True
            wants_workout = True

        sections: List[str] = []
        if wants_workout:
            workout_plan = await workout_plans_col.find_one({"user_id": user_id}, sort=[("created_at", -1)])
            sections.append(self._format_saved_plan_section("Workout Plan", workout_plan, "workout_plan", user_message))

        if wants_diet:
            diet_plan = await diet_plans_col.find_one({"user_id": user_id}, sort=[("created_at", -1)])
            sections.append(self._format_saved_plan_section("Diet Plan", diet_plan, "diet_plan", user_message))

        reply = "\n\n".join(section for section in sections if section).strip()
        if not reply:
            reply = "I could not find a saved plan yet. Ask me to create a new workout or diet plan when you are ready."

        return {
            "motivational_reply": reply,
            "requires_confirmation_buttons": False,
            "confirmation_action_type": None,
            "plan_action_trigger": None,
        }

    def _format_saved_plan_section(
        self,
        title: str,
        plan_doc: Optional[Dict[str, Any]],
        plan_field: str,
        user_message: str,
    ) -> str:
        if not plan_doc:
            return f"**{title}**\nNo saved {title.lower()} was found."

        plan_data = plan_doc.get(plan_field, {})
        lower_message = user_message.lower()
        selected_day_date = None
        if "today" in lower_message:
            plan_data = self._extract_today_plan(plan_data)
            if isinstance(plan_data, dict):
                selected_day_date = plan_data.get("date")
            title = f"Today's {title}"

        created_at = plan_doc.get("updated_at") or plan_doc.get("created_at")
        date_label = self._format_lookup_date_label(selected_day_date, created_at)
        return f"**{title}** ({date_label})\n{self._format_plan_value(plan_data)}"

    def _extract_today_plan(self, plan_data: Any) -> Any:
        if not isinstance(plan_data, dict):
            return plan_data

        today = datetime.datetime.now().date().isoformat()
        for value in plan_data.values():
            if isinstance(value, dict) and str(value.get("date", "")).split("T")[0] == today:
                return value

        weekday_key = f"day_{datetime.datetime.now().weekday() + 1}"
        if weekday_key in plan_data:
            return plan_data[weekday_key]

        if "weekly_plan" in plan_data and isinstance(plan_data["weekly_plan"], dict):
            return self._extract_today_plan(plan_data["weekly_plan"])

        first_key = next(iter(plan_data), None)
        return plan_data.get(first_key, plan_data) if first_key else plan_data

    def _format_lookup_date_label(self, selected_day_date: Any, fallback_date: Any) -> str:
        if selected_day_date:
            try:
                parsed = datetime.datetime.fromisoformat(str(selected_day_date).split("T")[0]).date()
                return parsed.strftime("%b %d, %Y")
            except ValueError:
                return str(selected_day_date)
        if isinstance(fallback_date, datetime.datetime):
            return fallback_date.strftime("%b %d, %Y")
        return "saved plan"

    def _format_plan_value(self, value: Any, indent: int = 0) -> str:
        prefix = "  " * indent
        if isinstance(value, dict):
            lines: List[str] = []
            for key, item in value.items():
                label = str(key).replace("_", " ").title()
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}- **{label}:**")
                    lines.append(self._format_plan_value(item, indent + 1))
                else:
                    lines.append(f"{prefix}- **{label}:** {item}")
            return "\n".join(lines)

        if isinstance(value, list):
            if not value:
                return f"{prefix}- No items listed."
            lines = []
            for item in value:
                if isinstance(item, (dict, list)):
                    lines.append(self._format_plan_value(item, indent))
                else:
                    lines.append(f"{prefix}- {item}")
            return "\n".join(lines)

        return f"{prefix}- {value}"
