"""
Router Layer: Gym Trainer Endpoints
FastAPI routes for pose tracking and workout statistics.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from pymongo.errors import PyMongoError
from datetime import datetime
from typing import Optional
import os
import time

import httpx


# ============================================================================
# Request Models
# ============================================================================
class StartTrackingRequest(BaseModel):
    user_id: str
    exercise_type: str
    target_reps_per_set: int = 10
    target_sets: int = 1


class LogCompletedWorkoutRequest(BaseModel):
    user_id: str
    exercise_name: str
    sets_completed: int
    correct_reps: int
    incorrect_reps: int
    target_reps_per_set: Optional[int] = None
    target_sets: Optional[int] = None
    notes: Optional[str] = None


class StopTrackingRequest(BaseModel):
    user_id: str


# ============================================================================
# Router Setup
# ============================================================================
router = APIRouter(prefix="/api/gym-trainer", tags=["AI Gym Trainer"])
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "https://fitness-ai-core.onrender.com").rstrip("/")

_service_cache = None
def get_service():
    global _service_cache
    if _service_cache is None:
        from app.services.gym_trainer_service import GymTrainerService
        _service_cache = GymTrainerService()
    return _service_cache


# ============================================================================
# Endpoints
# ============================================================================
@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def start_vision_session(payload: StartTrackingRequest):
    """Launch OpenCV pose tracking session."""
    start_time = time.perf_counter()
    try:
        service = get_service()
        result = await service.start_vision_session(
            payload.user_id,
            payload.exercise_type,
            max(1, payload.target_reps_per_set),
            max(1, payload.target_sets),
        )
        from app.services.analytics_service import AnalyticsService
        await AnalyticsService.log_ai_inference(
            "workout_detection",
            user_id=payload.user_id,
            success=True,
            latency_ms=(time.perf_counter() - start_time) * 1000,
            metadata={
                "exercise_type": payload.exercise_type,
                "target_reps_per_set": payload.target_reps_per_set,
                "target_sets": payload.target_sets,
            }
        )
        return result

    except Exception as e:
        from app.services.analytics_service import AnalyticsService
        await AnalyticsService.log_ai_inference(
            "workout_detection",
            user_id=payload.user_id,
            success=False,
            latency_ms=(time.perf_counter() - start_time) * 1000,
        )
        print(f"[ERROR] Failed to start vision session: {e}")
        raise HTTPException(status_code=500, detail="Unable to start pose tracking at this time.")


@router.post("/stop", status_code=status.HTTP_200_OK)
async def stop_vision_session(payload: StopTrackingRequest):
    """Stop an active OpenCV pose tracking session."""
    try:
        service = get_service()
        result = await service.stop_vision_session(payload.user_id)
        return result
    except Exception as e:
        print(f"[ERROR] Failed to stop vision session: {e}")
        raise HTTPException(status_code=500, detail="Unable to stop pose tracking at this time.")


@router.get("/latest-stats/{user_id}")
async def get_latest_workout_stats(user_id: str):
    """Retrieve live exercise statistics first, then aggregate today's completed workouts."""
    try:
        from app.modules.tracker_state import get_latest_live_stats
        from datetime import date, timedelta

        today = date.today().isoformat()
        live_stat = get_latest_live_stats(user_id)

        if live_stat:
            return {
                "found": True,
                "is_live": bool(live_stat.get("session_active")),
                "exercise_name": live_stat.get("exercise_name", "Unknown"),
                "sets_completed": int(live_stat.get("sets_completed") or 0),
                "target_sets": int(live_stat.get("target_sets") or 0),
                "target_reps_per_set": int(live_stat.get("target_reps_per_set") or 0),
                "current_set": int(live_stat.get("current_set") or 1),
                "current_set_reps": int(live_stat.get("current_set_reps") or 0),
                "correct_reps": int(live_stat.get("correct_reps") or 0),
                "incorrect_reps": int(live_stat.get("incorrect_reps") or 0),
                "total_reps": int(live_stat.get("total_reps") or 0),
                "target_total_reps": int(live_stat.get("target_total_reps") or 0),
                "progress_percent": float(live_stat.get("progress_percent") or 0),
                "exercise_completed": bool(live_stat.get("exercise_completed")),
                "accuracy": float(live_stat.get("accuracy") or 0),
                "feedback": live_stat.get("feedback", ""),
                "position_state": live_stat.get("position_state", ""),
                "timestamp": live_stat.get("timestamp", "N/A"),
                "date": today,
            }

        from app.database import exercise_logs_col
        live_since = datetime.utcnow() - timedelta(minutes=45)
        db_live_stat = await exercise_logs_col.find_one(
            {
                "user_id": user_id,
                "type": "live_tracking",
                "timestamp": {"$gte": live_since},
            },
            sort=[("timestamp", -1)]
        )

        if db_live_stat:
            return {
                "found": True,
                "is_live": bool(db_live_stat.get("session_active")),
                "exercise_name": db_live_stat.get("exercise_name", "Unknown"),
                "sets_completed": int(db_live_stat.get("sets_completed") or 0),
                "target_sets": int(db_live_stat.get("target_sets") or 0),
                "target_reps_per_set": int(db_live_stat.get("target_reps_per_set") or 0),
                "current_set": int(db_live_stat.get("current_set") or 1),
                "current_set_reps": int(db_live_stat.get("current_set_reps") or 0),
                "correct_reps": int(db_live_stat.get("correct_reps") or 0),
                "incorrect_reps": int(db_live_stat.get("incorrect_reps") or 0),
                "total_reps": int(db_live_stat.get("total_reps") or 0),
                "target_total_reps": int(db_live_stat.get("target_total_reps") or 0),
                "progress_percent": float(db_live_stat.get("progress_percent") or 0),
                "exercise_completed": bool(db_live_stat.get("exercise_completed")),
                "accuracy": float(db_live_stat.get("accuracy") or 0),
                "feedback": db_live_stat.get("feedback", ""),
                "position_state": db_live_stat.get("position_state", ""),
                "timestamp": db_live_stat.get("timestamp", "N/A"),
                "date": today,
            }
        
        # Get all completed workouts for today
        workouts = await exercise_logs_col.find({
            "user_id": user_id,
            "date": today
        }).sort("completed_at", -1).to_list(length=100)
        
        if not workouts:
            # Return default stats if no workouts completed
            return {
                "found": False,
                "exercise_name": "None",
                "sets_completed": 0,
                "correct_reps": 0,
                "incorrect_reps": 0,
                "timestamp": "No workouts completed today",
                "message": "Start a workout to track progress"
            }
        
        # Aggregate stats from all workouts
        total_correct_reps = sum(w.get("correct_reps", 0) for w in workouts)
        total_incorrect_reps = sum(w.get("incorrect_reps", 0) for w in workouts)
        total_sets = sum(w.get("sets_completed", 0) for w in workouts)
        
        # Get the most recent workout details
        latest_workout = workouts[0]  # Already sorted by time in database
        
        total_accuracy = round(
            (total_correct_reps / max(total_correct_reps + total_incorrect_reps, 1)) * 100, 2
        ) if (total_correct_reps + total_incorrect_reps) > 0 else 0
        
        return {
            "found": True,
            "exercise_name": latest_workout.get("exercise_name", "Unknown"),
            "sets_completed": total_sets,
            "correct_reps": total_correct_reps,
            "incorrect_reps": total_incorrect_reps,
            "total_reps": total_correct_reps + total_incorrect_reps,
            "accuracy": total_accuracy,
            "workout_count": len(workouts),
            "timestamp": latest_workout.get("completed_at", "N/A"),
            "date": today,
            "all_workouts": [
                {
                    "exercise": w.get("exercise_name"),
                    "sets": w.get("sets_completed"),
                    "correct_reps": w.get("correct_reps"),
                    "incorrect_reps": w.get("incorrect_reps"),
                    "accuracy": w.get("accuracy")
                } for w in workouts
            ]
        }

    except RuntimeError as e:
        if "Database not initialized" in str(e) or "Admin database not initialized" in str(e):
            return {
                "found": False,
                "exercise_name": "None",
                "sets_completed": 0,
                "correct_reps": 0,
                "incorrect_reps": 0,
                "timestamp": "No local stats yet",
                "message": "Start a workout to track progress",
            }
        print(f"[ERROR] Failed to retrieve stats: {e}")
        raise HTTPException(status_code=500, detail="Unable to load workout statistics at this time.")
    except PyMongoError as e:
        print(f"[DB_ERROR] Failed to load latest stats: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load latest workout stats.")
    except Exception as e:
        print(f"[ERROR] Failed to retrieve stats: {e}")
        raise HTTPException(status_code=500, detail="Unable to load workout statistics at this time.")


