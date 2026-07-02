"""
Deterministic weekly and monthly workout summaries.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.database import exercise_logs_col, users_col, weekly_summaries_col, monthly_summaries_col


class WorkoutSummaryService:
    """Builds compact report data for UI and chat context."""

    async def get_weekly_summary(
        self,
        user_id: str,
        start_date: Optional[datetime.date] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        today = datetime.date.today()
        week_start = start_date or (today - datetime.timedelta(days=today.weekday()))
        week_end = week_start + datetime.timedelta(days=6)
        workouts = await self._fetch_workouts(user_id, week_start, week_end)
        user = await users_col.find_one({"user_id": user_id}) or {}
        active_macrocycle = user.get("active_macrocycle") if isinstance(user, dict) else {}
        summary = self._build_weekly_payload(user_id, week_start, week_end, workouts, active_macrocycle)

        if persist:
            await weekly_summaries_col.update_one(
                {"user_id": user_id, "week_start": summary["week_start"]},
                {"$set": summary},
                upsert=True,
            )

        return summary

    async def get_monthly_summary(
        self,
        user_id: str,
        month_date: Optional[datetime.date] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        anchor = month_date or datetime.date.today()
        month_start = datetime.date(anchor.year, anchor.month, 1)
        if anchor.month == 12:
            next_month = datetime.date(anchor.year + 1, 1, 1)
        else:
            next_month = datetime.date(anchor.year, anchor.month + 1, 1)
        month_end = next_month - datetime.timedelta(days=1)
        today = datetime.date.today()
        if anchor.year == today.year and anchor.month == today.month:
            month_end = min(month_end, today)

        workouts = await self._fetch_workouts(user_id, month_start, month_end)
        summary = self._build_monthly_payload(user_id, month_start, month_end, workouts)

        if persist:
            await monthly_summaries_col.update_one(
                {"user_id": user_id, "month": summary["month"]},
                {"$set": summary},
                upsert=True,
            )

        return summary

    async def get_latest_compact_context(self, user_id: str) -> Dict[str, Any]:
        weekly = await weekly_summaries_col.find_one({"user_id": user_id}, sort=[("week_start", -1)])
        monthly = await monthly_summaries_col.find_one({"user_id": user_id}, sort=[("month", -1)])

        if not weekly:
            weekly = await self.get_weekly_summary(user_id, persist=True)
        if not monthly:
            monthly = await self.get_monthly_summary(user_id, persist=True)

        return {
            "latest_weekly_summary": self._compact_weekly(weekly or {}),
            "latest_monthly_summary": self._compact_monthly(monthly or {}),
        }

    async def _fetch_workouts(
        self,
        user_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> List[Dict[str, Any]]:
        return await exercise_logs_col.find({
            "user_id": user_id,
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat(),
            }
        }).to_list(length=3000)

    def _build_weekly_payload(
        self,
        user_id: str,
        week_start: datetime.date,
        week_end: datetime.date,
        workouts: List[Dict[str, Any]],
        active_macrocycle: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        days_active, daily_stats, exercise_totals = self._aggregate_workouts(workouts)
        planned_days = self._planned_days(active_macrocycle, default=7)
        completed_days = self._completed_days(active_macrocycle)
        active_day_count = sum(1 for value in days_active.values() if value)
        completed_count = len(completed_days) if completed_days else active_day_count
        completion_rate = min(round((completed_count / max(planned_days, 1)) * 100, 1), 100.0)
        skipped_days = max(planned_days - completed_count, 0)
        top_exercises = self._top_exercises(exercise_totals)

        return {
            "user_id": user_id,
            "period": "weekly",
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "planned_workout_days": planned_days,
            "completed_workout_days": completed_count,
            "skipped_days": skipped_days,
            "completion_percentage": completion_rate,
            "days_active": days_active,
            "daily_stats": sorted(daily_stats.values(), key=lambda item: item["date"]),
            "exercise_totals": list(exercise_totals.values()),
            "exercises": top_exercises,
            "total_workouts": len(workouts),
            "total_reps": sum(item.get("total_reps", 0) for item in exercise_totals.values()),
            "total_sets": sum(item.get("sets", 0) for item in exercise_totals.values()),
            "trend": self._weekly_trend(completion_rate),
            "report_notes": self._weekly_notes(completion_rate, skipped_days, top_exercises),
            "updated_at": datetime.datetime.utcnow(),
        }

    def _build_monthly_payload(
        self,
        user_id: str,
        month_start: datetime.date,
        month_end: datetime.date,
        workouts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        days_active, daily_stats, exercise_totals = self._aggregate_workouts(workouts)
        active_days = sum(1 for value in days_active.values() if value)
        days_elapsed = (month_end - month_start).days + 1
        completion_percentage = round((active_days / max(days_elapsed, 1)) * 100, 1)
        top_exercises = self._top_exercises(exercise_totals)
        week_buckets = self._monthly_week_buckets(month_start, month_end, days_active)
        best_week = max(week_buckets, key=lambda item: item["active_days"], default=None)

        return {
            "user_id": user_id,
            "period": "monthly",
            "month": f"{month_start.year}-{month_start.month:02d}",
            "month_start": month_start.isoformat(),
            "month_end": month_end.isoformat(),
            "days_elapsed": days_elapsed,
            "active_days": active_days,
            "completion_percentage": completion_percentage,
            "days_active": days_active,
            "daily_stats": sorted(daily_stats.values(), key=lambda item: item["date"]),
            "exercise_totals": list(exercise_totals.values()),
            "exercises": top_exercises,
            "total_workouts": len(workouts),
            "total_reps": sum(item.get("total_reps", 0) for item in exercise_totals.values()),
            "total_sets": sum(item.get("sets", 0) for item in exercise_totals.values()),
            "week_buckets": week_buckets,
            "best_week": best_week,
            "trend": self._monthly_trend(week_buckets),
            "report_notes": self._monthly_notes(completion_percentage, best_week, top_exercises),
            "updated_at": datetime.datetime.utcnow(),
        }

    def _aggregate_workouts(self, workouts: List[Dict[str, Any]]) -> tuple[Dict[str, bool], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        days_active: Dict[str, bool] = {}
        daily_stats: Dict[str, Dict[str, Any]] = {}
        exercise_totals: Dict[str, Dict[str, Any]] = {}

        for workout in workouts:
            date_key = str(workout.get("date") or "")
            if not date_key:
                continue
            exercise_name = str(workout.get("exercise_name") or "Unknown")
            correct = int(workout.get("correct_reps") or 0)
            incorrect = int(workout.get("incorrect_reps") or 0)
            reps = correct + incorrect
            sets = int(workout.get("sets_completed") or 0)

            days_active[date_key] = True
            daily = daily_stats.setdefault(date_key, {
                "date": date_key,
                "total_reps": 0,
                "total_sets": 0,
                "exercises": 0,
            })
            daily["total_reps"] += reps
            daily["total_sets"] += sets
            daily["exercises"] += 1

            exercise = exercise_totals.setdefault(exercise_name, {
                "exercise": exercise_name,
                "name": exercise_name,
                "total_reps": 0,
                "correct_reps": 0,
                "incorrect_reps": 0,
                "sets": 0,
                "count": 0,
            })
            exercise["total_reps"] += reps
            exercise["correct_reps"] += correct
            exercise["incorrect_reps"] += incorrect
            exercise["sets"] += sets
            exercise["count"] += 1

        return days_active, daily_stats, exercise_totals

    def _planned_days(self, active_macrocycle: Optional[Dict[str, Any]], default: int) -> int:
        if not isinstance(active_macrocycle, dict):
            return default
        schedule = active_macrocycle.get("plan_metadata", {}).get("schedule", [])
        if isinstance(schedule, list) and schedule:
            workout_days = [day for day in schedule if isinstance(day, dict) and not day.get("is_rest_day", False)]
            return len(workout_days) or len(schedule)
        return int(active_macrocycle.get("max_block_days") or default)

    def _completed_days(self, active_macrocycle: Optional[Dict[str, Any]]) -> List[int]:
        if not isinstance(active_macrocycle, dict):
            return []
        completed = []
        for day in active_macrocycle.get("completed_days", []):
            try:
                completed.append(int(day))
            except (TypeError, ValueError):
                continue
        return sorted(set(completed))

    def _top_exercises(self, exercise_totals: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            exercise_totals.values(),
            key=lambda item: item.get("total_reps", 0),
            reverse=True,
        )[:5]

    def _monthly_week_buckets(
        self,
        month_start: datetime.date,
        month_end: datetime.date,
        days_active: Dict[str, bool],
    ) -> List[Dict[str, Any]]:
        buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"active_days": 0, "total_days": 0})
        current = month_start
        while current <= month_end:
            week_start = current - datetime.timedelta(days=current.weekday())
            key = week_start.isoformat()
            buckets[key]["week_start"] = key
            buckets[key]["active_days"] += 1 if days_active.get(current.isoformat()) else 0
            buckets[key]["total_days"] += 1
            current += datetime.timedelta(days=1)

        return [
            {
                **value,
                "completion_percentage": round((value["active_days"] / max(value["total_days"], 1)) * 100, 1),
            }
            for _, value in sorted(buckets.items())
        ]

    def _weekly_trend(self, completion_rate: float) -> str:
        if completion_rate >= 80:
            return "strong"
        if completion_rate >= 50:
            return "steady"
        return "needs_attention"

    def _monthly_trend(self, week_buckets: List[Dict[str, Any]]) -> str:
        if len(week_buckets) < 2:
            return "stable"
        first = week_buckets[0].get("completion_percentage", 0)
        latest = week_buckets[-1].get("completion_percentage", 0)
        if latest > first + 10:
            return "improving"
        if latest < first - 10:
            return "dropping"
        return "stable"

    def _weekly_notes(self, completion_rate: float, skipped_days: int, top_exercises: List[Dict[str, Any]]) -> List[str]:
        notes = []
        if completion_rate >= 80:
            notes.append("Strong weekly consistency.")
        elif completion_rate >= 50:
            notes.append("Moderate consistency; keep the next sessions short and realistic.")
        else:
            notes.append("Low weekly consistency; reduce friction and protect the next workout slot.")
        if skipped_days:
            notes.append(f"{skipped_days} planned day(s) still need attention.")
        if top_exercises:
            notes.append(f"Highest volume exercise: {top_exercises[0].get('name')}.")
        return notes

    def _monthly_notes(
        self,
        completion_percentage: float,
        best_week: Optional[Dict[str, Any]],
        top_exercises: List[Dict[str, Any]],
    ) -> List[str]:
        notes = [f"Monthly activity rate is {completion_percentage}%."]
        if best_week:
            notes.append(f"Best week started {best_week.get('week_start')} with {best_week.get('active_days')} active day(s).")
        if top_exercises:
            notes.append(f"Most repeated exercise this month: {top_exercises[0].get('name')}.")
        return notes

    def _compact_weekly(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "week_start": summary.get("week_start"),
            "week_end": summary.get("week_end"),
            "planned_workout_days": summary.get("planned_workout_days"),
            "completed_workout_days": summary.get("completed_workout_days"),
            "skipped_days": summary.get("skipped_days"),
            "completion_percentage": summary.get("completion_percentage"),
            "trend": summary.get("trend"),
            "top_exercises": [
                {"name": item.get("name"), "total_reps": item.get("total_reps")}
                for item in summary.get("exercises", [])[:3]
            ],
            "notes": summary.get("report_notes", [])[:3],
        }

    def _compact_monthly(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "month": summary.get("month"),
            "active_days": summary.get("active_days"),
            "completion_percentage": summary.get("completion_percentage"),
            "trend": summary.get("trend"),
            "best_week": summary.get("best_week"),
            "top_exercises": [
                {"name": item.get("name"), "total_reps": item.get("total_reps")}
                for item in summary.get("exercises", [])[:3]
            ],
            "notes": summary.get("report_notes", [])[:3],
        }
