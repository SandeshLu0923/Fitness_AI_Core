import os
import datetime
import pymongo
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGODB_URL
import ssl

# Initialize client and db as None - will be set on first use
_client = None
_db = None
_admin_db = None

async def get_db():
    """Get or create database connection (lazy loading)."""
    global _client, _db, _admin_db
    
    if _db is None:
        try:
            _client = AsyncIOMotorClient(
                MONGODB_URL,
                tlsInsecure=True,
                serverSelectionTimeoutMS=5000,
                socketTimeoutMS=10000,
                connectTimeoutMS=10000,
                retryWrites=False
            )
            _db = _client.fitness_ai
            _admin_db = _client.fitness_ai_admin
            # Test connection
            await _db.command('ping')
            await _admin_db.command('ping')
            print("[DB] Connected to MongoDB successfully")
        except Exception as e:
            print(f"[DB_ERROR] Failed to connect to MongoDB: {e}")
            raise
    
    return _db

# Lazy-loaded db reference (will be set on first use)
db = None

# For synchronous access, create a placeholder
class LazyDB:
    """Lazy-loaded database access."""
    
    @property
    def users(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.users

    @property
    def admin_users(self):
        if _admin_db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _admin_db.admin_users
    
    @property
    def meals(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.meals
    
    @property
    def chats(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.chats
    
    @property
    def exercise_logs(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.exercise_logs
    
    @property
    def gyms(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.gyms
    
    @property
    def completed_challenges(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.completed_challenges
    
    @property
    def pinned_chats(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.pinned_chats
    
    @property
    def diet_plans(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.diet_plans
    
    @property
    def workout_plans(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.workout_plans
    
    @property
    def chat_sessions(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.chat_sessions

    @property
    def weekly_summaries(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.weekly_summaries

    @property
    def monthly_summaries(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.monthly_summaries

    @property
    def api_metrics(self):
        if _admin_db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _admin_db.api_metrics

    @property
    def ai_inference_logs(self):
        if _admin_db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _admin_db.ai_inference_logs

    @property
    def user_activity_logs(self):
        if _admin_db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _admin_db.user_activity_logs

    @property
    def mood_logs(self):
        if _db is None:
            raise RuntimeError("Database not initialized. Call get_db() first in async context.")
        return _db.mood_logs

db = LazyDB()

# For backwards compatibility, export collection references
# These will work once database is initialized
def get_users_col():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db.users

def get_admin_users_col():
    if _admin_db is None:
        raise RuntimeError("Database not initialized")
    return _admin_db.admin_users

def get_chats_col():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db.chats

def get_pinned_chats_col():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db.pinned_chats

def get_meals_col():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db.meals

def get_exercise_logs_col():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db.exercise_logs

def get_gyms_col():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db.gyms

def get_completed_challenges_col():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db.completed_challenges

def get_diet_plans_col():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db.diet_plans

def get_workout_plans_col():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db.workout_plans

# Direct references for backwards compatibility (will be lazy-initialized)
class _DirectCollectionRef:
    """Lazy collection reference that initializes on first access."""
    def __init__(self, collection_name):
        self.collection_name = collection_name
        self._collection = None
    
    def __getattr__(self, name):
        if _db is None:
            raise RuntimeError("Database not initialized. Ensure FastAPI app has called lifespan startup.")
        if self._collection is None:
            self._collection = getattr(_db, self.collection_name)
        return getattr(self._collection, name)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass


class _AdminCollectionRef(_DirectCollectionRef):
    """Lazy collection reference for the separate admin database."""

    def __getattr__(self, name):
        if _admin_db is None:
            raise RuntimeError("Admin database not initialized. Ensure FastAPI app has called lifespan startup.")
        if self._collection is None:
            self._collection = getattr(_admin_db, self.collection_name)
        return getattr(self._collection, name)

# Export lazy collection references for backwards compatibility
users_col = _DirectCollectionRef('users')
admin_users_col = _AdminCollectionRef('admin_users')
chats_col = _DirectCollectionRef('chats')
chat_sessions_col = _DirectCollectionRef('chat_sessions')
pinned_chats_col = _DirectCollectionRef('pinned_chats')
meals_col = _DirectCollectionRef('meals')
exercise_logs_col = _DirectCollectionRef('exercise_logs')
gyms_col = _DirectCollectionRef('gyms')
completed_challenges_col = _DirectCollectionRef('completed_challenges')
diet_plans_col = _DirectCollectionRef('diet_plans')
workout_plans_col = _DirectCollectionRef('workout_plans')
weekly_summaries_col = _DirectCollectionRef('weekly_summaries')
monthly_summaries_col = _DirectCollectionRef('monthly_summaries')
api_metrics_col = _AdminCollectionRef('api_metrics')
ai_inference_logs_col = _AdminCollectionRef('ai_inference_logs')
user_activity_logs_col = _AdminCollectionRef('user_activity_logs')
mood_logs_col = _DirectCollectionRef('mood_logs')

# ==========================================================================
# ⚡ OPTION 3: AUTOMATED ON-BOOT DATABASE INDEX INITIALIZER 
# ==========================================================================
async def init_db_indexes():
    """
    Executes automatically on application startup to build strategic indices,
    permanently removing backend database scan lag and handling 7-day TTL purges.
    """
    print("\n[DATABASE_INIT] Verifying background performance indices...")
    try:
        # 1. Optimize Chat Companion pipeline and clear 3-chat processing lag
        try:
            await chats_col.create_index(
                [("user_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)],
                name="idx_user_chat_history"
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_user_chat_history already exists, skipping...")
            else:
                raise
        
        # 2. Optimize ML inference history tracking query data streams
        try:
            await exercise_logs_col.create_index(
                [("user_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)],
                name="idx_user_exercise_telemetry"
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_user_exercise_telemetry already exists, skipping...")
            else:
                raise
        
        # 3. Automated 7-Day TTL Expiration Indexing for pinned chats
        # MongoDB background daemon worker thread auto-deletes nodes when expires_at passes
        try:
            # First, try to drop the old index if it exists
            try:
                await pinned_chats_col.drop_index("idx_pinned_chats_15day_ttl")
                print("[DATABASE_INIT] Dropped old TTL index idx_pinned_chats_15day_ttl")
            except pymongo.errors.OperationFailure:
                pass  # Index doesn't exist, continue
            
            await pinned_chats_col.create_index(
                [("expires_at", pymongo.ASCENDING)],
                expireAfterSeconds=0,
                name="idx_pinned_chats_7day_ttl"
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_pinned_chats_7day_ttl already exists, skipping...")
            else:
                raise
        
        # 4. Optimize diet plans lookup by user
        try:
            await diet_plans_col.create_index(
                [("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
                name="idx_user_diet_plans"
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_user_diet_plans already exists, skipping...")
            else:
                raise
        
        # 5. Optimize workout plans lookup by user
        try:
            await workout_plans_col.create_index(
                [("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
                name="idx_user_workout_plans"
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_user_workout_plans already exists, skipping...")
            else:
                raise
        
        # 5. Add geospatial index for user location (for nearby gyms)
        try:
            await users_col.create_index(
                [("location", pymongo.GEOSPHERE)],
                name="idx_user_location_geospatial"
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_user_location_geospatial already exists, skipping...")
            else:
                pass  # Geospatial index may not be critical, continue

        # 6. Compact workout reports for history UI and chat context
        try:
            await weekly_summaries_col.create_index(
                [("user_id", pymongo.ASCENDING), ("week_start", pymongo.DESCENDING)],
                name="idx_user_weekly_summaries",
                unique=True
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_user_weekly_summaries already exists, skipping...")
            else:
                raise

        await _migrate_admin_collections_to_admin_db()

        try:
            await admin_users_col.create_index(
                [("email", pymongo.ASCENDING)],
                unique=True,
                name="idx_admin_users_email_unique"
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_admin_users_email_unique already exists, skipping...")
            else:
                raise

        await _ensure_default_admin_user()

        try:
            await monthly_summaries_col.create_index(
                [("user_id", pymongo.ASCENDING), ("month", pymongo.DESCENDING)],
                name="idx_user_monthly_summaries",
                unique=True
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_user_monthly_summaries already exists, skipping...")
            else:
                raise

        for collection, index_name in (
            (api_metrics_col, "idx_api_metrics_timestamp"),
            (ai_inference_logs_col, "idx_ai_inference_timestamp"),
            (user_activity_logs_col, "idx_user_activity_timestamp"),
            (mood_logs_col, "idx_mood_logs_timestamp"),
        ):
            try:
                await collection.create_index(
                    [("timestamp", pymongo.DESCENDING)],
                    name=index_name
                )
            except pymongo.errors.OperationFailure as e:
                if "already exists" in str(e):
                    print(f"[DATABASE_INIT] Index {index_name} already exists, skipping...")
                else:
                    raise

        try:
            await user_activity_logs_col.create_index(
                [("user_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)],
                name="idx_user_activity_user_timestamp"
            )
        except pymongo.errors.OperationFailure as e:
            if "already exists" in str(e):
                print("[DATABASE_INIT] Index idx_user_activity_user_timestamp already exists, skipping...")
            else:
                raise
        
        print("[DATABASE_INIT] All indices successfully verified and compiled error-free!\n")
    except Exception as e:
        print(f"[DATABASE_INIT_ERROR] Background indexing configuration failed: {str(e)}\n")


async def _ensure_default_admin_user():
    """Seed a separate admin account for the admin dashboard."""
    admin_email = os.getenv("ADMIN_EMAIL", "admin@fitness.ai").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin@12345")
    admin_name = os.getenv("ADMIN_NAME", "Admin")
    if not admin_email or not admin_password:
        return

    existing = await admin_users_col.find_one({"email": admin_email})
    if existing:
        return

    password_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
    await admin_users_col.insert_one({
        "name": admin_name,
        "email": admin_email,
        "password_hash": password_hash,
        "role": "admin",
        "is_active": True,
        "created_at": datetime.datetime.utcnow(),
        "updated_at": datetime.datetime.utcnow(),
    })
    print(f"[DATABASE_INIT] Seeded default admin user: {admin_email}")


async def _migrate_admin_collections_to_admin_db():
    """Move admin-only collections out of the user application database."""
    if _db is None or _admin_db is None:
        return

    admin_collection_names = (
        "admin_users",
        "api_metrics",
        "ai_inference_logs",
        "user_activity_logs",
    )

    existing_user_collections = set(await _db.list_collection_names())
    for collection_name in admin_collection_names:
        if collection_name not in existing_user_collections:
            continue

        source = _db[collection_name]
        target = _admin_db[collection_name]
        moved_count = 0
        cursor = source.find({})

        async for document in cursor:
            try:
                await target.replace_one({"_id": document["_id"]}, document, upsert=True)
                moved_count += 1
            except pymongo.errors.DuplicateKeyError:
                # Same admin email may already exist in the admin DB under a different _id.
                continue

        await source.drop()
        print(f"[DATABASE_MIGRATION] Moved {moved_count} docs from fitness_ai.{collection_name} to fitness_ai_admin.{collection_name} and dropped old collection.")
