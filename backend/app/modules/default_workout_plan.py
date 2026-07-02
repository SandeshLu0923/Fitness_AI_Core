"""
Default Workout Plan Data
Contains the default workout plan and daily challenges for new users.
"""

from datetime import datetime, timedelta

# Default workout plan structure
DEFAULT_WORKOUT_PLAN = {
    "archetype": "Full Body",
    "difficulty_multiplier": "Beginner",
    "total_days": 7,
    "days": [
        {
            "day": 1,
            "focus": "Full Body Warm-up",
            "exercises": [
                {
                    "name": "Jumping Jacks",
                    "sets": 3,
                    "reps": 30,
                    "rest_seconds": 60
                },
                {
                    "name": "Squats",
                    "sets": 3,
                    "reps": 15,
                    "rest_seconds": 90
                },
                {
                    "name": "Pushups",
                    "sets": 3,
                    "reps": 15,
                    "rest_seconds": 90
                },
                {
                    "name": "Pullups",
                    "sets": 4,
                    "reps": 10,
                    "rest_seconds": 120
                },
                {
                    "name": "Situps",
                    "sets": 3,
                    "reps": 20,
                    "rest_seconds": 60
                }
            ]
        }
    ]
}

# Repeat the same day plan for all 7 days
for day in range(2, 8):
    DEFAULT_WORKOUT_PLAN["days"].append({
        "day": day,
        "focus": "Full Body Warm-up",
        "exercises": [
            {
                "name": "Jumping Jacks",
                "sets": 3,
                "reps": 30,
                "rest_seconds": 60
            },
            {
                "name": "Squats",
                "sets": 3,
                "reps": 15,
                "rest_seconds": 90
            },
            {
                "name": "Pushups",
                "sets": 3,
                "reps": 15,
                "rest_seconds": 90
            },
            {
                "name": "Pullups",
                "sets": 4,
                "reps": 10,
                "rest_seconds": 120
            },
            {
                "name": "Situps",
                "sets": 3,
                "reps": 20,
                "rest_seconds": 60
            }
        ]
    })


# Default daily challenges (one per day, repeated for 7 days)
DEFAULT_DAILY_CHALLENGES = [
    {
        "day": 1,
        "challenge": "Squats - Complete 30 reps",
        "daily_metric_challenge": "Complete 30 squats",
        "difficulty": "Beginner",
        "exercise": "Squats",
        "target_reps": 30
    }
]

# Repeat for all 7 days
for day in range(2, 8):
    DEFAULT_DAILY_CHALLENGES.append({
        "day": day,
        "challenge": "Squats - Complete 30 reps",
        "daily_metric_challenge": "Complete 30 squats",
        "difficulty": "Beginner",
        "exercise": "Squats",
        "target_reps": 30
    })


def get_default_workout_plan():
    """Get the default workout plan for new users."""
    return DEFAULT_WORKOUT_PLAN.copy()


def get_default_daily_challenges():
    """Get the default daily challenges for new users."""
    return [challenge.copy() for challenge in DEFAULT_DAILY_CHALLENGES]


def get_weekly_plan_with_dates(start_date: datetime = None):
    """
    Get a weekly plan with actual dates.
    
    Args:
        start_date: The date to start the week from. Defaults to today.
    
    Returns:
        A list of days with exercises and dates.
    """
    if start_date is None:
        start_date = datetime.now()
    
    weekly_plan = []
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        day_plan = {
            "day": i + 1,
            "date": current_date.strftime("%Y-%m-%d"),
            "day_name": current_date.strftime("%A"),
            "focus": "Full Body Warm-up",
            "exercises": [
                {
                    "name": "Jumping Jacks",
                    "sets": 3,
                    "reps": 30,
                    "rest_seconds": 60
                },
                {
                    "name": "Squats",
                    "sets": 3,
                    "reps": 15,
                    "rest_seconds": 90
                },
                {
                    "name": "Pushups",
                    "sets": 3,
                    "reps": 15,
                    "rest_seconds": 90
                },
                {
                    "name": "Pullups",
                    "sets": 4,
                    "reps": 10,
                    "rest_seconds": 120
                },
                {
                    "name": "Situps",
                    "sets": 3,
                    "reps": 20,
                    "rest_seconds": 60
                }
            ]
        }
        weekly_plan.append(day_plan)
    
    return weekly_plan


def get_todays_workout(start_date: datetime = None):
    """Get today's workout plan from the weekly schedule."""
    if start_date is None:
        start_date = datetime.now()
    
    weekly_plan = get_weekly_plan_with_dates(start_date)
    # Return the first day's plan (today)
    return weekly_plan[0] if weekly_plan else None


def get_todays_challenge(start_date: datetime = None):
    """Get today's daily challenge."""
    if start_date is None:
        start_date = datetime.now()
    
    return {
        "date": start_date.strftime("%Y-%m-%d"),
        "day_name": start_date.strftime("%A"),
        "challenge": "Squats - Complete 30 reps",
        "daily_metric_challenge": "Complete 30 squats",
        "difficulty": "Beginner",
        "exercise": "Squats",
        "target_reps": 30,
        "is_activated": False,
        "is_completed": False
    }
