"""
Service: Habit Tracker Calculator
Handles biometric calculations and user fitness level determination.
"""

from typing import Tuple
from app.modules.trainer_utils import calculate_macrocycle_history_metrics, calculate_user_fitness_level
from app.modules.trainer_engine import run_mifflin_st_jeor_calories, run_haskell_fox_max_hr, predict_skip_probability
from app.database import completed_challenges_col

DEFAULT_MACROCYCLE_DAYS = 7


class HabitTrackerCalculator:
    """Handles biometric calculations for habit tracking."""

    async def calculate_user_biometrics(self, user_id: str, profile: dict) -> dict:
        """
        Calculate all biometric metrics for a user.
        
        Args:
            user_id: The user's ID
            profile: User profile dict with age, height, weight, fitness_goal
            
        Returns:
            Dict with all calculated metrics
        """
        user_id = user_id.strip()
        
        # Extract profile data
        goal_str = profile.get("fitness_goal", "General Fitness")
        age = int(profile.get("age", 25))
        weight = float(profile.get("weight_kg", 70.0))
        height = float(profile.get("height_cm", 175.0))

        # Calculate fitness metrics
        goal_encoded = self._encode_goal(goal_str)
        target_max_hr = run_haskell_fox_max_hr(age)
        predicted_maintenance_calories = run_mifflin_st_jeor_calories(weight, height, age)
        bmi = round(weight / ((height / 100.0) ** 2), 1) if height > 0 else 22.0

        # Get history metrics
        hours_elapsed, volume_delta = await calculate_macrocycle_history_metrics(user_id)
        skip_probability = predict_skip_probability(
            bmi, target_max_hr, predicted_maintenance_calories,
            hours_elapsed, volume_delta, goal_encoded
        )
        try:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference(
                "habit_skip_prediction",
                user_id=user_id,
                success=True,
                metadata={"skip_probability": skip_probability}
            )
        except Exception as analytics_error:
            print(f"[ANALYTICS_WARNING] Habit prediction not logged: {analytics_error}")

        # Get current tier level
        completed_count = await completed_challenges_col.count_documents({"user_id": user_id})
        current_tier_level = calculate_user_fitness_level(completed_count)

        return {
            "goal_str": goal_str,
            "goal_encoded": goal_encoded,
            "age": age,
            "height": height,
            "weight": weight,
            "bmi": bmi,
            "target_max_hr": target_max_hr,
            "predicted_maintenance_calories": predicted_maintenance_calories,
            "hours_elapsed": hours_elapsed,
            "volume_delta": volume_delta,
            "skip_probability": skip_probability,
            "current_tier_level": current_tier_level,
            "completed_count": completed_count
        }

    def _encode_goal(self, goal_str: str) -> float:
        """Encode fitness goal to numeric value."""
        if "gain" in goal_str.lower() or "build" in goal_str.lower():
            return 1.0
        elif "loss" in goal_str.lower() or "cut" in goal_str.lower():
            return 0.0
        else:
            return 2.0

    def build_generation_prompt(self, biometrics: dict) -> str:
        """Build the macrocycle generation prompt."""
        return (
            f"Generate a synchronized periodized training macrocycle block for a professional fitness plan.\n"
            f"User Goal: {biometrics['goal_str']}. Current Athlete Progression Level: {biometrics['current_tier_level']}.\n"
            f"Target Macrocycle Duration: EXACTLY {DEFAULT_MACROCYCLE_DAYS} Days.\n"
            f"Biometrics Profile -> Age: {biometrics['age']}, Height: {biometrics['height']}cm, Weight: {biometrics['weight']}kg, Operational BMI: {biometrics['bmi']}.\n"
            f"Heart Rate Max Capacity: {biometrics['target_max_hr']} BPM. Metabolic Maintenance: {biometrics['predicted_maintenance_calories']} kcal. Skip Risk: {biometrics['skip_probability']:.2f}.\n\n"
            f"Tasks:\n"
            f"1. Structure an explicit {DEFAULT_MACROCYCLE_DAYS}-day chronological schedule array layout mapping days 1 to {DEFAULT_MACROCYCLE_DAYS}.\n"
            f"2. Prescribe custom muscle group splits or recovery blocks based on ALL biometric variables.\n"
            f"3. Generate specific exercise items with exact rep structures and numeric sets matching maintenance needs.\n"
            f"4. Attach exactly ONE hard physical metric challenge per day scaling linearly with their level: {biometrics['current_tier_level']}.\n"
            f"5. Verify the schedule size matches exactly {DEFAULT_MACROCYCLE_DAYS} objects."
        )
