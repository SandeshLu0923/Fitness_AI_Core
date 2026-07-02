"""
Service Layer: Recommender Business Logic
Manages gym search, distance calculation, and website resolution.
"""

import math
from typing import Dict, List, Any
from app.repositories.recommender_repo import RecommenderRepository


class RecommenderService:
    """Service for gym recommendation and location-based search."""

    def __init__(self):
        self.repo = RecommenderRepository()

    @staticmethod
    def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two GPS coordinates in km."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 2)

    async def find_nearby_gyms(self, latitude: float, longitude: float, search_radius_km: float = 10.0) -> List[Dict[str, Any]]:
        """
        Find gyms within search radius, sorted by distance.
        
        Args:
            latitude: User latitude
            longitude: User longitude
            search_radius_km: Search radius in kilometers
            
        Returns:
            List of nearby gyms with details, sorted by distance
        """
        try:
            all_gyms = await self.repo.get_all_gyms()
            nearby_gyms = []
            nearest_gyms = []

            for gym_doc in all_gyms:
                gym_lat = gym_doc.get("latitude")
                gym_lon = gym_doc.get("longitude")

                if gym_lat is None or gym_lon is None:
                    continue

                dist = self.calculate_haversine_distance(latitude, longitude, float(gym_lat), float(gym_lon))
                name = gym_doc.get("name", "Unknown Gym")
                locality = gym_doc.get("locality", "Local Area")
                gym_payload = {
                    "name": name,
                    "locality": locality,
                    "address": gym_doc.get("address", "N/A"),
                    "rating": float(gym_doc.get("rating", 0.0)),
                    "distance_km": dist,
                    "website": gym_doc.get("website", "Not Available"),
                    "phone": gym_doc.get("phone", "Not Available")
                }
                nearest_gyms.append(gym_payload)

                if dist <= search_radius_km:
                    nearby_gyms.append(gym_payload)

            nearby_gyms.sort(key=lambda x: x["distance_km"])
            if not nearby_gyms:
                nearest_gyms.sort(key=lambda x: x["distance_km"])
                return nearest_gyms[:10]
            return nearby_gyms

        except Exception as e:
            print(f"[ERROR] Failed to find nearby gyms: {e}")
            raise
