"""
Performance Analytics Router
Endpoints for workout performance analysis and weekly reports
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from typing import Optional
from ..services.performance_analyzer_service import PerformanceAnalyzerService
from ..database import get_db
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/api/performance", tags=["performance"])


def get_performance_service(db: AsyncIOMotorClient = Depends(get_db)):
    return PerformanceAnalyzerService(db)


@router.post("/score")
async def record_performance_score(
    user_id: str,
    exercise_type: str,
    reps_completed: int,
    reps_correct: int,
    session_data: dict,
    landmarks_history: list = None,
    service: PerformanceAnalyzerService = Depends(get_performance_service),
):
    """Record workout performance and calculate score"""
    start_time = datetime.utcnow()
    if landmarks_history is None:
        landmarks_history = []
    
    metrics = await service.calculate_performance_score(
        user_id=user_id,
        exercise_type=exercise_type,
        reps_completed=reps_completed,
        reps_correct=reps_correct,
        landmarks_history=landmarks_history,
        session_data=session_data,
    )
    try:
        from app.services.analytics_service import AnalyticsService
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        await AnalyticsService.log_ai_inference(
            "performance_scoring",
            user_id=user_id,
            success=True,
            latency_ms=latency_ms,
            metadata={
                "exercise_type": exercise_type,
                "performance_score": metrics.performance_score,
                "accuracy": metrics.accuracy,
            }
        )
    except Exception as analytics_error:
        print(f"[ANALYTICS_WARNING] Performance scoring not logged: {analytics_error}")
    
    return {
        "success": True,
        "performance_score": metrics.performance_score,
        "accuracy": metrics.accuracy,
        "tempo": metrics.avg_tempo,
        "rom": metrics.avg_rom,
        "posture": metrics.posture_quality,
        "recovery": metrics.recovery_efficiency,
    }


@router.get("/weekly-report/{user_id}")
async def get_weekly_report(
    user_id: str,
    service: PerformanceAnalyzerService = Depends(get_performance_service),
):
    """Get weekly performance report"""
    report = await service.generate_weekly_report(user_id)
    
    return {
        "success": True,
        "week_start": report.week_start,
        "week_end": report.week_end,
        "total_workouts": report.total_workouts,
        "avg_performance_score": report.avg_performance_score,
        "best_exercise": report.best_exercise,
        "worst_exercise": report.worst_exercise,
        "weekly_trend": report.weekly_trend,
        "recommendations": report.recommendations,
        "exercises_data": report.exercises_data,
    }


@router.get("/history/{user_id}")
async def get_performance_history(
    user_id: str,
    limit: int = 20,
    service: PerformanceAnalyzerService = Depends(get_performance_service),
):
    """Get recent performance metrics"""
    metrics = await service.get_performance_history(user_id, limit)
    
    return {
        "success": True,
        "count": len(metrics),
        "metrics": [
            {
                "exercise_type": m["exercise_type"],
                "performance_score": m["performance_score"],
                "accuracy": m["accuracy"],
                "date": m["date"].isoformat(),
                "reps_completed": m["reps_completed"],
            }
            for m in metrics
        ],
    }


@router.get("/comparison/{user_id}")
async def get_exercise_comparison(
    user_id: str,
    service: PerformanceAnalyzerService = Depends(get_performance_service),
):
    """Compare performance across different exercises"""
    comparison = await service.get_exercise_comparison(user_id)
    
    return {
        "success": True,
        "exercises": [
            {
                "exercise": name,
                "avg_score": data["avg_score"],
                "total_workouts": data["total_workouts"],
                "avg_accuracy": data["avg_accuracy"],
            }
            for name, data in comparison.items()
        ],
    }


@router.get("/insights/{user_id}")
async def get_performance_insights(
    user_id: str,
    service: PerformanceAnalyzerService = Depends(get_performance_service),
):
    """Get AI-generated performance insights"""
    # Get last 30 days of data
    metrics = await service.get_performance_history(user_id, limit=100)
    
    if not metrics:
        return {
            "success": True,
            "insights": ["Start your first workout to get personalized insights!"],
            "strength_areas": [],
            "improvement_areas": [],
        }
    
    # Analyze patterns
    exercise_scores = {}
    for m in metrics:
        exercise = m["exercise_type"]
        if exercise not in exercise_scores:
            exercise_scores[exercise] = []
        exercise_scores[exercise].append(m["performance_score"])
    
    # Identify strengths and weaknesses
    strength_areas = []
    improvement_areas = []
    
    for exercise, scores in exercise_scores.items():
        avg_score = sum(scores) / len(scores)
        if avg_score >= 85:
            strength_areas.append(f"{exercise}: {avg_score:.1f}/100")
        elif avg_score < 70:
            improvement_areas.append(f"{exercise}: {avg_score:.1f}/100")
    
    insights = []
    if strength_areas:
        insights.append(f"💪 Your strongest exercises: {', '.join(strength_areas)}")
    if improvement_areas:
        insights.append(f"🎯 Focus on improving: {', '.join(improvement_areas)}")
    
    total_reps = sum(m["reps_completed"] for m in metrics)
    insights.append(f"📊 Total reps this month: {total_reps}")
    
    return {
        "success": True,
        "insights": insights,
        "strength_areas": strength_areas,
        "improvement_areas": improvement_areas,
        "total_metrics_analyzed": len(metrics),
    }
