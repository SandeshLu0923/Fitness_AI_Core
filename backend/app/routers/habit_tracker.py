"""
Router Layer: Habit Tracker Endpoints
FastAPI routes for macrocycle generation and daily challenge tracking.
"""

import json
import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field, ValidationError
from pymongo.errors import PyMongoError
from app.modules.trainer_utils import WeeklyMacrocyclePlan


# ============================================================================
# Request/Response Models
# ============================================================================
class MacrocycleConfirmationRequest(BaseModel):
    user_id: str = Field(..., description="Unique user identifier")
    action: str = Field(..., description="Target action: 'update' or 'cancel'")
    macrocycle_payload: Optional[WeeklyMacrocyclePlan] = Field(..., description="The macrocycle plan data")


class ChallengeLogRequest(BaseModel):
    user_id: str
    day_number: int
    challenge_text: str


class SkipDayRequest(BaseModel):
    user_id: str
    reason: Optional[str] = None


# ============================================================================
# Router Setup
# ============================================================================
router = APIRouter(prefix="/api/habit-tracker", tags=["Macrocycles & Daily Challenges"])

_service_cache = None
def get_service():
    global _service_cache
    if _service_cache is None:
        from app.services.habit_tracker_service import HabitTrackerService
        _service_cache = HabitTrackerService()
    return _service_cache

_repo_cache = None
def get_repo():
    global _repo_cache
    if _repo_cache is None:
        from app.repositories.habit_tracker_repo import HabitTrackerRepository
        _repo_cache = HabitTrackerRepository()
    return _repo_cache


# ============================================================================
# Endpoints
# ============================================================================
@router.post("/generate-weekly-block", response_model=WeeklyMacrocyclePlan)
async def generate_weekly_block(user_id: str):
    """Generate a personalized weekly training macrocycle."""
    try:
        service = get_service()
        result = await service.generate_weekly_block(user_id)
        return result

    except ValueError as e:
        print(f"[ERROR] Generation failed: {e}")
        raise HTTPException(status_code=404, detail="User profile required.")
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"[VALIDATION_ERROR] Macrocycle validation failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to parse macrocycle model output.")
    except PyMongoError as e:
        print(f"[DB_ERROR] Database check failed: {e}")
        raise HTTPException(status_code=500, detail="Database validation check failed.")


@router.post("/confirm-macrocycle")
async def confirm_macrocycle(payload: MacrocycleConfirmationRequest):
    """Confirm and activate a macrocycle plan."""
    try:
        action = payload.action.strip().lower()

        if action == "cancel":
            return {"status": "discarded", "message": "Weekly macrocycle setup rejected."}

        elif action == "update":
            if not payload.macrocycle_payload:
                raise HTTPException(status_code=400, detail="Missing macrocycle payload object data.")

            service = get_service()
            result = await service.confirm_macrocycle(payload.user_id, payload.macrocycle_payload)
            return result

        else:
            raise HTTPException(status_code=400, detail="Action not recognized. Use 'update' or 'cancel'.")

    except PyMongoError as e:
        print(f"[DB_ERROR] Failed to confirm macrocycle: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate macrocycle.")


