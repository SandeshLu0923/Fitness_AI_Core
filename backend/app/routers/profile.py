"""
Router Layer: Profile Endpoints
FastAPI routes for user profile management.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError


# ============================================================================
# Request/Response Models
# ============================================================================
class UserProfile(BaseModel):
    user_id: str
    age: int = Field(default=25, gt=0)
    weight_kg: float = Field(default=70.0, gt=0)
    height_cm: float = Field(default=175.0, gt=0)
    fitness_goal: str = Field(default="General Fitness")
    activity_level: str = Field(default="Moderate")
    latitude: float = Field(default=0.0, description="User location latitude")
    longitude: float = Field(default=0.0, description="User location longitude")


# ============================================================================
# Router Setup
# ============================================================================
router = APIRouter(prefix="/api/profile", tags=["Profile Management"])

_service_cache = None
def get_service():
    global _service_cache
    if _service_cache is None:
        from app.services.profile_service import ProfileService
        _service_cache = ProfileService()
    return _service_cache


# ============================================================================
# Endpoints
# ============================================================================
@router.post("/upsert", status_code=status.HTTP_200_OK)
async def upsert_profile(profile: UserProfile):
    """Create or update user profile."""
    try:
        service = get_service()
        result = await service.create_or_update_profile(profile.user_id, profile)
        return result

    except PyMongoError as e:
        print(f"[DB_ERROR] Failed to upsert profile: {e}")
        raise HTTPException(status_code=500, detail="Database write failed while updating profile.")
    except Exception as e:
        print(f"[ERROR] Profile upsert failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to update profile at this time.")


@router.get("/{user_id}", response_model=UserProfile)
async def get_profile(user_id: str):
    """Retrieve user profile."""
    try:
        service = get_service()
        profile_data = await service.get_profile(user_id, UserProfile)
        
        # Ensure required fields have defaults if missing
        if profile_data.age is None:
            profile_data.age = 25
        if profile_data.weight_kg is None:
            profile_data.weight_kg = 70.0
        if profile_data.height_cm is None:
            profile_data.height_cm = 175.0
        if profile_data.fitness_goal is None or profile_data.fitness_goal == "":
            profile_data.fitness_goal = "General Fitness"
        if profile_data.activity_level is None or profile_data.activity_level == "":
            profile_data.activity_level = "Moderate"
            
        return profile_data

    except ValueError as e:
        print(f"[ERROR] Profile not found: {e}")
        raise HTTPException(status_code=404, detail="User profile not found.")
    except PyMongoError as e:
        print(f"[DB_ERROR] Failed to retrieve profile: {e}")
        raise HTTPException(status_code=500, detail="Database query failed.")
    except Exception as e:
        print(f"[ERROR] Profile retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to load profile at this time.")
