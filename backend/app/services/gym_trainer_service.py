"""
Service Layer: Gym Trainer Business Logic
Manages OpenCV pose tracking session launch and workout statistics retrieval.
"""

import asyncio
import concurrent.futures
import threading
from typing import Dict, Any, Optional
from app.modules.trainer_engine import launch_native_opencv_tracker
from app.repositories.gym_trainer_repo import GymTrainerRepository


class GymTrainerService:
    """Service for vision-based workout tracking."""

    def __init__(self):
        self.repo = GymTrainerRepository()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        self._stop_events: Dict[str, threading.Event] = {}

    async def start_vision_session(
        self,
        user_id: str,
        exercise_type: str,
        target_reps_per_set: int = 10,
        target_sets: int = 1,
    ) -> Dict[str, Any]:
        """
        Launch OpenCV tracker in thread executor (non-blocking).
        
        Args:
            user_id: User ID
            exercise_type: Type of exercise to track
            
        Returns:
            Status message with task ID
        """
        try:
            loop = asyncio.get_running_loop()
            stop_event = threading.Event()
            self._stop_events[user_id] = stop_event

            # Queue the executor task and get future
            future = loop.run_in_executor(
                self.executor, 
                launch_native_opencv_tracker, 
                user_id, 
                exercise_type,
                stop_event,
                target_reps_per_set,
                target_sets,
            )
            print(f"[TRACKER] Vision session queued for {user_id} - {exercise_type}")
            
            # Return immediately without awaiting (fire-and-forget pattern)
            # Client can poll /latest-stats endpoint for updates
            return {
                "status": "initiated", 
                "message": "Pose tracking session started in background",
                "user_id": user_id,
                "exercise_type": exercise_type,
                "target_reps_per_set": target_reps_per_set,
                "target_sets": target_sets,
            }
        except RuntimeError as e:
            # RuntimeError means no event loop running (shouldn't happen in FastAPI context)
            print(f"[ERROR] Event loop error in vision session: {e}")
            raise
        except Exception as e:
            print(f"[ERROR] Failed to start vision session: {e}")
            raise

    async def stop_vision_session(self, user_id: str) -> Dict[str, Any]:
        """
        Request stopping the OpenCV desktop trainer session.
        """
        stop_event = self._stop_events.get(user_id)
        if not stop_event:
            return {"status": "not_found", "message": "No active training session found for user."}

        stop_event.set()
        self._stop_events.pop(user_id, None)
        print(f"[TRACKER] Stop signal sent for user {user_id}")
        return {"status": "stopping", "message": "Stop signal sent to desktop tracker."}

    async def get_latest_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieve latest workout statistics for UI refresh.
        
        Args:
            user_id: User ID
            
        Returns:
            Latest exercise stats or not found indicator
        """
        try:
            log = await self.repo.get_latest_workout_stats(user_id)

            if not log:
                return {"found": False}

            exercises = log.get("exercises")
            exercise = exercises[0] if isinstance(exercises, list) and exercises else {}

            timestamp = log.get("timestamp")
            timestamp_str = "Just Now"
            if timestamp:
                try:
                    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                except (AttributeError, TypeError):
                    timestamp_str = str(timestamp)
            
            return {
                "found": True,
                "exercise_name": exercise.get("name", "Unknown"),
                "sets_completed": exercise.get("sets_completed", 0),
                "correct_reps": exercise.get("correct_reps", 0),
                "incorrect_reps": exercise.get("incorrect_reps", 0),
                "timestamp": timestamp_str
            }

        except Exception as e:
            print(f"[ERROR] Failed to retrieve latest stats: {e}")
            raise
