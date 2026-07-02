"""
Router Layer: Dietician Endpoints
FastAPI routes for meal logging and grocery list generation.
"""

import json
import datetime
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError
from pymongo.errors import PyMongoError


# ============================================================================
# Request/Response Models
# ============================================================================
class FoodItem(BaseModel):
    food_name: str
    quantity: str
    estimated_calories: int
    protein_g: float
    carbs_g: float
    fats_g: float


class DietResponse(BaseModel):
    extracted_foods: List[FoodItem]
    total_meal_calories: int
    nutritional_advice: str


class LogMealRequest(BaseModel):
    user_id: str
    user_input: str


class GroceryItem(BaseModel):
    item_name: str
    estimated_quantity: str
    category: str
    purpose: str


class GroceryResponse(BaseModel):
    dietary_focus: str
    items: List[GroceryItem]
    meal_prep_tip: str


class GroceryRequest(BaseModel):
    user_id: str
    preferences_or_allergies: str = "None"


# ============================================================================
# Router Setup
# ============================================================================
router = APIRouter(prefix="/api/dietician", tags=["Dietician Engine"])

# Lazy initialization of service
_service_cache = None

def get_service():
    """Get or create dietician service (lazy loading)."""
    global _service_cache
    if _service_cache is None:
        from app.services.dietician_service import DieticianService
        _service_cache = DieticianService()
    return _service_cache


# ============================================================================
# Endpoints
# ============================================================================
@router.post("/log-meal", response_model=DietResponse)
async def log_meal(payload: LogMealRequest):
    """Analyze meal input and return nutritional breakdown."""
    try:
        service = get_service()
        result = await service.analyze_meal(payload.user_id, payload.user_input, DietResponse)
        return result

    except (RuntimeError, ValueError) as e:
        print(f"[ERROR] Meal logging failed: {e}")
        if "Profile required" in str(e):
            raise HTTPException(status_code=404, detail="Profile required before logging meals.")
        raise HTTPException(status_code=500, detail="Unable to analyze meal at this time.")
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"[VALIDATION_ERROR] Meal validation failed: {e}")
        raise HTTPException(status_code=502, detail="Meal analysis format invalid.")
    except PyMongoError as e:
        print(f"[DB_ERROR] Meal persistence failed: {e}")
        raise HTTPException(status_code=500, detail="Database write failed while saving meal information.")


@router.post("/generate-grocery-list", response_model=GroceryResponse)
async def generate_grocery_list(payload: GroceryRequest):
    """Generate a weekly macro-focused grocery list."""
    try:
        service = get_service()
        result = await service.generate_grocery_list(
            payload.user_id,
            payload.preferences_or_allergies,
            GroceryResponse
        )
        return result

    except (RuntimeError, ValueError) as e:
        print(f"[ERROR] Grocery list generation failed: {e}")
        if "Profile required" in str(e):
            raise HTTPException(status_code=404, detail="Profile required to build grocery plan.")
        raise HTTPException(status_code=500, detail="Unable to generate grocery list at this time.")
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"[VALIDATION_ERROR] Grocery validation failed: {e}")
        raise HTTPException(status_code=502, detail="Grocery list format invalid.")
    except PyMongoError as e:
        print(f"[DB_ERROR] Grocery persistence failed: {e}")
        raise HTTPException(status_code=500, detail="Database write failed while saving grocery list.")


@router.get("/nutrition-summary/{user_id}")
async def get_nutrition_summary(user_id: str, days: int = 7):
    """Return calorie and macro totals from logged meals."""
    try:
        from app.database import meals_col, users_col

        days = max(1, min(days, 30))
        today = datetime.datetime.utcnow().date()
        since = datetime.datetime.combine(today - datetime.timedelta(days=days - 1), datetime.time.min)
        user = await users_col.find_one({"user_id": user_id}) or await users_col.find_one({"_id": user_id})
        calorie_target = int(user.get("daily_calorie_target") or user.get("target_calories") or 2200) if user else 2200

        logs = await meals_col.find({
            "user_id": user_id,
            "timestamp": {"$gte": since},
            "metrics": {"$exists": True}
        }).sort("timestamp", -1).to_list(length=500)

        daily = {}
        recent_logs = []
        for log in logs:
            timestamp = log.get("timestamp")
            if not isinstance(timestamp, datetime.datetime):
                continue
            day_key = timestamp.date().isoformat()
            metrics = log.get("metrics") or {}
            foods = metrics.get("extracted_foods") or []
            day = daily.setdefault(day_key, {
                "date": day_key,
                "calories": 0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fats_g": 0.0,
                "meal_count": 0,
            })
            day["calories"] += int(metrics.get("total_meal_calories") or 0)
            day["meal_count"] += 1
            for food in foods:
                day["protein_g"] += float(food.get("protein_g") or 0)
                day["carbs_g"] += float(food.get("carbs_g") or 0)
                day["fats_g"] += float(food.get("fats_g") or 0)
            recent_logs.append({
                "timestamp": timestamp.isoformat(),
                "raw_input": log.get("raw_input", ""),
                "calories": int(metrics.get("total_meal_calories") or 0),
                "advice": metrics.get("nutritional_advice", ""),
            })

        today_key = today.isoformat()
        today_summary = daily.get(today_key, {
            "date": today_key,
            "calories": 0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fats_g": 0.0,
            "meal_count": 0,
        })
        today_summary["calorie_target"] = calorie_target
        today_summary["remaining_calories"] = max(calorie_target - int(today_summary["calories"]), 0)

        ordered_daily = [
            daily.get((today - datetime.timedelta(days=days - 1 - idx)).isoformat(), {
                "date": (today - datetime.timedelta(days=days - 1 - idx)).isoformat(),
                "calories": 0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fats_g": 0.0,
                "meal_count": 0,
            })
            for idx in range(days)
        ]

        return {
            "status": "success",
            "today": today_summary,
            "daily": ordered_daily,
            "recent_logs": recent_logs[:10],
        }
    except Exception as e:
        print(f"[NUTRITION_SUMMARY_ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve nutrition summary.")
