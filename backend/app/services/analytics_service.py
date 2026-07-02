import datetime
from typing import Any, Dict, Optional

from app.database import ai_inference_logs_col, mood_logs_col, user_activity_logs_col


class AnalyticsService:
    """Small persistence helper for product analytics and admin metrics."""

    @staticmethod
    async def log_ai_inference(
        feature: str,
        user_id: Optional[str] = None,
        success: bool = True,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            await ai_inference_logs_col.insert_one({
                "feature": feature,
                "user_id": user_id,
                "success": success,
                "latency_ms": round(float(latency_ms), 2) if latency_ms is not None else None,
                "metadata": metadata or {},
                "timestamp": datetime.datetime.utcnow(),
            })
        except Exception as exc:
            print(f"[ANALYTICS_WARNING] Failed to log AI inference: {exc}")

    @staticmethod
    async def log_user_activity(user_id: str, activity_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not user_id:
            return
        try:
            await user_activity_logs_col.insert_one({
                "user_id": user_id,
                "activity_type": activity_type,
                "metadata": metadata or {},
                "timestamp": datetime.datetime.utcnow(),
            })
        except Exception as exc:
            print(f"[ANALYTICS_WARNING] Failed to log user activity: {exc}")

    @staticmethod
    async def log_mood(user_id: str, mood: str, score: float, message: str = "") -> None:
        if not user_id:
            return
        try:
            await mood_logs_col.insert_one({
                "user_id": user_id,
                "mood": mood,
                "score": round(float(score), 2),
                "message_excerpt": message[:240],
                "timestamp": datetime.datetime.utcnow(),
            })
        except Exception as exc:
            print(f"[ANALYTICS_WARNING] Failed to log mood: {exc}")

