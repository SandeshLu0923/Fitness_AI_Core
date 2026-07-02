import datetime
from collections import defaultdict
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException

from app.database import (
    ai_inference_logs_col,
    api_metrics_col,
    exercise_logs_col,
    mood_logs_col,
    user_activity_logs_col,
    users_col,
)

router = APIRouter(prefix="/api/admin", tags=["Admin Analytics"])


def require_admin(authorization: str | None = Header(None)) -> dict:
    from app.routers.auth import verify_token

    payload = verify_token(authorization)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


def _utc_now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _start_of_day(days_ago: int = 0) -> datetime.datetime:
    today = _utc_now().date()
    return datetime.datetime.combine(today - datetime.timedelta(days=days_ago), datetime.time.min)


def _iso_day(value: datetime.datetime) -> str:
    return value.date().isoformat()


async def _count_distinct_users_since(days: int) -> int:
    since = _start_of_day(days - 1)
    users = await user_activity_logs_col.distinct("user_id", {"timestamp": {"$gte": since}})
    return len([user for user in users if user])


async def _count_docs_by_day(collection, date_field: str, days: int, extra_match: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    since = _start_of_day(days - 1)
    match = {date_field: {"$gte": since}}
    if extra_match:
        match.update(extra_match)
    cursor = collection.aggregate([
        {"$match": match},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": f"${date_field}"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ])
    rows = await cursor.to_list(length=days + 5)
    counts = {row["_id"]: row["count"] for row in rows}
    return [
        {"date": (_start_of_day(days - 1 - idx)).date().isoformat(), "count": counts.get((_start_of_day(days - 1 - idx)).date().isoformat(), 0)}
        for idx in range(days)
    ]


@router.get("/overview")
async def get_admin_overview(_admin: dict = Depends(require_admin)):
    """Return dashboard KPIs and chart-ready analytics."""
    now = _utc_now()
    last_24h = now - datetime.timedelta(hours=24)
    last_7d = now - datetime.timedelta(days=7)
    prev_7d_start = now - datetime.timedelta(days=14)

    daily_active = await _count_distinct_users_since(1)
    weekly_active = await _count_distinct_users_since(7)
    monthly_active = await _count_distinct_users_since(30)

    current_week_users = set(await user_activity_logs_col.distinct("user_id", {"timestamp": {"$gte": last_7d}}))
    previous_week_users = set(await user_activity_logs_col.distinct("user_id", {"timestamp": {"$gte": prev_7d_start, "$lt": last_7d}}))
    retained_users = len(current_week_users.intersection(previous_week_users))
    retention_rate = round((retained_users / max(len(previous_week_users), 1)) * 100, 1) if previous_week_users else 0.0

    inference_total = await ai_inference_logs_col.count_documents({"timestamp": {"$gte": last_7d}})
    inference_success = await ai_inference_logs_col.count_documents({"timestamp": {"$gte": last_7d}, "success": True})

    workout_rows = await exercise_logs_col.find({"completed_at": {"$gte": last_7d}}).to_list(length=5000)
    total_reps = sum(int(row.get("total_reps") or 0) for row in workout_rows)
    correct_reps = sum(int(row.get("correct_reps") or 0) for row in workout_rows)
    model_accuracy_rate = round((correct_reps / max(total_reps, 1)) * 100, 1) if workout_rows else 0.0
    if model_accuracy_rate == 0 and inference_total:
        model_accuracy_rate = round((inference_success / max(inference_total, 1)) * 100, 1)

    metric_rows = await api_metrics_col.find({"timestamp": {"$gte": last_24h}}).to_list(length=10000)
    avg_latency = round(sum(float(row.get("duration_ms") or 0) for row in metric_rows) / max(len(metric_rows), 1), 1)
    error_count = len([row for row in metric_rows if int(row.get("status_code") or 0) >= 400 or row.get("error")])
    error_rate = round((error_count / max(len(metric_rows), 1)) * 100, 1)

    hour_counts: Dict[int, int] = defaultdict(int)
    for row in workout_rows:
        completed_at = row.get("completed_at")
        if isinstance(completed_at, datetime.datetime):
            hour_counts[completed_at.hour] += 1
    peak_hour = max(hour_counts.items(), key=lambda item: item[1], default=(None, 0))

    feature_counts_cursor = ai_inference_logs_col.aggregate([
        {"$match": {"timestamp": {"$gte": last_7d}}},
        {"$group": {"_id": "$feature", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ])
    feature_distribution = [
        {"feature": row["_id"] or "unknown", "count": row["count"]}
        for row in await feature_counts_cursor.to_list(length=20)
    ]

    latency_points = [
        {
            "endpoint": row.get("path", "unknown"),
            "method": row.get("method", "GET"),
            "latency_ms": round(float(row.get("duration_ms") or 0), 1),
            "status_code": row.get("status_code"),
            "timestamp": row.get("timestamp").isoformat() if isinstance(row.get("timestamp"), datetime.datetime) else None,
        }
        for row in sorted(metric_rows, key=lambda item: item.get("timestamp") or datetime.datetime.min)[-200:]
    ]

    churn_buckets = await _behavioral_prediction_buckets(last_7d)
    server_load = _server_load_snapshot()

    return {
        "kpis": {
            "active_users": {
                "daily": daily_active,
                "weekly": weekly_active,
                "monthly": monthly_active,
            },
            "ai_inference_volume": inference_total,
            "model_accuracy_rate": model_accuracy_rate,
            "system_latency_ms": avg_latency,
            "user_retention_rate": retention_rate,
            "peak_activity_hour": f"{peak_hour[0]:02d}:00" if peak_hour[0] is not None else "N/A",
            "error_log_rate": error_rate,
        },
        "charts": {
            "user_growth": await _count_docs_by_day(users_col, "created_at", 14),
            "feature_distribution": feature_distribution,
            "server_load": server_load,
            "behavioral_predictions": churn_buckets,
            "api_response_times": latency_points,
        },
    }


async def _behavioral_prediction_buckets(since: datetime.datetime) -> List[Dict[str, Any]]:
    rows = await ai_inference_logs_col.find({
        "timestamp": {"$gte": since},
        "feature": {"$in": ["habit_skip_prediction", "habit_tracker", "chat_companion"]},
    }).to_list(length=5000)
    buckets = {"Low": 0, "Medium": 0, "High": 0}
    for row in rows:
        metadata = row.get("metadata") or {}
        risk = metadata.get("skip_probability")
        try:
            risk_value = float(risk)
        except (TypeError, ValueError):
            continue
        if risk_value >= 0.7:
            buckets["High"] += 1
        elif risk_value >= 0.35:
            buckets["Medium"] += 1
        else:
            buckets["Low"] += 1
    return [{"bucket": key, "count": value} for key, value in buckets.items()]


def _server_load_snapshot() -> List[Dict[str, Any]]:
    try:
        import psutil
        return [{
            "timestamp": _utc_now().isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
        }]
    except Exception:
        return [{
            "timestamp": _utc_now().isoformat(),
            "cpu_percent": 0,
            "memory_percent": 0,
        }]
