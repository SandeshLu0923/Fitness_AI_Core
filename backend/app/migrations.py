"""
Database Migrations and Schema Updates
Handles restructuring and updates to MongoDB collections
"""

from app.database import (
    meals_col, chats_col, users_col, chat_sessions_col
)
from datetime import datetime
import pymongo


async def migrate_meals_collection():
    """
    Migrate meals collection to include detailed food breakdown with nutrition.
    Old structure: { user_id, meal_name, calories, timestamp }
    New structure: { user_id, meal_name, foods: [{food_name, quantity, unit, estimated_calories, protein_g, carbs_g, fats_g}], timestamp }
    """
    try:
        print("[MIGRATION] Starting meals collection restructure...")
        
        # Create index for user_id + timestamp for efficient queries
        await meals_col.create_index(
            [("user_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)],
            name="idx_meals_user_timestamp"
        )
        
        # Add foods array field to existing documents if missing
        await meals_col.update_many(
            {"foods": {"$exists": False}},
            {"$set": {"foods": []}}
        )
        
        print("[MIGRATION] Meals collection restructured successfully ✓")
        return True
    except Exception as e:
        print(f"[MIGRATION_ERROR] Meals restructure failed: {e}")
        return False


async def migrate_chats_collection():
    """
    Migrate chats to chat_sessions collection with recent 5 sessions per user.
    Old structure: chats_col with all historical messages
    New structure: chat_sessions_col with user_id and list of recent 5 sessions (each with messages)
    """
    try:
        print("[MIGRATION] Starting chat sessions restructure...")
        
        # Create index for efficient session queries
        await chat_sessions_col.create_index(
            [("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
            name="idx_sessions_user_time"
        )
        
        # Get all unique users from chats collection
        unique_users = await chats_col.distinct("user_id")
        
        for user_id in unique_users:
            # Get all chats for this user, sorted by timestamp DESC, limit to 5
            recent_chats = await chats_col.find(
                {"user_id": user_id}
            ).sort("timestamp", pymongo.DESCENDING).limit(5).to_list(length=5)
            
            if recent_chats:
                # Create a session document with these chats
                session_doc = {
                    "user_id": user_id,
                    "messages": recent_chats,
                    "created_at": datetime.utcnow(),
                    "message_count": len(recent_chats)
                }
                
                # Upsert the session
                await chat_sessions_col.update_one(
                    {"user_id": user_id},
                    {"$set": session_doc},
                    upsert=True
                )
        
        print(f"[MIGRATION] Chat sessions created for {len(unique_users)} users ✓")
        return True
    except Exception as e:
        print(f"[MIGRATION_ERROR] Chat sessions restructure failed: {e}")
        return False


async def migrate_users_collection():
    """
    Ensure users collection has location fields (latitude, longitude).
    Add indexes for efficient queries.
    """
    try:
        print("[MIGRATION] Validating users collection structure...")
        
        # Ensure location fields exist
        await users_col.update_many(
            {"latitude": {"$exists": False}},
            {"$set": {"latitude": 0.0, "longitude": 0.0}}
        )
        
        # Create geospatial index for location queries
        try:
            await users_col.create_index(
                [("location", pymongo.GEOSPHERE)],
                name="idx_user_location_geospatial"
            )
            print("[MIGRATION] Geospatial index created ✓")
        except Exception as geo_err:
            # Index might already exist with same or different name
            if "already exists" in str(geo_err).lower():
                print(f"[MIGRATION] Geospatial index already exists ✓")
            else:
                print(f"[MIGRATION] Geospatial index creation warning: {geo_err}")
        
        print("[MIGRATION] Users collection validated ✓")
        return True
    except Exception as e:
        print(f"[MIGRATION_ERROR] Users restructure failed: {e}")
        return False


async def run_all_migrations():
    """Run all database migrations on startup."""
    try:
        print("\n[MIGRATIONS] Starting database schema updates...\n")
        
        results = []
        results.append(await migrate_meals_collection())
        results.append(await migrate_chats_collection())
        results.append(await migrate_users_collection())
        
        if all(results):
            print("\n[MIGRATIONS] All migrations completed successfully ✓\n")
            return True
        else:
            print("\n[MIGRATIONS] Some migrations failed - see errors above\n")
            return False
            
    except Exception as e:
        print(f"\n[MIGRATIONS_ERROR] Migration suite failed: {e}\n")
        return False
