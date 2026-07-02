"""
Utilities for aligning saved plans to real calendar dates.
"""

from __future__ import annotations

import copy
import datetime
from typing import Any, Dict, List


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def align_weekly_plan_dates(plan_data: Dict[str, Any], start_date: datetime.date | None = None) -> Dict[str, Any]:
    """Return a copy of a weekly plan whose day_1 starts on start_date."""
    if not isinstance(plan_data, dict):
        return plan_data

    aligned = copy.deepcopy(plan_data)
    start = start_date or datetime.date.today()
    source = aligned.get("weekly_plan") if isinstance(aligned.get("weekly_plan"), dict) else aligned

    if isinstance(source.get("days"), list):
        for index, day in enumerate(source["days"]):
            if not isinstance(day, dict):
                continue
            current_date = start + datetime.timedelta(days=index)
            day["date"] = current_date.isoformat()
            day["day_name"] = WEEKDAYS[current_date.weekday()]
        return aligned

    for index in range(7):
        day_key = f"day_{index + 1}"
        day = source.get(day_key)
        if not isinstance(day, dict):
            continue
        current_date = start + datetime.timedelta(days=index)
        day["date"] = current_date.isoformat()
        day["day_name"] = WEEKDAYS[current_date.weekday()]

    return aligned


def build_tracking_state_from_workout_plan(
    workout_plan: Dict[str, Any],
    difficulty_multiplier: str = "profile_based",
    max_days: int = 7,
    start_date: datetime.date | None = None,
) -> Dict[str, Any]:
    """Build the active_macrocycle shape consumed by dashboard/challenge routes."""
    start = start_date or datetime.date.today()
    aligned_plan = align_weekly_plan_dates(workout_plan, start)
    source = aligned_plan.get("weekly_plan") if isinstance(aligned_plan.get("weekly_plan"), dict) else aligned_plan
    schedule: List[Dict[str, Any]] = []

    for index in range(max_days):
        day_number = index + 1
        day_key = f"day_{day_number}"
        day = source.get(day_key, {}) if isinstance(source, dict) else {}
        if not isinstance(day, dict):
            day = {}

        raw_exercises = day.get("exercises", [])
        exercises = [_normalize_tracking_exercise(item) for item in raw_exercises if item]
        current_date = start + datetime.timedelta(days=index)
        focus = (
            day.get("focus")
            or day.get("focus_area")
            or day.get("target_muscle_split")
            or day.get("day_name")
            or WEEKDAYS[current_date.weekday()]
        )

        schedule.append({
            "day_number": day_number,
            "date": current_date.isoformat(),
            "day_name": WEEKDAYS[current_date.weekday()],
            "target_muscle_split": focus,
            "is_rest_day": len(exercises) == 0,
            "exercises": exercises,
            "daily_metric_challenge": _extract_challenge_text(day, exercises),
        })

    return {
        "current_active_day": 1,
        "completed_days": [],
        "max_block_days": max_days,
        "plan_metadata": {
            "user_fitness_archetype": "AI Coach Weekly Plan",
            "trainer_coaching_voice": "Professional Gym Companion",
            "current_difficulty_multiplier": difficulty_multiplier,
            "macrocycle_volume_target_kg": 0.0,
            "block_duration_days": max_days,
            "start_date": start.isoformat(),
            "end_date": (start + datetime.timedelta(days=max_days - 1)).isoformat(),
            "schedule": schedule,
        },
        "created_at": datetime.datetime.utcnow(),
        "is_fully_completed": False,
    }


def _normalize_tracking_exercise(exercise: Any) -> Dict[str, Any]:
    if isinstance(exercise, str):
        return {
            "exercise_name": exercise,
            "prescribed_sets": 1,
            "prescribed_reps": "As prescribed",
            "trainer_execution_note": "Use controlled form.",
        }

    if not isinstance(exercise, dict):
        return {
            "exercise_name": "Exercise",
            "prescribed_sets": 1,
            "prescribed_reps": "As prescribed",
            "trainer_execution_note": "Use controlled form.",
        }

    sets = exercise.get("sets") or exercise.get("prescribed_sets") or 1
    try:
        sets_value = int(str(sets).split()[0])
    except (TypeError, ValueError):
        sets_value = 1

    return {
        "exercise_name": str(exercise.get("exercise_name") or exercise.get("exercise") or exercise.get("name") or "Exercise"),
        "prescribed_sets": sets_value,
        "prescribed_reps": str(exercise.get("reps") or exercise.get("prescribed_reps") or exercise.get("sets_reps") or "As prescribed"),
        "trainer_execution_note": str(exercise.get("notes") or exercise.get("trainer_execution_note") or "Use controlled form."),
    }


def _extract_challenge_text(day: Dict[str, Any], exercises: List[Dict[str, Any]]) -> str:
    challenge = day.get("daily_metric_challenge") or day.get("challenge")
    if challenge:
        return str(challenge)
    if exercises:
        first = exercises[0]
        return f"Complete {first['exercise_name']} with controlled form."
    return "Active recovery and mobility."
