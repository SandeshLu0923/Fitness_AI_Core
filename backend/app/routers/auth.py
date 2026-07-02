"""
Router Layer: Authentication Endpoints
FastAPI routes for user registration, login, and token management.
"""

import datetime
import os
from fastapi import APIRouter, HTTPException, status, Depends, Header
from pydantic import BaseModel
import jwt
import bcrypt
from typing import Optional

# ============================================================================
# Configuration
# ============================================================================
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRY_DAYS = 30

# ============================================================================
# Request/Response Models
# ============================================================================
class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: str
    name: str
    email: str
    role: str = "user"


class UserData(BaseModel):
    age: int
    weight_kg: float
    height_cm: float
    latitude: float = 0.0
    longitude: float = 0.0


class UpdateProfileRequest(BaseModel):
    age: int
    weight_kg: float
    height_cm: float
    latitude: float = 0.0
    longitude: float = 0.0


# ============================================================================
# Router Setup
# ============================================================================
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

_repo_cache = None
def get_repo():
    global _repo_cache
    if _repo_cache is None:
        from app.repositories.users_repo import UsersRepository
        _repo_cache = UsersRepository()
    return _repo_cache


# ============================================================================
# Helper Functions
# ============================================================================
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        # Handle both string and bytes for hashed password
        if isinstance(hashed, bytes):
            hash_bytes = hashed
        else:
            hash_bytes = hashed.encode()
        return bcrypt.checkpw(password.encode(), hash_bytes)
    except Exception as e:
        print(f"[PASSWORD_VERIFY_ERROR] {e}")
        return False


def create_token(user_id: str, email: str, role: str = "user") -> str:
    """Create a JWT token."""
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=TOKEN_EXPIRY_DAYS),
        "iat": datetime.datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(authorization: Optional[str] = Header(None)) -> dict:
    """Verify and decode a JWT token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        # Extract token from "Bearer <token>"
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")
        
        payload = jwt.decode(credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Invalid token")


# ============================================================================
# Endpoints
# ============================================================================
@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """Register a new user account."""
    try:
        # Check if user already exists
        repo = get_repo()
        existing = await repo.get_user_by_email(request.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password
        hashed_password = hash_password(request.password)

        # Create user
        user_id = await repo.create_user(
            name=request.name,
            email=request.email,
            password_hash=hashed_password
        )

        # AUTO-CREATE DEFAULT PROFILE for new user (fixes Issue #5)
        try:
            from app.repositories.profile_repo import ProfileRepository
            default_profile_data = {
                "age": 25,
                "weight_kg": 70.0,
                "height_cm": 175.0,
                "fitness_goal": "General Fitness",
                "activity_level": "Moderate",
                "latitude": 13.0827,
                "longitude": 80.2707,
                "profile_completed": True
            }
            await ProfileRepository.upsert_profile(user_id, default_profile_data)
            print(f"[PROFILE_CREATED] Auto-created default profile for user: {user_id}")
        except Exception as profile_err:
            print(f"[PROFILE_WARNING] Could not auto-create profile: {profile_err}")
            # Don't fail registration if profile creation fails

        # Create token
        token = create_token(user_id, request.email)
        try:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_user_activity(user_id, "register", {"email": request.email})
        except Exception as activity_error:
            print(f"[ACTIVITY_WARNING] Registration activity not logged: {activity_error}")

        return LoginResponse(
            token=token,
            user_id=user_id,
            name=request.name,
            email=request.email,
            role="user"
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[AUTH_ERROR] Registration failed: {e}")
        print(f"[AUTH_ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return token."""
    try:
        # Find user by email
        repo = get_repo()
        user = await repo.get_user_by_email(request.email)
        if not user:
            print(f"[LOGIN] User not found for email: {request.email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password
        print(f"[LOGIN] Verifying password for {request.email}")
        
        if not verify_password(request.password, user["password_hash"]):
            print(f"[LOGIN] Password verification failed for {request.email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Create token
        user_id_str = str(user["_id"])
        token = create_token(user_id_str, request.email)
        try:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_user_activity(user_id_str, "login", {"email": request.email})
        except Exception as activity_error:
            print(f"[ACTIVITY_WARNING] Login activity not logged: {activity_error}")

        return LoginResponse(
            token=token,
            user_id=user_id_str,
            name=user["name"],
            email=user["email"],
            role="user"
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH_ERROR] Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/profile/complete", status_code=status.HTTP_200_OK)
async def complete_profile(
    user_id: str,
    request: UpdateProfileRequest,
    authorization: Optional[str] = Header(None)
):
    """Complete user profile on first login."""
    try:
        # Verify token
        payload = verify_token(authorization)
        
        # Verify the token is for the correct user
        if payload["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Update user profile
        repo = get_repo()
        await repo.update_user_profile(
            user_id=user_id,
            age=request.age,
            weight_kg=request.weight_kg,
            height_cm=request.height_cm,
            latitude=request.latitude,
            longitude=request.longitude
        )

        return {"status": "success", "message": "Profile completed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH_ERROR] Profile completion failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete profile")


@router.get("/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current logged-in user info."""
    try:
        payload = verify_token(authorization)
        repo = get_repo()
        user = await repo.get_user_by_id(payload["user_id"])
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "user_id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "age": user.get("age"),
            "weight_kg": user.get("weight_kg"),
            "height_cm": user.get("height_cm"),
            "latitude": user.get("latitude", 0.0),
            "longitude": user.get("longitude", 0.0),
            "profile_completed": user.get("profile_completed", False)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH_ERROR] Failed to get current user: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user info")


@router.post("/admin/login", response_model=LoginResponse)
async def admin_login(request: LoginRequest):
    """Authenticate a separate admin account."""
    try:
        from app.database import admin_users_col

        admin = await admin_users_col.find_one({"email": request.email.strip().lower(), "role": "admin"})
        if not admin or not admin.get("is_active", True):
            raise HTTPException(status_code=401, detail="Invalid admin email or password")

        if not verify_password(request.password, admin["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid admin email or password")

        admin_id = str(admin["_id"])
        token = create_token(admin_id, admin["email"], role="admin")

        try:
            from app.services.analytics_service import AnalyticsService
            await AnalyticsService.log_user_activity(admin_id, "admin_login", {"email": admin["email"]})
        except Exception as activity_error:
            print(f"[ACTIVITY_WARNING] Admin login activity not logged: {activity_error}")

        return LoginResponse(
            token=token,
            user_id=admin_id,
            name=admin.get("name", "Admin"),
            email=admin["email"],
            role="admin"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH_ERROR] Admin login failed: {e}")
        raise HTTPException(status_code=500, detail="Admin login failed")


@router.get("/admin/me")
async def get_current_admin(authorization: Optional[str] = Header(None)):
    """Get current logged-in admin info."""
    try:
        from bson import ObjectId
        from app.database import admin_users_col

        payload = verify_token(authorization)
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        admin = await admin_users_col.find_one({"_id": ObjectId(payload["user_id"]), "role": "admin"})
        if not admin or not admin.get("is_active", True):
            raise HTTPException(status_code=404, detail="Admin not found")

        return {
            "user_id": str(admin["_id"]),
            "name": admin.get("name", "Admin"),
            "email": admin["email"],
            "role": "admin",
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH_ERROR] Failed to get current admin: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve admin info")
