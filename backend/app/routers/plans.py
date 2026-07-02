"""
Router: Plan Management
Handles saving diet plans, workout plans, and pinning chats to database.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from app.database import diet_plans_col, workout_plans_col, pinned_chats_col, chats_col, users_col
from app.modules.challenges_generator import generate_daily_challenges, enhance_workout_plan
from app.services.plan_date_service import align_weekly_plan_dates, build_tracking_state_from_workout_plan
from app.services.workout_summary_service import WorkoutSummaryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/plans", tags=["Plan Management"])


def _serialize_mongo_value(value: Any) -> Any:
    """Convert Mongo-specific values recursively before FastAPI serializes the response."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_mongo_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_mongo_value(item) for key, item in value.items()}
    if value.__class__.__name__ == "ObjectId":
        return str(value)
    return value


def _normalize_session_messages(raw_messages: Any) -> List[Dict[str, Any]]:
    """Support both new session messages and legacy migrated chat documents."""
    if not isinstance(raw_messages, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue

        if "user_message" in item or "response" in item or "response_text" in item:
            timestamp = item.get("timestamp")
            user_text = item.get("user_message", "")
            buddy_text = item.get("response_text") or item.get("response", {}).get("motivational_reply", "")
            if user_text:
                normalized.append({"sender": "user", "text": user_text, "timestamp": timestamp})
            if buddy_text:
                normalized.append({"sender": "buddy", "text": buddy_text, "timestamp": timestamp})
            continue

        normalized.append({
            "sender": item.get("sender") or "buddy",
            "text": item.get("text") or item.get("message") or "",
            "timestamp": item.get("timestamp"),
        })

    return normalized


def _plan_age_days(plan_doc: Optional[Dict[str, Any]]) -> Optional[int]:
    if not plan_doc:
        return None
    reference = plan_doc.get("updated_at") or plan_doc.get("created_at")
    if not isinstance(reference, datetime):
        return None
    return max((datetime.utcnow() - reference).days, 0)


def _is_plan_expired(plan_doc: Optional[Dict[str, Any]], duration_days: int = 7) -> bool:
    age = _plan_age_days(plan_doc)
    return age is not None and age >= duration_days


def _notification_item(kind: str, title: str, message: str, action: str, severity: str = "info") -> Dict[str, Any]:
    return {
        "id": f"{kind}:{action}:{datetime.utcnow().date().isoformat()}",
        "kind": kind,
        "title": title,
        "message": message,
        "action": action,
        "severity": severity,
        "created_at": datetime.utcnow().isoformat(),
    }


# ==========================================
# DATA MODELS
# ==========================================

class DietPlanRequest(BaseModel):
    user_id: str
    diet_plan: Dict[str, Any]
    grocery_list: List[str]
    notes: str = ""


class WorkoutPlanRequest(BaseModel):
    user_id: str
    workout_plan: Dict[str, Any]
    daily_challenges: List[Dict[str, Any]]
    archetype: str
    difficulty_multiplier: str


class PinChatRequest(BaseModel):
    user_id: str
    chat_message: str
    sender: str  # 'user' or 'buddy'


class UnpinChatRequest(BaseModel):
    user_id: str
    pin_id: str


class UpdateDietPlanRequest(BaseModel):
    diet_plan: Dict[str, Any]
    grocery_list: List[str]
    notes: str = ""


class UpdateWorkoutPlanRequest(BaseModel):
    workout_plan: Dict[str, Any]
    daily_challenges: List[Dict[str, Any]]
    archetype: str
    difficulty_multiplier: str


class GenerateChallengesRequest(BaseModel):
    workout_plan: Dict[str, Any]
    archetype: str
    difficulty_multiplier: str
    num_days: Optional[int] = None


# ==========================================
# ENDPOINTS
# ==========================================

@router.post("/save-diet-plan", status_code=status.HTTP_201_CREATED)
async def save_diet_plan(payload: DietPlanRequest):
    """Save user's diet plan along with grocery list."""
    try:
        aligned_diet_plan = align_weekly_plan_dates(payload.diet_plan)
        existing_plan = await diet_plans_col.find_one({"user_id": payload.user_id}, sort=[("updated_at", -1), ("created_at", -1)])
        now = datetime.utcnow()

        plan_document = {
            "user_id": payload.user_id,
            "diet_plan": aligned_diet_plan,
            "grocery_list": payload.grocery_list,
            "notes": payload.notes,
            "updated_at": now,
            "start_date": now.date().isoformat(),
            "is_active": True
        }
        
        if existing_plan:
            await diet_plans_col.update_one(
                {"_id": existing_plan["_id"]},
                {"$set": plan_document, "$setOnInsert": {"created_at": existing_plan.get("created_at", now)}}
            )
            await diet_plans_col.delete_many({"user_id": payload.user_id, "_id": {"$ne": existing_plan["_id"]}})
            plan_id = str(existing_plan["_id"])
        else:
            plan_document["created_at"] = now
            result = await diet_plans_col.insert_one(plan_document)
            plan_id = str(result.inserted_id)

        logger.info(f"[DIET_PLAN_SAVED] Plan {plan_id} for user {payload.user_id}")
        try:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference("diet_planning", user_id=payload.user_id, success=True)
        except Exception as analytics_error:
            logger.debug(f"[ANALYTICS_WARNING] Diet planning event not logged: {analytics_error}")
        
        return {
            "status": "success",
            "plan_id": plan_id,
            "message": "Diet plan and grocery list saved successfully!"
        }
    except Exception as e:
        logger.error(f"[DIET_PLAN_ERROR] Failed to save diet plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save diet plan.")


@router.post("/generate-challenges", status_code=status.HTTP_200_OK)
async def generate_challenges(payload: GenerateChallengesRequest):
    """Generate daily challenges for a workout plan."""
    try:
        num_days = payload.num_days or len(payload.workout_plan.get("days", [])) or 7
        
        daily_challenges = await generate_daily_challenges(
            workout_plan=payload.workout_plan,
            archetype=payload.archetype,
            difficulty_multiplier=payload.difficulty_multiplier,
            num_days=num_days
        )
        
        logger.info(f"[CHALLENGES_GENERATED] Generated {len(daily_challenges)} challenges for {payload.archetype}")
        
        return {
            "status": "success",
            "total_challenges": len(daily_challenges),
            "challenges": daily_challenges,
            "message": "Daily challenges generated successfully!"
        }
    except Exception as e:
        logger.error(f"[GENERATE_CHALLENGES_ERROR] Failed to generate challenges: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate challenges.")


@router.post("/save-workout-plan", status_code=status.HTTP_201_CREATED)
async def save_workout_plan(payload: WorkoutPlanRequest):
    """Save user's workout plan along with daily challenges."""
    try:
        aligned_workout_plan = align_weekly_plan_dates(payload.workout_plan)

        # Use provided challenges or generate if empty
        daily_challenges = payload.daily_challenges
        if not daily_challenges or len(daily_challenges) == 0:
            logger.info(f"[SAVE_WORKOUT_PLAN] No challenges provided, generating...")
            num_days = len(aligned_workout_plan.get("days", [])) or 7
            daily_challenges = await generate_daily_challenges(
                workout_plan=aligned_workout_plan,
                archetype=payload.archetype,
                difficulty_multiplier=payload.difficulty_multiplier,
                num_days=num_days
            )
        
        existing_plan = await workout_plans_col.find_one({"user_id": payload.user_id}, sort=[("updated_at", -1), ("created_at", -1)])
        now = datetime.utcnow()
        plan_document = {
            "user_id": payload.user_id,
            "workout_plan": aligned_workout_plan,
            "daily_challenges": daily_challenges,
            "archetype": payload.archetype,
            "difficulty_multiplier": payload.difficulty_multiplier,
            "updated_at": now,
            "start_date": now.date().isoformat(),
            "is_active": True,
            "total_days": len(daily_challenges)
        }
        
        if existing_plan:
            await workout_plans_col.update_one(
                {"_id": existing_plan["_id"]},
                {"$set": plan_document, "$setOnInsert": {"created_at": existing_plan.get("created_at", now)}}
            )
            await workout_plans_col.delete_many({"user_id": payload.user_id, "_id": {"$ne": existing_plan["_id"]}})
            plan_id = str(existing_plan["_id"])
        else:
            plan_document["created_at"] = now
            result = await workout_plans_col.insert_one(plan_document)
            plan_id = str(result.inserted_id)

        tracking_state = build_tracking_state_from_workout_plan(
            aligned_workout_plan,
            difficulty_multiplier=payload.difficulty_multiplier,
            max_days=len(daily_challenges) or 7,
        )
        await users_col.update_one(
            {"user_id": payload.user_id},
            {"$set": {"active_macrocycle": tracking_state}},
            upsert=True
        )
        logger.info(f"[WORKOUT_PLAN_SAVED] Plan {plan_id} for user {payload.user_id} with {len(daily_challenges)} challenges")
        try:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_ai_inference("workout_planning", user_id=payload.user_id, success=True)
        except Exception as analytics_error:
            logger.debug(f"[ANALYTICS_WARNING] Workout planning event not logged: {analytics_error}")
        
        return {
            "status": "success",
            "plan_id": plan_id,
            "total_days": len(daily_challenges),
            "total_challenges": len(daily_challenges),
            "message": "Workout plan with daily challenges saved successfully!"
        }
    except Exception as e:
        logger.error(f"[WORKOUT_PLAN_ERROR] Failed to save workout plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save workout plan.")


@router.put("/diet-plans/{plan_id}", status_code=status.HTTP_200_OK)
async def update_diet_plan(plan_id: str, payload: UpdateDietPlanRequest):
    """Update an existing diet plan."""
    try:
        from bson import ObjectId

        existing_plan = await diet_plans_col.find_one({"_id": ObjectId(plan_id)})
        if not existing_plan:
            raise HTTPException(status_code=404, detail="Diet plan not found.")

        aligned_diet_plan = align_weekly_plan_dates(payload.diet_plan)
        
        update_data = {
            "diet_plan": aligned_diet_plan,
            "grocery_list": payload.grocery_list,
            "notes": payload.notes,
            "is_active": True,
            "updated_at": datetime.utcnow()
        }
        
        await diet_plans_col.delete_many(
            {"_id": {"$ne": ObjectId(plan_id)}, "user_id": existing_plan.get("user_id")}
        )

        result = await diet_plans_col.update_one(
            {"_id": ObjectId(plan_id)},
            {"$set": update_data}
        )
        
        logger.info(f"[DIET_PLAN_UPDATED] Plan {plan_id} updated")
        
        return {
            "status": "success",
            "plan_id": plan_id,
            "message": "Diet plan updated successfully!"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPDATE_DIET_PLAN_ERROR] Failed to update diet plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update diet plan.")


@router.put("/workout-plans/{plan_id}", status_code=status.HTTP_200_OK)
async def update_workout_plan(plan_id: str, payload: UpdateWorkoutPlanRequest):
    """Update an existing workout plan."""
    try:
        from bson import ObjectId

        aligned_workout_plan = align_weekly_plan_dates(payload.workout_plan)
        existing_plan = await workout_plans_col.find_one({"_id": ObjectId(plan_id)})
        if not existing_plan:
            raise HTTPException(status_code=404, detail="Workout plan not found.")
        
        update_data = {
            "workout_plan": aligned_workout_plan,
            "daily_challenges": payload.daily_challenges,
            "archetype": payload.archetype,
            "difficulty_multiplier": payload.difficulty_multiplier,
            "total_days": len(payload.daily_challenges),
            "updated_at": datetime.utcnow()
        }
        
        result = await workout_plans_col.update_one(
            {"_id": ObjectId(plan_id)},
            {"$set": update_data}
        )
        await workout_plans_col.delete_many(
            {"_id": {"$ne": ObjectId(plan_id)}, "user_id": existing_plan.get("user_id")}
        )
        
        tracking_state = build_tracking_state_from_workout_plan(
            aligned_workout_plan,
            difficulty_multiplier=payload.difficulty_multiplier,
            max_days=len(payload.daily_challenges) or 7,
        )
        await users_col.update_one(
            {"user_id": existing_plan.get("user_id")},
            {"$set": {"active_macrocycle": tracking_state}},
            upsert=True
        )
        
        logger.info(f"[WORKOUT_PLAN_UPDATED] Plan {plan_id} updated")
        
        return {
            "status": "success",
            "plan_id": plan_id,
            "total_days": len(payload.daily_challenges),
            "message": "Workout plan updated successfully!"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPDATE_WORKOUT_PLAN_ERROR] Failed to update workout plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update workout plan.")


@router.post("/pin-chat", status_code=status.HTTP_201_CREATED)
async def pin_chat(payload: PinChatRequest):
    """Pin a chat message for 7 days."""
    try:
        # Calculate expiration (7 days from now)
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        pin_document = {
            "user_id": payload.user_id,
            "chat_message": payload.chat_message,
            "message_text": payload.chat_message,
            "sender": payload.sender,
            "pinned_at": datetime.utcnow(),
            "expires_at": expires_at
        }
        
        result = await pinned_chats_col.insert_one(pin_document)
        logger.info(f"[CHAT_PINNED] Chat {result.inserted_id} pinned for user {payload.user_id}")
        
        return {
            "status": "success",
            "pin_id": str(result.inserted_id),
            "expires_at": expires_at.isoformat(),
            "message": "Chat pinned for 7 days!"
        }
    except Exception as e:
        logger.error(f"[PIN_CHAT_ERROR] Failed to pin chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to pin chat.")


@router.post("/unpin-chat", status_code=status.HTTP_200_OK)
async def unpin_chat(payload: UnpinChatRequest):
    """Remove a pinned chat."""
    try:
        from bson import ObjectId
        result = await pinned_chats_col.delete_one({
            "_id": ObjectId(payload.pin_id),
            "user_id": payload.user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Pinned chat not found.")
        
        logger.info(f"[CHAT_UNPINNED] Chat {payload.pin_id} unpinned for user {payload.user_id}")
        
        return {"status": "success", "message": "Chat unpinned successfully!"}
    except Exception as e:
        logger.error(f"[UNPIN_CHAT_ERROR] Failed to unpin chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to unpin chat.")


@router.get("/pinned-chats/{user_id}", status_code=status.HTTP_200_OK)
async def get_pinned_chats(user_id: str):
    """Get all pinned chats for a user."""
    try:
        cursor = pinned_chats_col.find({
            "user_id": user_id,
            "expires_at": {"$gt": datetime.utcnow()}
        }).sort("pinned_at", -1)
        
        pinned_chats = await cursor.to_list(length=100)
        
        # Convert ObjectId to string for JSON serialization
        for chat in pinned_chats:
            chat["_id"] = str(chat["_id"])
        
        return {
            "status": "success",
            "total_pinned": len(pinned_chats),
            "chats": pinned_chats
        }
    except Exception as e:
        logger.error(f"[GET_PINNED_CHATS_ERROR] Failed to retrieve pinned chats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve pinned chats.")


@router.get("/diet-plans/{user_id}", status_code=status.HTTP_200_OK)
async def get_diet_plans(user_id: str):
    """Get the current diet plan for a user."""
    try:
        plan = await diet_plans_col.find_one(
            {"user_id": user_id, "is_active": True},
            sort=[("updated_at", -1), ("created_at", -1)]
        )
        if not plan:
            plan = await diet_plans_col.find_one(
                {"user_id": user_id},
                sort=[("updated_at", -1), ("created_at", -1)]
            )

        plans = [plan] if plan else []
        
        for plan in plans:
            plan["_id"] = str(plan["_id"])
            plan["created_at"] = plan["created_at"].isoformat() if isinstance(plan.get("created_at"), datetime) else plan.get("created_at")
            if isinstance(plan.get("updated_at"), datetime):
                plan["updated_at"] = plan["updated_at"].isoformat()
        
        return {
            "status": "success",
            "total_plans": len(plans),
            "plans": plans
        }
    except Exception as e:
        logger.error(f"[GET_DIET_PLANS_ERROR] Failed to retrieve diet plans: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve diet plans.")


@router.get("/overview/{user_id}", status_code=status.HTTP_200_OK)
async def get_plan_overview(user_id: str):
    """Return compact dashboard state for diet/workout cards and notifications."""
    try:
        user_id = user_id.strip()
        active_diet = await diet_plans_col.find_one(
            {"user_id": user_id, "is_active": True},
            sort=[("updated_at", -1), ("created_at", -1)]
        )
        if not active_diet:
            active_diet = await diet_plans_col.find_one(
                {"user_id": user_id},
                sort=[("updated_at", -1), ("created_at", -1)]
            )

        latest_workout = await workout_plans_col.find_one(
            {"user_id": user_id},
            sort=[("updated_at", -1), ("created_at", -1)]
        )
        user_doc = await users_col.find_one({"user_id": user_id}) or {}
        active_macrocycle = user_doc.get("active_macrocycle") if isinstance(user_doc, dict) else None
        workout_completed = bool(active_macrocycle and active_macrocycle.get("is_fully_completed"))
        diet_expired = _is_plan_expired(active_diet)

        return {
            "status": "success",
            "diet": {
                "exists": bool(active_diet),
                "is_completed": bool(diet_expired),
                "age_days": _plan_age_days(active_diet),
                "plan_id": str(active_diet.get("_id")) if active_diet else None,
                "label": "Plan your next Diet" if diet_expired else ("Check Diet Plan" if active_diet else "Plan your Diet"),
            },
            "workout": {
                "exists": bool(latest_workout or active_macrocycle),
                "is_completed": workout_completed,
                "current_active_day": active_macrocycle.get("current_active_day") if active_macrocycle else None,
                "max_block_days": active_macrocycle.get("max_block_days") if active_macrocycle else None,
                "plan_id": str(latest_workout.get("_id")) if latest_workout else None,
                "label": "Plan your next Workout" if workout_completed else ("Check Workout Plan" if (latest_workout or active_macrocycle) else "Plan Workout"),
            }
        }
    except Exception as e:
        logger.error(f"[PLAN_OVERVIEW_ERROR] Failed to build plan overview: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve plan overview.")


@router.get("/notifications/{user_id}", status_code=status.HTTP_200_OK)
async def get_user_notifications(user_id: str):
    """Build actionable fitness notifications from existing plan and summary data."""
    try:
        user_id = user_id.strip()
        notifications: List[Dict[str, Any]] = []

        user_doc = await users_col.find_one({"user_id": user_id}) or {}
        active_macrocycle = user_doc.get("active_macrocycle") if isinstance(user_doc, dict) else None
        latest_workout = await workout_plans_col.find_one(
            {"user_id": user_id},
            sort=[("updated_at", -1), ("created_at", -1)]
        )
        active_diet = await diet_plans_col.find_one(
            {"user_id": user_id, "is_active": True},
            sort=[("updated_at", -1), ("created_at", -1)]
        )
        if not active_diet:
            active_diet = await diet_plans_col.find_one(
                {"user_id": user_id},
                sort=[("updated_at", -1), ("created_at", -1)]
            )

        if active_macrocycle:
            if active_macrocycle.get("is_fully_completed"):
                notifications.append(_notification_item(
                    "workout_completed",
                    "Training block completed",
                    "Your 7-day workout block is complete. Start the next workout plan when you are ready.",
                    "plan_next_workout",
                    "success",
                ))
            else:
                day = active_macrocycle.get("current_active_day", 1)
                notifications.append(_notification_item(
                    "workout_due",
                    "Workout due today",
                    f"Day {day} workout is ready. Complete it to keep your weekly streak active.",
                    "open_workout",
                    "info",
                ))
        elif latest_workout:
            notifications.append(_notification_item(
                "workout_due",
                "Workout plan available",
                "Your saved workout plan is ready. Open today’s workout routine.",
                "open_workout",
                "info",
            ))
        else:
            notifications.append(_notification_item(
                "workout_missing",
                "No workout plan active",
                "Create a 7-day workout plan to start tracking daily progress.",
                "plan_workout",
                "warning",
            ))

        if active_diet:
            if _is_plan_expired(active_diet):
                notifications.append(_notification_item(
                    "diet_refresh",
                    "Diet plan refresh due",
                    "Your 7-day diet plan window has ended. Generate your next diet plan.",
                    "plan_next_diet",
                    "warning",
                ))
            else:
                notifications.append(_notification_item(
                    "diet_active",
                    "Diet plan available",
                    "Your active diet plan and grocery list are ready to review.",
                    "open_diet",
                    "info",
                ))
        else:
            notifications.append(_notification_item(
                "diet_missing",
                "No diet plan saved",
                "Create a diet plan to get day-wise meals and a grocery list.",
                "plan_diet",
                "warning",
            ))

        try:
            weekly_summary = await WorkoutSummaryService().get_weekly_summary(user_id, persist=True)
            completion = float(weekly_summary.get("completion_percentage") or 0)
            if completion >= 80:
                notifications.append(_notification_item(
                    "weekly_progress",
                    "Strong weekly progress",
                    f"Weekly completion is {completion}%. Keep this structure going.",
                    "open_history",
                    "success",
                ))
            elif active_macrocycle and completion < 50:
                notifications.append(_notification_item(
                    "low_consistency",
                    "Weekly consistency needs attention",
                    f"Weekly completion is {completion}%. Consider adjusting your plan.",
                    "open_history",
                    "warning",
                ))
        except Exception as summary_error:
            logger.debug(f"[NOTIFICATION_SUMMARY_WARNING] {summary_error}")

        try:
            from app.database import meals_col, mood_logs_col
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            meal_count = await meals_col.count_documents({
                "user_id": user_id,
                "timestamp": {"$gte": today_start},
                "metrics": {"$exists": True}
            })
            if active_diet and meal_count == 0:
                notifications.append(_notification_item(
                    "meal_log_missing",
                    "No meals logged today",
                    "Log your first meal to track calories against your diet target.",
                    "open_diet",
                    "info",
                ))

            recent_mood = await mood_logs_col.find_one(
                {"user_id": user_id},
                sort=[("timestamp", -1)]
            )
            if recent_mood and float(recent_mood.get("score", 0)) < -0.4:
                notifications.append(_notification_item(
                    "motivation_nudge",
                    "Small step reminder",
                    "Your recent check-in sounded low. Start with one light set or a short walk.",
                    "open_workout",
                    "warning",
                ))
        except Exception as nudge_error:
            logger.debug(f"[NOTIFICATION_NUDGE_WARNING] {nudge_error}")

        return {
            "status": "success",
            "count": len(notifications),
            "notifications": notifications[:8],
        }
    except Exception as e:
        logger.error(f"[NOTIFICATIONS_ERROR] Failed to build notifications: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve notifications.")


@router.get("/workout-plans/{user_id}", status_code=status.HTTP_200_OK)
async def get_workout_plans(user_id: str):
    """Get all workout plans for a user."""
    try:
        cursor = workout_plans_col.find({"user_id": user_id}).sort("created_at", -1)
        plans = await cursor.to_list(length=100)
        
        for plan in plans:
            plan["_id"] = str(plan["_id"])
            plan["created_at"] = plan["created_at"].isoformat() if isinstance(plan.get("created_at"), datetime) else plan.get("created_at")
        
        return {
            "status": "success",
            "total_plans": len(plans),
            "plans": plans
        }
    except Exception as e:
        logger.error(f"[GET_WORKOUT_PLANS_ERROR] Failed to retrieve workout plans: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve workout plans.")


@router.get("/workout-plans/{user_id}/latest", status_code=status.HTTP_200_OK)
async def get_latest_workout_plan(user_id: str):
    """Get the most recent workout plan for a user."""
    try:
        plan = await workout_plans_col.find_one(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        )
        
        if not plan:
            return {
                "status": "success",
                "plan": None,
                "message": "No workout plans found."
            }
        
        plan["_id"] = str(plan["_id"])
        plan["created_at"] = plan["created_at"].isoformat() if isinstance(plan.get("created_at"), datetime) else plan.get("created_at")
        
        return {
            "status": "success",
            "plan": plan
        }
    except Exception as e:
        logger.error(f"[GET_LATEST_WORKOUT_PLAN_ERROR] Failed to retrieve latest workout plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve latest workout plan.")


@router.get("/workout/default/today", status_code=status.HTTP_200_OK)
async def get_default_todays_workout():
    """Get today's default workout plan."""
    try:
        from app.modules.default_workout_plan import get_todays_workout
        todays_plan = get_todays_workout()
        
        return {
            "status": "success",
            "workout": todays_plan,
            "message": "Default workout for today"
        }
    except Exception as e:
        logger.error(f"[GET_TODAY_WORKOUT_ERROR] {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve today's workout")


@router.get("/workout/default/weekly", status_code=status.HTTP_200_OK)
async def get_default_weekly_plan():
    """Get the default weekly workout plan with dates."""
    try:
        from app.modules.default_workout_plan import get_weekly_plan_with_dates
        weekly_plan = get_weekly_plan_with_dates()
        
        return {
            "status": "success",
            "weekly_plan": weekly_plan,
            "total_days": len(weekly_plan),
            "message": "Default weekly workout plan"
        }
    except Exception as e:
        logger.error(f"[GET_WEEKLY_PLAN_ERROR] {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve weekly plan")


@router.get("/challenge/default/today", status_code=status.HTTP_200_OK)
async def get_default_todays_challenge():
    """Get today's default daily challenge."""
    try:
        from app.modules.default_workout_plan import get_todays_challenge
        todays_challenge = get_todays_challenge()
        
        return {
            "status": "success",
            "challenge": todays_challenge,
            "message": "Default challenge for today"
        }
    except Exception as e:
        logger.error(f"[GET_TODAY_CHALLENGE_ERROR] {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve today's challenge")


@router.delete("/diet-plans/{plan_id}", status_code=status.HTTP_200_OK)
async def delete_diet_plan(plan_id: str):
    """Delete a diet plan."""
    try:
        from bson import ObjectId
        result = await diet_plans_col.delete_one({"_id": ObjectId(plan_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Diet plan not found.")
        
        logger.info(f"[DIET_PLAN_DELETED] Plan {plan_id} deleted")
        return {"status": "success", "message": "Diet plan deleted successfully!"}
    except Exception as e:
        logger.error(f"[DELETE_DIET_PLAN_ERROR] Failed to delete diet plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete diet plan.")


@router.delete("/workout-plans/{plan_id}", status_code=status.HTTP_200_OK)
async def delete_workout_plan(plan_id: str):
    """Delete a workout plan."""
    try:
        from bson import ObjectId
        result = await workout_plans_col.delete_one({"_id": ObjectId(plan_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Workout plan not found.")
        
        logger.info(f"[WORKOUT_PLAN_DELETED] Plan {plan_id} deleted")
        return {"status": "success", "message": "Workout plan deleted successfully!"}
    except Exception as e:
        logger.error(f"[DELETE_WORKOUT_PLAN_ERROR] Failed to delete workout plan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete workout plan.")


@router.get("/chat-sessions/{user_id}", status_code=status.HTTP_200_OK)
async def get_chat_sessions(user_id: str):
    """Get recent chat sessions for a user (from chat_sessions collection)."""
    try:
        from app.database import db
        chat_sessions_col = db.chat_sessions
        
        # Fetch recent sessions for this user, newest activity first.
        cursor = chat_sessions_col.find({"user_id": user_id}).sort("updated_at", -1).limit(10)
        sessions = await cursor.to_list(length=10)

        if not sessions:
            chat_cursor = chats_col.find({"user_id": user_id}).sort("timestamp", -1).limit(10)
            chats = await chat_cursor.to_list(length=10)
            sessions = [
                {
                    "_id": chat.get("_id"),
                    "user_id": user_id,
                    "session_id": chat.get("session_id") or str(chat.get("_id")),
                    "created_at": chat.get("timestamp"),
                    "updated_at": chat.get("timestamp"),
                    "title": str(chat.get("user_message", "New chat"))[:60],
                    "message_count": 2,
                    "messages": [
                        {"sender": "user", "text": chat.get("user_message", "")},
                        {"sender": "buddy", "text": chat.get("response_text") or chat.get("response", {}).get("motivational_reply", "")}
                    ]
                }
                for chat in chats
            ]
        
        # Convert ObjectId and datetime to serializable formats
        for session in sessions:
            session["_id"] = str(session["_id"])
            for date_key in ("created_at", "updated_at"):
                if date_key in session:
                    session[date_key] = session[date_key].isoformat() if isinstance(session.get(date_key), datetime) else session.get(date_key)
            messages = _normalize_session_messages(session.get("messages") or [])
            session["messages"] = messages
            if messages:
                session["preview"] = str(messages[-1].get("text", ""))[:120]
            session["message_count"] = session.get("message_count") or len(messages)
            session.setdefault("session_id", str(session["_id"]))
            session.setdefault("title", "New chat")
        
        return {
            "status": "success",
            "total_sessions": len(sessions),
            "sessions": _serialize_mongo_value(sessions)
        }
    except Exception as e:
        logger.error(f"[GET_CHAT_SESSIONS_ERROR] Failed to retrieve chat sessions: {str(e)}", exc_info=True)
        # Return empty list if collection doesn't exist yet
        return {
            "status": "success",
            "total_sessions": 0,
            "sessions": []
        }