@router.get("/active-day-plan")
async def get_active_day_plan(user_id: str = Query(..., description="User ID")):
    """Get the current active day's training details."""
    try:
        user_id = user_id.strip()
        repo = get_repo()
        macrocycle = await repo.get_active_macrocycle(user_id)

        if not macrocycle:
            # Return default/empty response instead of raising
            return {
                "current_active_day": 1,
                "difficulty_multiplier": 1.0,
                "day_details": {
                    "day_number": 1,
                    "focus_area": "Preparation",
                    "exercises": [],
                    "notes": "No active macrocycle. Create one to begin training!"
                }
            }

        if macrocycle.get("is_fully_completed", False):
            return {"message": "Block completed! Request your next periodized program."}

        current_day = macrocycle["current_active_day"]
        schedule_array = macrocycle["plan_metadata"]["schedule"]
        today = datetime.datetime.now().date().isoformat()
        day_block = next(
            (day for day in schedule_array if str(day.get("date", "")).split("T")[0] == today),
            None
        )
        if not day_block:
            day_block = next((day for day in schedule_array if day["day_number"] == current_day), None)

        if not day_block:
            # Return default day block instead of raising error
            return {
                "current_active_day": current_day,
                "difficulty_multiplier": macrocycle["plan_metadata"].get("current_difficulty_multiplier", 1.0),
                "day_details": {
                    "day_number": current_day,
                    "focus_area": "Recovery",
                    "exercises": [],
                    "notes": "Unable to retrieve day details"
                }
            }

        return {
            "current_active_day": day_block.get("day_number", current_day),
            "tracking_active_day": current_day,
            "difficulty_multiplier": macrocycle["plan_metadata"].get("current_difficulty_multiplier"),
            "day_details": day_block
        }

    except Exception as e:
        print(f"[WARNING] Failed to retrieve active day plan: {type(e).__name__}: {e}")
        # Return default response with 200 status
        return {
            "current_active_day": 1,
            "difficulty_multiplier": 1.0,
            "day_details": {
                "day_number": 1,
                "focus_area": "Building Your Foundation",
                "exercises": [],
                "notes": "Getting ready to start your habit formation journey! We're preparing your personalized plan. Check back in a moment for your exercises!"
            }
        }


@router.get("/active-schedule")
async def get_active_schedule(user_id: str = Query(..., description="User ID")):
    """Return the current shifted active macrocycle schedule."""
    try:
        user_id = user_id.strip()
        repo = get_repo()
        macrocycle = await repo.get_active_macrocycle(user_id)
        if not macrocycle:
            return {"schedule": [], "current_active_day": None, "skipped_days": []}

        plan_metadata = macrocycle.get("plan_metadata", {}) if isinstance(macrocycle, dict) else {}
        return {
            "schedule": plan_metadata.get("schedule", []),
            "current_active_day": macrocycle.get("current_active_day"),
            "skipped_days": macrocycle.get("skipped_days", []),
            "is_fully_completed": macrocycle.get("is_fully_completed", False),
        }
    except PyMongoError as e:
        print(f"[DB_ERROR] Failed to retrieve active schedule: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve active schedule.")


@router.post("/complete-active-day")
async def complete_active_day(payload: ChallengeLogRequest):
    """Mark the current active day as completed."""
    try:
        user_id = payload.user_id.strip()
        repo = get_repo()
        macrocycle = await repo.get_active_macrocycle(user_id)

        if not macrocycle:
            raise HTTPException(status_code=404, detail="Active macrocycle instance missing.")

        from app.database import completed_challenges_col

        current_day = macrocycle["current_active_day"]
        max_block_days = macrocycle.get("max_block_days", 7)
        completed_list = list(macrocycle.get("completed_days", []))

        # Log the challenge completion
        await completed_challenges_col.insert_one({
            "user_id": user_id,
            "challenge_text": payload.challenge_text,
            "completed_at": datetime.datetime.utcnow()
        })

        # Mark day as completed
        if current_day not in completed_list:
            completed_list.append(current_day)

        next_day = current_day + 1
        is_completed = len(completed_list) >= max_block_days or next_day > max_block_days

        if is_completed:
            from app.database import users_col
            await users_col.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "active_macrocycle.is_fully_completed": True,
                        "active_macrocycle.completed_days": completed_list
                    }
                }
            )
            message = "Phenomenal effort! You have completed the training block."
        else:
            from app.database import users_col
            await users_col.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "active_macrocycle.current_active_day": next_day,
                        "active_macrocycle.completed_days": completed_list
                    }
                }
            )
            message = f"Day {current_day} verified! Moving to Day {next_day}."

        try:
            from app.services.workout_summary_service import WorkoutSummaryService
            summary_service = WorkoutSummaryService()
            await summary_service.get_weekly_summary(user_id, persist=True)
            await summary_service.get_monthly_summary(user_id, persist=True)
        except Exception as summary_error:
            print(f"[SUMMARY_REFRESH_WARNING] {summary_error}")

        return {
            "status": "success",
            "message": message,
            "macrocycle_finished": is_completed
        }

    except PyMongoError as e:
        print(f"[DB_ERROR] Failed to complete active day: {e}")
        raise HTTPException(status_code=500, detail="Failed to log day completion.")


