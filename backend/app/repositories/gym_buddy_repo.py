"""
Repository Layer: Gym Buddy Data Access
Handles all MongoDB interactions for chat history, pinned messages, and user profiles.
"""

import datetime
from typing import List, Optional, Dict, Any
from pymongo.errors import PyMongoError
from app.database import chats_col, chat_sessions_col, pinned_chats_col, users_col


class GymBuddyRepository:
    """Repository for gym buddy chat persistence and retrieval."""

    @staticmethod
    async def get_chat_history(user_id: str, session_id: Optional[str] = None, limit: int = 6) -> List[Dict[str, Any]]:
        """Retrieve recent chat history for the active session."""
        try:
            query = {
                "user_id": user_id,
                "user_message": {"$regex": "^(?!__trigger_)"}
            }
            if session_id:
                query["session_id"] = session_id

            cursor = chats_col.find(query).sort("timestamp", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            docs.reverse()
            return docs
        except Exception as e:
            print(f"[DB_WARNING] Failed to retrieve chat history, using fallback: {e}")
            # Return empty list as fallback (first time user, no history)
            return []

    @staticmethod
    async def save_chat_exchange(
        user_id: str,
        user_message: str,
        response_payload: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> None:
        """Persist a complete chat exchange to the database."""
        try:
            utc_now = datetime.datetime.utcnow()
            await chats_col.insert_one({
                "user_id": user_id,
                "session_id": session_id,
                "timestamp": utc_now,
                "user_message": user_message,
                "response": response_payload,
                "response_text": response_payload.get("motivational_reply", "")
            })
            if session_id:
                await chat_sessions_col.update_one(
                    {"user_id": user_id, "session_id": session_id},
                    {
                        "$setOnInsert": {
                            "user_id": user_id,
                            "session_id": session_id,
                            "created_at": utc_now,
                            "title": GymBuddyRepository._build_session_title(user_message),
                        },
                        "$set": {"updated_at": utc_now},
                        "$inc": {"message_count": 2},
                        "$push": {
                            "messages": {
                                "$each": [
                                    {"sender": "user", "text": user_message, "timestamp": utc_now},
                                    {
                                        "sender": "buddy",
                                        "text": response_payload.get("motivational_reply", ""),
                                        "timestamp": utc_now,
                                    },
                                ]
                            }
                        },
                    },
                    upsert=True,
                )
        except Exception as e:
            print(f"[DB_WARNING] Failed to save chat exchange (data will not persist): {e}")
            # Continue without raising - user still gets response, just not persisted

    @staticmethod
    def _build_session_title(user_message: str) -> str:
        title = user_message.replace("__trigger_diet_plan__", "Diet plan request")
        title = title.replace("__trigger_workout_plan__", "Workout plan request").strip()
        if not title:
            return "New chat"
        return title[:60] + ("..." if len(title) > 60 else "")

    @staticmethod
    async def get_recent_chats_for_serialization(user_id: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Retrieve recent chats for serialization into structured plans."""
        try:
            cursor = chats_col.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            docs.reverse()
            return docs
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to retrieve chats for serialization: {e}")
            raise

    @staticmethod
    async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user profile for context enrichment."""
        default_profile = {
            "user_id": user_id,
            "name": "User",
            "fitness_goal": "General Fitness",
            "activity_level": "Moderate",
            "age": 25,
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "daily_calorie_target": "N/A",
            "dietary_restrictions": "None",
            "preferences": "None",
        }
        try:
            from bson import ObjectId

            profile = None
            try:
                profile = await users_col.find_one({"_id": ObjectId(user_id)})
            except Exception:
                profile = await users_col.find_one({"user_id": user_id})

            if not profile:
                return default_profile

            return {
                "user_id": user_id,
                "name": profile.get("name", "User"),
                "fitness_goal": profile.get("fitness_goal") or "General Fitness",
                "activity_level": profile.get("activity_level") or "Moderate",
                "age": profile.get("age") or 25,
                "weight_kg": profile.get("weight_kg") or 70.0,
                "height_cm": profile.get("height_cm") or 175.0,
                "daily_calorie_target": profile.get("daily_calorie_target") or profile.get("target_calories") or "N/A",
                "dietary_restrictions": profile.get("dietary_restrictions") or profile.get("preferences_or_allergies") or "None",
                "preferences": profile.get("preferences") or "None",
            }
        except Exception as e:
            print(f"[DB_WARNING] Failed to retrieve user profile, using defaults: {e}")
            return default_profile

    @staticmethod
    async def pin_message(user_id: str, message_text: str, expiry_days: int = 15) -> None:
        """Pin a message to pinned_chats_col with TTL."""
        try:
            utc_now = datetime.datetime.utcnow()
            await pinned_chats_col.insert_one({
                "user_id": user_id,
                "pinned_at": utc_now,
                "expires_at": utc_now + datetime.timedelta(days=expiry_days),
                "message_text": message_text
            })
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to pin message: {e}")
            raise

    @staticmethod
    async def get_pinned_messages(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve all pinned messages for a user, most recent first."""
        try:
            cursor = pinned_chats_col.find({"user_id": user_id}).sort("pinned_at", -1)
            docs = await cursor.to_list(length=limit)
            return docs
        except PyMongoError as e:
            print(f"[DB_ERROR] Failed to retrieve pinned messages: {e}")
            raise
