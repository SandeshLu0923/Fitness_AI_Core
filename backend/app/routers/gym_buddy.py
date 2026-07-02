"""
Router Layer: Gym Buddy Endpoints
FastAPI route handlers for chat, serialization, and message pinning.
"""

import datetime
import sys
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================
class CasualChatRequest(BaseModel):
    user_id: str
    user_message: str
    session_id: Optional[str] = None


class CasualChatResponse(BaseModel):
    motivational_reply: str
    requires_confirmation_buttons: bool
    confirmation_action_type: Optional[str] = None  # "workout", "diet", or "plan"
    plan_action_trigger: Optional[str] = None
    session_id: Optional[str] = None


class SerializationRequest(BaseModel):
    user_id: str
    action_type: str = "plan"
    approved_chat_plan: Optional[str] = None


class PinMessageRequest(BaseModel):
    user_id: str
    message_text: str


class PinnedMessageItem(BaseModel):
    id: str
    text: str
    pinned_at: datetime.datetime


# ============================================================================
# Router Setup
# ============================================================================
router = APIRouter(prefix="/api/gym-buddy", tags=["Virtual Gym Buddy"])

# Lazy initialization of services
_service_cache = None
_repo_cache = None

def get_service():
    """Get or create gym buddy service (lazy loading)."""
    global _service_cache
    if _service_cache is None:
        from app.services.gym_buddy_service import GymBuddyService
        _service_cache = GymBuddyService()
    return _service_cache

def get_repo():
    """Get or create gym buddy repository (lazy loading)."""
    global _repo_cache
    if _repo_cache is None:
        from app.repositories.gym_buddy_repo import GymBuddyRepository
        _repo_cache = GymBuddyRepository()
    return _repo_cache


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/debug/model")
async def get_model_debug():
    """Debug endpoint to check which Groq model is configured."""
    from app.config import GROQ_MODEL
    service = get_service()
    return {
        "configured_model": GROQ_MODEL,
        "service_model": service.chat_service.model
    }

@router.post("/chat", response_model=CasualChatResponse)
async def chat_gym_buddy(payload: CasualChatRequest):
    """
    Casual chat endpoint. Sends user message to Gemini and returns motivational response.
    Automatically detects plan triggers and includes confirmation buttons when needed.
    """
    logger.info(f"[CHAT_ENDPOINT] Received request from {payload.user_id}")
    
    try:
        user_id = payload.user_id.strip()
        is_diet_trigger = "__trigger_diet_plan__" in payload.user_message
        is_workout_trigger = "__trigger_workout_plan__" in payload.user_message

        logger.info(f"[CHAT_ENDPOINT] Calling service for {user_id}, message length: {len(payload.user_message)}")
        
        service = get_service()
        response = await service.generate_casual_chat_response(
            user_id=user_id,
            user_message=payload.user_message,
            session_id=payload.session_id,
            is_diet_trigger=is_diet_trigger,
            is_workout_trigger=is_workout_trigger
        )
        response["session_id"] = payload.session_id
        logger.info(f"[CHAT_ENDPOINT] Successfully generated response for {user_id}: {response.get('motivational_reply', '')[:50]}...")
        return response

    except Exception as e:
        logger.error(f"[ERROR] Chat endpoint failed: {type(e).__name__}: {str(e)}", exc_info=True)
        
        # Return thoughtful fallback response instead of raising error
        return CasualChatResponse(
            motivational_reply="Hey! I'm here to support your fitness journey! 💪 Tell me what's on your mind - whether it's about your workout, diet, or fitness goals, I'm ready to help push you towards your best self!",
            requires_confirmation_buttons=False,
            confirmation_action_type=None
        )


@router.post("/serialize-and-commit")
async def serialize_and_commit_data(payload: SerializationRequest):
    """
    Triggered when user confirms a plan. Converts the approved assistant message
    into structured weekly plan JSON and saves the relevant plan collections.
    """
    try:
        user_id = payload.user_id.strip()
        action_type = payload.action_type.strip().lower()

        service = get_service()
        if payload.approved_chat_plan:
            return await service.extract_and_commit_approved_plan(
                user_id=user_id,
                approved_chat_plan=payload.approved_chat_plan
            )

        if action_type == "workout":
            await service.serialize_chat_to_workout_plan(user_id)
            return {
                "status": "success",
                "message": "Workout plan serialization complete. Ready for confirmation."
            }

        raise HTTPException(status_code=400, detail="approved_chat_plan is required for plan updates.")

    except (RuntimeError, ValueError, TypeError) as e:
        print(f"[ERROR] Serialization endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to process plan serialization at this time.")


@router.post("/pin", status_code=status.HTTP_201_CREATED)
async def pin_chat_message(payload: PinMessageRequest):
    """Pin a chat message for 15 days."""
    try:
        user_id = payload.user_id.strip()
        repo = get_repo()
        await repo.pin_message(user_id, payload.message_text)
        return {"status": "success", "message": "Dialogue node pinned for 15 days."}

    except PyMongoError as e:
        print(f"[DB_ERROR] Failed to pin message: {e}")
        raise HTTPException(status_code=500, detail="Unable to pin message at this time.")


@router.get("/pinned-list/{user_id}", response_model=List[PinnedMessageItem])
async def get_pinned_messages(user_id: str):
    """Retrieve all pinned messages for a user."""
    try:
        repo = get_repo()
        docs = await repo.get_pinned_messages(user_id.strip())
        return [
            PinnedMessageItem(
                id=str(d["_id"]),
                text=d.get("message_text", d.get("chat_message", "")),
                pinned_at=d.get("pinned_at", datetime.datetime.utcnow())
            )
            for d in docs
        ]

    except PyMongoError as e:
        print(f"[DB_ERROR] Failed to read pinned messages: {e}")
        raise HTTPException(status_code=500, detail="Unable to load pinned messages at this time.")
    except Exception as e:
        print(f"[DB_ERROR] Unexpected error reading pinned messages: {e}")
        raise HTTPException(status_code=500, detail="Unable to process pinned messages at this time.")