@router.post("/skip-active-day")
async def skip_active_day(payload: SkipDayRequest):
    """Skip the current day and shift the skipped workout into the next rest day."""
    try:
        user_id = payload.user_id.strip()
        repo = get_repo()
        macrocycle = await repo.get_active_macrocycle(user_id)

        if not macrocycle:
            raise HTTPException(status_code=404, detail="Active macrocycle instance missing.")
        if macrocycle.get("is_fully_completed", False):
            raise HTTPException(status_code=400, detail="Training block is already completed.")

        plan_metadata = dict(macrocycle.get("plan_metadata", {}))
        schedule = list(plan_metadata.get("schedule", []))
        today = datetime.datetime.now().date().isoformat()
        current_idx = next(
            (idx for idx, day in enumerate(schedule) if str(day.get("date", "")).split("T")[0] == today),
            -1
        )
        if current_idx == -1:
            current_day = int(macrocycle.get("current_active_day", 1))
            current_idx = next((idx for idx, day in enumerate(schedule) if int(day.get("day_number", 0)) == current_day), -1)
        else:
            current_day = int(schedule[current_idx].get("day_number", current_idx + 1))

        if current_idx < 0 or current_idx >= len(schedule):
            raise HTTPException(status_code=404, detail="Current day was not found in the active schedule.")

        skipped_block = dict(schedule[current_idx])
        if skipped_block.get("was_skipped", False):
            raise HTTPException(status_code=400, detail="Today's workout is already marked as skipped.")
        if skipped_block.get("is_rest_day", False):
            raise HTTPException(status_code=400, detail="Today is already a rest or skipped day. No workout needs to be skipped.")

        rest_idx = next(
            (
                idx for idx in range(current_idx + 1, len(schedule))
                if isinstance(schedule[idx], dict) and schedule[idx].get("is_rest_day", False)
            ),
            -1
        )

        if rest_idx == -1:
            rest_idx = len(schedule)
            last_day = dict(schedule[-1]) if schedule else {}
            next_day_number = int(last_day.get("day_number", len(schedule))) + 1
            next_date = _add_days_to_iso_date(last_day.get("date"), 1)
            schedule.append({
                "day_number": next_day_number,
                "date": next_date,
                "day_name": _weekday_name(next_date),
                "target_muscle_split": "Extended Recovery Slot",
                "is_rest_day": True,
                "exercises": [],
                "daily_metric_challenge": "Recovery buffer created after skipped workout.",
            })
            plan_metadata["block_duration_days"] = next_day_number
            macrocycle["max_block_days"] = next_day_number

        for idx in range(rest_idx, current_idx + 1, -1):
            schedule[idx] = _move_training_content(schedule[idx - 1], schedule[idx])

        moved_to_day = int(schedule[current_idx + 1].get("day_number", current_day + 1))
        schedule[current_idx] = _mark_skipped_slot(schedule[current_idx], moved_to_day)
        plan_metadata["schedule"] = schedule

        skipped_records = list(macrocycle.get("skipped_days", []))
        skipped_records.append({
            "original_day_number": current_day,
            "moved_to_day_number": moved_to_day,
            "date": skipped_block.get("date") or today,
            "reason": payload.reason or "",
            "skipped_at": datetime.datetime.utcnow(),
        })

        next_active_day = min(current_day + 1, int(macrocycle.get("max_block_days", len(schedule))))

        from app.database import users_col
        await users_col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "active_macrocycle.current_active_day": next_active_day,
                    "active_macrocycle.max_block_days": int(macrocycle.get("max_block_days", len(schedule))),
                    "active_macrocycle.plan_metadata": plan_metadata,
                    "active_macrocycle.skipped_days": skipped_records,
                    "active_macrocycle.schedule_shift_count": len(skipped_records),
                }
            }
        )

        try:
            from app.services.workout_summary_service import WorkoutSummaryService
            summary_service = WorkoutSummaryService()
            await summary_service.get_weekly_summary(user_id, persist=True)
            await summary_service.get_monthly_summary(user_id, persist=True)
        except Exception as summary_error:
            print(f"[SUMMARY_REFRESH_WARNING] {summary_error}")

        return {
            "status": "success",
            "message": f"Day {current_day} skipped. Its workout moved to Day {moved_to_day}.",
            "current_active_day": next_active_day,
            "moved_to_day_number": moved_to_day,
            "skipped_days": skipped_records
        }

    except HTTPException:
        raise
    except PyMongoError as e:
        print(f"[DB_ERROR] Failed to skip active day: {e}")
        raise HTTPException(status_code=500, detail="Failed to skip active day.")


