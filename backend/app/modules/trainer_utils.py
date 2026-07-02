import datetime
import numpy as np
from pydantic import BaseModel, Field
from typing import List

def get_exercise_logs_col():
    """Get exercise logs collection (lazy loaded)."""
    from app.database import exercise_logs_col
    return exercise_logs_col

def calculate_angle(a, b, c):
    """Calculates the clean 2D joint angle formed by three landmarks with b as the vertex."""
    try:
        ba = np.array(a) - np.array(b)
        bc = np.array(c) - np.array(b)
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
        return float(np.degrees(angle))
    except (TypeError, ValueError, ZeroDivisionError):
        return 180.0

# ==========================================================================
# GAMIFIED LEVEL CALCULATOR MATRIX (5 COMPLETIONS = 1 MILESTONE LEVEL)
# ==========================================================================
def calculate_user_fitness_level(completed_count: int) -> str:
    """
    Every 5 daily challenge completions advances 1 milestone level sub-tier.
    Every 25 completions advances the overarching athlete rank class.
    """
    milestone_level = (completed_count // 5) % 5 + 1  # Loops 1x to 5x
    
    if completed_count < 25:
        return f"Beginner {milestone_level}x Level"
    elif completed_count < 50:
        return f"Intermediate {milestone_level}x Level"
    elif completed_count < 75:
        return f"Advanced Trainee {milestone_level}x Level"
    else:
        return f"Elite Athlete {milestone_level}x Level"

# ==========================================================================
# DYNAMIC PERIODIZED SYSTEM DATA CONTRACTS
# ==========================================================================
class ExercisePlanItem(BaseModel):
    exercise_name: str
    prescribed_sets: int
    prescribed_reps: str
    trainer_execution_note: str

class DailyPlanBlock(BaseModel):
    day_number: int = Field(..., description="Day index of the current cycle, e.g., 1, 2, 3, etc.")
    target_muscle_split: str = Field(..., description="Target muscle group focus or recovery day assignment.")
    is_rest_day: bool = Field(..., description="Flag indicating if this day is strictly for recovery.")
    exercises: List[ExercisePlanItem] = Field(..., description="List of exercises. Must be empty [] if is_rest_day is true.")
    daily_metric_challenge: str = Field(..., description="Hard physical metric challenge linked to this day's tier workload.")

class WeeklyMacrocyclePlan(BaseModel):
    user_fitness_archetype: str
    trainer_coaching_voice: str
    current_difficulty_multiplier: str
    macrocycle_volume_target_kg: float = Field(..., description="Target cumulative weight volume for the entire block.")
    block_duration_days: int = Field(..., description="Total calendar duration length in days of this macrocycle block plan.")
    schedule: List[DailyPlanBlock] = Field(..., description="Sequential daily tracking blocks matching the duration length exactly.")

# ==========================================================================
# METRIC TELEMETRY ENGINE AGGREGATORS
# ==========================================================================
async def calculate_macrocycle_history_metrics(user_id: str):
    exercise_logs_col = get_exercise_logs_col()
    cursor = exercise_logs_col.find({"user_id": user_id}).sort("timestamp", -1).limit(5)
    history = await cursor.to_list(length=5)
    hours_elapsed = 48.0
    volume_delta = 0.0

    if history and len(history) > 0:
        history.sort(key=lambda x: x["timestamp"])
        hours_elapsed = float((datetime.datetime.utcnow() - history[-1]["timestamp"]).total_seconds() / 3600.0)
        
        latest_vol = sum(
            ex.get("sets_completed", 0) * ex.get("total_weight_kg", 0.0) 
            for ex in history[-1].get("exercises", []) if isinstance(history[-1].get("exercises"), list)
        )
        
        if len(history) >= 2:
            baseline_vol = sum(
                ex.get("sets_completed", 0) * ex.get("total_weight_kg", 0.0) 
                for ex in history[0].get("exercises", []) if isinstance(history[0].get("exercises"), list)
            )
            volume_delta = float(latest_vol - baseline_vol)
            
    return hours_elapsed, volume_delta
