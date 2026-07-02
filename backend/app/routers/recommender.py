"""
Router Layer: Recommender Endpoints
FastAPI routes for gym search and recommendations.
"""

from typing import List
from fastapi import APIRouter
from pydantic import BaseModel


# ============================================================================
# Request/Response Models
# ============================================================================
class GymFacility(BaseModel):
    name: str
    locality: str
    address: str
    rating: float
    distance_km: float
    website: str
    phone: str


class RecommendationResponse(BaseModel):
    total_found: int
    recommended_gyms: List[GymFacility]


class RecommendationRequest(BaseModel):
    latitude: float
    longitude: float
    search_radius_km: float = 10.0


# ============================================================================
# Router Setup
# ============================================================================
router = APIRouter(prefix="/api/recommender", tags=["Gym Recommender"])

_service_cache = None
def get_service():
    global _service_cache
    if _service_cache is None:
        from app.services.recommender_service import RecommenderService
        _service_cache = RecommenderService()
    return _service_cache


# ============================================================================
# Endpoints
# ============================================================================
@router.post("/explore-gyms", response_model=RecommendationResponse)
async def explore_fitness_recommendations(payload: RecommendationRequest):
    """Find nearby gyms within search radius, sorted by distance."""
    try:
        service = get_service()
        nearby_gyms = await service.find_nearby_gyms(
            payload.latitude,
            payload.longitude,
            payload.search_radius_km
        )

        return RecommendationResponse(
            total_found=len(nearby_gyms),
            recommended_gyms=nearby_gyms
        )

    except Exception as e:
        print(f"[ERROR] Gym exploration failed: {e}")
        raise