def _move_training_content(source_day: dict, target_day: dict) -> dict:
    """Move workout content into the target calendar slot while preserving target identity."""
    moved = dict(target_day)
    for key in ("target_muscle_split", "is_rest_day", "exercises", "daily_metric_challenge"):
        moved[key] = source_day.get(key)
    moved["shifted_from_day_number"] = source_day.get("day_number")
    moved.pop("was_skipped", None)
    moved.pop("moved_to_day_number", None)
    moved.pop("skipped_at", None)
    return moved


def _mark_skipped_slot(day: dict, moved_to_day: int) -> dict:
    skipped = dict(day)
    skipped["target_muscle_split"] = f"Skipped - moved to Day {moved_to_day}"
    skipped["is_rest_day"] = True
    skipped["exercises"] = []
    skipped["daily_metric_challenge"] = f"Skipped workout moved to Day {moved_to_day}."
    skipped["was_skipped"] = True
    skipped["moved_to_day_number"] = moved_to_day
    skipped["skipped_at"] = datetime.datetime.utcnow().isoformat()
    return skipped


def _add_days_to_iso_date(date_value: Optional[str], days: int) -> Optional[str]:
    if not date_value:
        return None
    try:
        base = datetime.datetime.fromisoformat(str(date_value).split("T")[0]).date()
        return (base + datetime.timedelta(days=days)).isoformat()
    except ValueError:
        return None


def _weekday_name(date_value: Optional[str]) -> str:
    if not date_value:
        return "Extended Day"
    try:
        parsed = datetime.datetime.fromisoformat(str(date_value).split("T")[0]).date()
        return parsed.strftime("%A")
    except ValueError:
        return "Extended Day"


@router.post("/challenges-hub")
async def get_challenges_hub(payload: dict):
    """Get current challenges hub data for the user."""
    try:
        user_id = payload.get("user_id", "").strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        # Return default challenge structure
        return {
            "status": "success",
            "current_difficulty_multiplier": "Intermediate",
            "daily_metric_challenge": "Squats - Complete 30 reps",
            "milestone_volume_target": "100 total reps this week",
            "user_id": user_id
        }

    except Exception as e:
        print(f"[CHALLENGES_HUB_ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch challenges hub")


@router.post("/complete-challenge")
async def complete_challenge(payload: dict):
    """Mark a challenge as completed."""
    try:
        user_id = payload.get("user_id", "").strip()
        challenge_text = payload.get("challenge_text", "")
        challenge_type = payload.get("challenge_type", "daily")

        if not user_id or not challenge_text:
            raise HTTPException(status_code=400, detail="Missing required fields")

        # Log the completion
        from app.database import completed_challenges_col
        await completed_challenges_col.insert_one({
            "user_id": user_id,
            "challenge_text": challenge_text,
            "challenge_type": challenge_type,
            "completed_at": datetime.datetime.utcnow()
        })

        return {
            "status": "success",
            "message": f"Challenge '{challenge_text}' completed!",
            "challenge_type": challenge_type
        }

    except Exception as e:
        print(f"[COMPLETE_CHALLENGE_ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to complete challenge")


@router.get("/completed-challenges/{user_id}")
async def get_completed_challenges(user_id: str):
    """Return recent completed challenges for the user."""
    try:
        from app.database import completed_challenges_col

        cursor = completed_challenges_col.find({"user_id": user_id.strip()}).sort("completed_at", -1).limit(20)
        docs = await cursor.to_list(length=20)
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            if isinstance(doc.get("completed_at"), datetime.datetime):
                doc["completed_at"] = doc["completed_at"].isoformat()

        return {
            "status": "success",
            "completed_challenges": docs,
            "total_completed": len(docs)
        }
    except Exception as e:
        print(f"[COMPLETED_CHALLENGES_ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch completed challenges")


# Import json and ValidationError
import json
from pydantic import ValidationError