@router.post("/log-completed-workout", status_code=status.HTTP_201_CREATED)
async def log_completed_workout(payload: LogCompletedWorkoutRequest):
    """Log a completed workout session with form correction and rep counts."""
    try:
        from app.database import exercise_logs_col
        from datetime import date
        
        completed_workout = {
            "user_id": payload.user_id,
            "exercise_name": payload.exercise_name,
            "sets_completed": payload.sets_completed,
            "target_sets": payload.target_sets,
            "target_reps_per_set": payload.target_reps_per_set,
            "correct_reps": payload.correct_reps,
            "incorrect_reps": payload.incorrect_reps,
            "total_reps": payload.correct_reps + payload.incorrect_reps,
            "accuracy": round((payload.correct_reps / max(payload.correct_reps + payload.incorrect_reps, 1)) * 100, 2),
            "notes": payload.notes or "",
            "completed_at": datetime.utcnow(),
            "date": date.today().isoformat()
        }
        
        result = await exercise_logs_col.insert_one(completed_workout)
        try:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference(
                "workout_detection_result",
                user_id=payload.user_id,
                success=True,
                metadata={
                    "exercise_name": payload.exercise_name,
                    "accuracy": completed_workout["accuracy"],
                    "total_reps": completed_workout["total_reps"],
                }
            )
        except Exception as analytics_error:
            print(f"[ANALYTICS_WARNING] Workout result not logged: {analytics_error}")
        
        return {
            "status": "success",
            "message": f"Workout logged: {payload.exercise_name}",
            "workout_id": str(result.inserted_id),
            "data": {
                "exercise": payload.exercise_name,
                "correct_reps": payload.correct_reps,
                "incorrect_reps": payload.incorrect_reps,
                "accuracy": round((payload.correct_reps / max(payload.correct_reps + payload.incorrect_reps, 1)) * 100, 2)
            }
        }
    except RuntimeError as e:
        if "Database not initialized" not in str(e):
            print(f"[LOG_WORKOUT_ERROR] {e}")
            raise HTTPException(status_code=500, detail="Failed to log workout")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{BACKEND_API_URL}/api/gym-trainer/log-completed-workout",
                    json=payload.model_dump(),
                )
                response.raise_for_status()
                return response.json()
        except Exception as forward_error:
            print(f"[LOG_WORKOUT_FORWARD_ERROR] {forward_error}")
            raise HTTPException(status_code=502, detail="Failed to forward workout to backend")
    except Exception as e:
        print(f"[LOG_WORKOUT_ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to log workout")


