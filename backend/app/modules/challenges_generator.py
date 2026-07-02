"""
Daily Challenges Generator
Generates specific daily challenges for workout plans using AI.
"""

import asyncio
import logging
from typing import Dict, List, Any
from groq import Groq
import os
import json

logger = logging.getLogger(__name__)

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

client = Groq(api_key=GROQ_API_KEY)


async def generate_daily_challenges(
    workout_plan: Dict[str, Any],
    archetype: str,
    difficulty_multiplier: str,
    num_days: int
) -> List[Dict[str, Any]]:
    """
    Generate specific daily challenges for each day of the workout plan.
    
    Args:
        workout_plan: The structured workout plan with exercises
        archetype: User's training archetype (e.g., 'strength', 'endurance', 'hybrid')
        difficulty_multiplier: Difficulty level (e.g., 'beginner', 'intermediate', 'advanced')
        num_days: Number of days to generate challenges for
    
    Returns:
        List of daily challenges with specific metrics and targets
    """
    try:
        prompt = f"""You are a creative, behavioral fitness assistant. Your sole task is to generate {num_days} highly engaging daily health challenges tailored directly to complement the user's weekly workout plan.

INPUT VARIABLES TO ANALYZE:
1. Extracted Weekly Plan: {json.dumps(workout_plan, default=str)}
2. User Profile: {{"archetype": "{archetype}", "difficulty_multiplier": "{difficulty_multiplier}"}}

CRITICAL RULES:
- Generate an array containing exactly {num_days} objects, matching days 1 through {num_days} sequentially.
- Align the challenge with the theme of that workout day. Include a concrete action description along with specific target sets and reps.
- TIME-BASED METRIC RULE: If a challenge is timed (e.g., a 15-minute walk or a 5-minute stretch), populate BOTH the "sets" and the "reps" fields with that exact time string (e.g., "15 mins").
- Keep the challenge text field concise and direct. Do not write a paragraph.
- Return a raw JSON object matching your database scheme exactly. No conversational text wrappers.

You must return your output strictly in JSON format matching this schema:
{{
  "daily_challenges": [
    {{
      "day": 1,
      "challenge": "Short challenge summary title",
      "description": "Clear action instruction text",
      "sets": "e.g., '3' or '5 mins'",
      "reps": "e.g., '10' or '5 mins'"
    }}
  ]
}}"""

        # Run Groq API call in thread to avoid blocking
        def call_groq():
            message = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1200,
                response_format={"type": "json_object"}
            )
            return message.choices[0].message.content

        response = await asyncio.to_thread(call_groq)

        # Parse the JSON response
        # Remove markdown code blocks if present
        response_text = response.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        parsed = json.loads(response_text.strip())
        daily_challenges = parsed.get("daily_challenges", parsed)
        
        # Validate and normalize the response
        if not isinstance(daily_challenges, list):
            daily_challenges = [daily_challenges]
        
        # Ensure we have exactly num_days challenges
        daily_challenges = daily_challenges[:num_days]
        
        # Add any missing fields
        for i, challenge in enumerate(daily_challenges):
            if "day" not in challenge:
                challenge["day"] = i + 1
            challenge["challenge"] = challenge.get("challenge") or challenge.get("title") or f"Day {i + 1} Challenge"
            challenge["description"] = challenge.get("description") or "Complete the assigned movement with controlled form."
            if "sets" not in challenge:
                challenge["sets"] = str(challenge.get("metrics", {}).get("sets", "3"))
            if "reps" not in challenge:
                challenge["reps"] = str(challenge.get("metrics", {}).get("reps", "10"))
        
        logger.info(f"[CHALLENGES_GENERATED] Generated {len(daily_challenges)} daily challenges for {archetype} {difficulty_multiplier}")
        
        return daily_challenges

    except json.JSONDecodeError as e:
        logger.error(f"[CHALLENGES_JSON_ERROR] Failed to parse Groq response as JSON: {str(e)}", exc_info=True)
        # Return fallback challenges
        return _generate_fallback_challenges(num_days, difficulty_multiplier)
    
    except Exception as e:
        logger.error(f"[CHALLENGES_GENERATION_ERROR] Failed to generate challenges: {str(e)}", exc_info=True)
        # Return fallback challenges
        return _generate_fallback_challenges(num_days, difficulty_multiplier)


def _generate_fallback_challenges(num_days: int, difficulty: str) -> List[Dict[str, Any]]:
    """Generate fallback challenges if AI generation fails."""
    fallback_metrics = {
        "beginner": {"reps": "10", "sets": "2"},
        "intermediate": {"reps": "15", "sets": "3"},
        "advanced": {"reps": "20", "sets": "4"}
    }
    
    metrics = fallback_metrics.get(difficulty, fallback_metrics["intermediate"])
    
    challenges = []
    exercise_types = ["Strength", "Endurance", "Core", "Cardio", "Flexibility", "Recovery", "HIIT"]
    
    for day in range(1, num_days + 1):
        exercise_type = exercise_types[(day - 1) % len(exercise_types)]
        challenges.append({
            "day": day,
            "challenge": f"{exercise_type} Challenge",
            "description": f"Complete {exercise_type.lower()} exercises with focus on form and consistency",
            "sets": metrics["sets"],
            "reps": metrics["reps"]
        })
    
    return challenges


async def enhance_workout_plan(
    workout_plan: Dict[str, Any],
    archetype: str,
    difficulty_multiplier: str
) -> Dict[str, Any]:
    """
    Enhance a workout plan by adding structured daily challenges.
    
    Args:
        workout_plan: The base workout plan
        archetype: User's training archetype
        difficulty_multiplier: Difficulty level
    
    Returns:
        Workout plan with added daily challenges
    """
    try:
        # Determine number of days from workout plan
        num_days = len(workout_plan.get("days", [])) or 7  # Default to 7 days if not specified
        
        # Generate challenges
        daily_challenges = await generate_daily_challenges(
            workout_plan=workout_plan,
            archetype=archetype,
            difficulty_multiplier=difficulty_multiplier,
            num_days=num_days
        )
        
        # Enhance the plan with challenges
        enhanced_plan = {
            **workout_plan,
            "daily_challenges": daily_challenges,
            "total_days": num_days,
            "has_challenges": True
        }
        
        return enhanced_plan
    
    except Exception as e:
        logger.error(f"[ENHANCE_PLAN_ERROR] Failed to enhance workout plan: {str(e)}", exc_info=True)
        # Return original plan if enhancement fails
        return {
            **workout_plan,
            "daily_challenges": _generate_fallback_challenges(
                len(workout_plan.get("days", [])) or 7,
                difficulty_multiplier
            ),
            "has_challenges": True
        }
