"""
Performance Analyzer Service
Scores workout performance using motion efficiency analysis
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
import json
from statistics import mean, stdev


class PerformanceMetrics(BaseModel):
    """Metrics for a single workout"""
    user_id: str
    exercise_type: str
    session_id: str
    date: datetime
    reps_completed: int
    reps_correct: int
    accuracy: float  # 0-100
    avg_tempo: float  # reps per minute
    tempo_consistency: float  # 0-100 (std dev based)
    avg_rom: float  # average range of motion 0-100
    posture_quality: float  # 0-100
    recovery_efficiency: float  # 0-100
    performance_score: float  # 0-100 (weighted average)


class WeeklyReport(BaseModel):
    """Weekly performance summary"""
    user_id: str
    week_start: datetime
    week_end: datetime
    total_workouts: int
    avg_performance_score: float
    best_exercise: str
    worst_exercise: str
    weekly_trend: str  # "improving", "stable", "declining"
    recommendations: List[str]
    exercises_data: Dict[str, Dict]


class PerformanceAnalyzerService:
    def __init__(self, db: AsyncIOMotorClient):
        self.db = db
        self.perf_collection = db.gym_assistant.performance_metrics
        self.report_collection = db.gym_assistant.weekly_reports
        self.exercise_baselines = {
            "squat": {"target_tempo": 1.0, "target_rom": 90, "target_posture": 95},
            "pushup": {"target_tempo": 0.8, "target_rom": 85, "target_posture": 90},
            "jumping-jacks": {"target_tempo": 2.0, "target_rom": 100, "target_posture": 85},
            "pullup": {"target_tempo": 0.6, "target_rom": 100, "target_posture": 95},
            "situp": {"target_tempo": 1.2, "target_rom": 80, "target_posture": 85},
        }

    async def calculate_performance_score(
        self,
        user_id: str,
        exercise_type: str,
        reps_completed: int,
        reps_correct: int,
        landmarks_history: List[Dict],
        session_data: Dict,
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance score
        """
        # Calculate individual metrics
        accuracy = (reps_correct / reps_completed * 100) if reps_completed > 0 else 0
        
        # Tempo analysis (reps per minute)
        session_duration = session_data.get("duration_seconds", 60)
        avg_tempo = (reps_completed / (session_duration / 60)) if session_duration > 0 else 0
        
        # Tempo consistency (lower std dev = more consistent)
        tempo_consistency = self._calculate_tempo_consistency(landmarks_history)
        
        # Range of motion analysis
        avg_rom = self._calculate_rom(landmarks_history, exercise_type)
        
        # Posture quality (based on landmark visibility and alignment)
        posture_quality = self._calculate_posture_quality(landmarks_history, exercise_type)
        
        # Recovery efficiency (rest time vs workout intensity)
        recovery_efficiency = self._calculate_recovery_efficiency(session_data)
        
        # Weighted performance score
        weights = {
            "accuracy": 0.30,
            "tempo": 0.15,
            "tempo_consistency": 0.15,
            "rom": 0.15,
            "posture": 0.15,
            "recovery": 0.10,
        }
        
        performance_score = (
            (accuracy / 100) * weights["accuracy"] * 100
            + (min(avg_tempo / self.exercise_baselines.get(exercise_type, {}).get("target_tempo", 1), 1.0))
            * weights["tempo"] * 100
            + (tempo_consistency / 100) * weights["tempo_consistency"] * 100
            + (avg_rom / 100) * weights["rom"] * 100
            + (posture_quality / 100) * weights["posture"] * 100
            + (recovery_efficiency / 100) * weights["recovery"] * 100
        )
        
        metrics = PerformanceMetrics(
            user_id=user_id,
            exercise_type=exercise_type,
            session_id=session_data.get("session_id", ""),
            date=datetime.utcnow(),
            reps_completed=reps_completed,
            reps_correct=reps_correct,
            accuracy=round(accuracy, 2),
            avg_tempo=round(avg_tempo, 2),
            tempo_consistency=round(tempo_consistency, 2),
            avg_rom=round(avg_rom, 2),
            posture_quality=round(posture_quality, 2),
            recovery_efficiency=round(recovery_efficiency, 2),
            performance_score=round(performance_score, 2),
        )
        
        # Store in database
        await self.perf_collection.insert_one(metrics.dict())
        
        return metrics

    def _calculate_tempo_consistency(self, landmarks_history: List[Dict]) -> float:
        """
        Calculate how consistent the rep tempo is (lower variance = better)
        Range: 0-100 (100 = perfect consistency)
        """
        if len(landmarks_history) < 2:
            return 100.0
        
        # Calculate time between rep peaks
        intervals = []
        for i in range(1, len(landmarks_history)):
            if landmarks_history[i].get("rep_completed"):
                intervals.append(
                    landmarks_history[i]["timestamp"] - landmarks_history[i - 1]["timestamp"]
                )
        
        if not intervals or len(intervals) < 2:
            return 100.0
        
        # Lower std dev = higher consistency
        avg_interval = mean(intervals)
        interval_stdev = stdev(intervals) if len(intervals) > 1 else 0
        
        # Convert to 0-100 scale (target: <5% variance)
        consistency = max(0, 100 - (interval_stdev / avg_interval * 100)) if avg_interval > 0 else 100
        return min(100, consistency)

    def _calculate_rom(self, landmarks_history: List[Dict], exercise_type: str) -> float:
        """
        Calculate average range of motion
        Range: 0-100 (100 = full ROM)
        """
        if not landmarks_history:
            return 0.0
        
        max_angles = []
        min_angles = []
        
        for landmark in landmarks_history:
            angle = landmark.get("current_angle", 0)
            max_angles.append(angle)
            min_angles.append(angle)
        
        if not max_angles:
            return 0.0
        
        max_angle = max(max_angles)
        min_angle = min(min_angles)
        angle_range = max_angle - min_angle
        
        # Baseline ranges by exercise
        baselines = {
            "squat": 60,  # 90° down to 150° up
            "pushup": 80,  # 100° down to 180° up
            "jumping-jacks": 100,
            "pullup": 100,
            "situp": 90,
        }
        
        target_range = baselines.get(exercise_type, 90)
        rom_percentage = min(100, (angle_range / target_range) * 100)
        
        return round(rom_percentage, 2)

    def _calculate_posture_quality(
        self, landmarks_history: List[Dict], exercise_type: str
    ) -> float:
        """
        Calculate posture quality based on landmark visibility and alignment
        Range: 0-100
        """
        if not landmarks_history:
            return 0.0
        
        visibility_scores = []
        alignment_scores = []
        
        for landmark in landmarks_history:
            # Average visibility of key joints (should be >0.7)
            visibility = landmark.get("visibility", 0.5)
            visibility_scores.append(min(100, visibility * 100))
            
            # Alignment score (how well joints are aligned)
            alignment = landmark.get("alignment_score", 0.8)
            alignment_scores.append(min(100, alignment * 100))
        
        if not visibility_scores:
            return 0.0
        
        avg_visibility = mean(visibility_scores)
        avg_alignment = mean(alignment_scores) if alignment_scores else 50
        
        # Weighted average
        posture_score = (avg_visibility * 0.6 + avg_alignment * 0.4)
        return round(posture_score, 2)

    def _calculate_recovery_efficiency(self, session_data: Dict) -> float:
        """
        Calculate recovery efficiency
        Range: 0-100 (100 = optimal recovery)
        """
        # Ideal recovery: proportional rest to intensity
        intensity = session_data.get("intensity_level", 5)  # 1-10
        reps_completed = session_data.get("reps_completed", 0)
        rest_time = session_data.get("rest_seconds", 0)
        
        # Expected rest (30 sec per 10 reps at medium intensity)
        expected_rest = (reps_completed / 10) * 30 * (intensity / 5)
        
        if expected_rest == 0:
            return 100.0
        
        # Calculate efficiency (penalize both too much and too little rest)
        rest_ratio = rest_time / expected_rest
        if 0.8 <= rest_ratio <= 1.2:
            efficiency = 100.0
        else:
            efficiency = max(0, 100 - (abs(rest_ratio - 1.0) * 50))
        
        return round(efficiency, 2)

    async def generate_weekly_report(self, user_id: str) -> WeeklyReport:
        """
        Generate weekly performance report
        """
        # Get last 7 days of data
        week_start = datetime.utcnow() - timedelta(days=7)
        week_end = datetime.utcnow()
        
        metrics_list = await self.perf_collection.find(
            {
                "user_id": user_id,
                "date": {"$gte": week_start, "$lte": week_end},
            }
        ).to_list(None)
        
        if not metrics_list:
            return WeeklyReport(
                user_id=user_id,
                week_start=week_start,
                week_end=week_end,
                total_workouts=0,
                avg_performance_score=0,
                best_exercise="",
                worst_exercise="",
                weekly_trend="stable",
                recommendations=["Start your first workout to get personalized recommendations!"],
                exercises_data={},
            )
        
        # Analyze by exercise
        exercises_data = {}
        all_scores = []
        
        for metric in metrics_list:
            exercise = metric["exercise_type"]
            score = metric["performance_score"]
            all_scores.append(score)
            
            if exercise not in exercises_data:
                exercises_data[exercise] = {
                    "count": 0,
                    "avg_score": 0,
                    "avg_accuracy": 0,
                    "total_reps": 0,
                }
            
            exercises_data[exercise]["count"] += 1
            exercises_data[exercise]["total_reps"] += metric["reps_completed"]
            exercises_data[exercise]["avg_score"] = round(
                (exercises_data[exercise]["avg_score"] * (exercises_data[exercise]["count"] - 1) + score)
                / exercises_data[exercise]["count"],
                2,
            )
            exercises_data[exercise]["avg_accuracy"] = round(
                (exercises_data[exercise]["avg_accuracy"] * (exercises_data[exercise]["count"] - 1)
                 + metric["accuracy"])
                / exercises_data[exercise]["count"],
                2,
            )
        
        # Determine best and worst
        best_exercise = max(exercises_data.items(), key=lambda x: x[1]["avg_score"])[0]
        worst_exercise = min(exercises_data.items(), key=lambda x: x[1]["avg_score"])[0]
        
        # Determine trend
        if len(all_scores) >= 2:
            trend = "improving" if all_scores[-1] > all_scores[0] else (
                "declining" if all_scores[-1] < all_scores[0] else "stable"
            )
        else:
            trend = "stable"
        
        # Generate recommendations
        recommendations = self._generate_recommendations(exercises_data, trend)
        
        report = WeeklyReport(
            user_id=user_id,
            week_start=week_start,
            week_end=week_end,
            total_workouts=len(metrics_list),
            avg_performance_score=round(mean(all_scores), 2),
            best_exercise=best_exercise,
            worst_exercise=worst_exercise,
            weekly_trend=trend,
            recommendations=recommendations,
            exercises_data=exercises_data,
        )
        
        # Store report
        await self.report_collection.insert_one(report.dict())
        
        return report

    def _generate_recommendations(self, exercises_data: Dict, trend: str) -> List[str]:
        """
        Generate personalized recommendations based on data
        """
        recommendations = []
        
        if trend == "declining":
            recommendations.append("📉 Your performance is declining. Try taking a rest day or reducing intensity.")
        elif trend == "improving":
            recommendations.append("📈 Great progress! Keep up the momentum and gradually increase intensity.")
        
        for exercise, data in exercises_data.items():
            if data["avg_score"] < 60:
                recommendations.append(
                    f"⚠️ {exercise.capitalize()}: Focus on form quality. Your accuracy is {data['avg_accuracy']:.1f}%."
                )
            elif data["avg_score"] > 85:
                recommendations.append(f"🎯 {exercise.capitalize()}: Excellent form! Consider increasing reps.")
        
        if not recommendations:
            recommendations.append("💪 Keep maintaining your current performance level!")
        
        return recommendations[:5]  # Limit to 5 recommendations

    async def get_performance_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get recent performance metrics"""
        metrics = await self.perf_collection.find(
            {"user_id": user_id}
        ).sort("date", -1).limit(limit).to_list(limit)
        
        return metrics

    async def get_exercise_comparison(self, user_id: str) -> Dict:
        """Compare performance across exercises"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": "$exercise_type",
                    "avg_score": {"$avg": "$performance_score"},
                    "total_workouts": {"$sum": 1},
                    "avg_accuracy": {"$avg": "$accuracy"},
                }
            },
            {"$sort": {"avg_score": -1}},
        ]
        
        comparison = await self.perf_collection.aggregate(pipeline).to_list(None)
        return {exercise["_id"]: exercise for exercise in comparison}