@router.get("/completed-workouts/{user_id}", status_code=status.HTTP_200_OK)
async def get_completed_workouts_today(user_id: str):
    """Get all completed workouts for today."""
    try:
        from app.database import exercise_logs_col
        from datetime import date
        
        today = date.today().isoformat()
        workouts = await exercise_logs_col.find({
            "user_id": user_id,
            "date": today
        }).sort("completed_at", -1).to_list(length=100)
        
        for workout in workouts:
            workout["_id"] = str(workout["_id"])
        
        return {
            "status": "success",
            "user_id": user_id,
            "date": today,
            "completed_workouts": workouts,
            "total_completed": len(workouts)
        }
    except Exception as e:
        print(f"[GET_COMPLETED_ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve completed workouts")


@router.get("/weekly-stats/{user_id}")
async def get_weekly_stats(user_id: str):
    """Get weekly workout stats, report notes, and compact trend data."""
    try:
        from app.services.workout_summary_service import WorkoutSummaryService

        summary = await WorkoutSummaryService().get_weekly_summary(user_id.strip())
        summary["status"] = "success"
        return summary
    except Exception as e:
        print(f"[WEEKLY_STATS_ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve weekly stats")


@router.get("/monthly-stats/{user_id}")
async def get_monthly_stats(user_id: str):
    """Get monthly workout stats, report notes, and trend data."""
    try:
        from app.services.workout_summary_service import WorkoutSummaryService

        summary = await WorkoutSummaryService().get_monthly_summary(user_id.strip())
        summary["status"] = "success"
        return summary
    except Exception as e:
        print(f"[MONTHLY_STATS_ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve monthly stats")
