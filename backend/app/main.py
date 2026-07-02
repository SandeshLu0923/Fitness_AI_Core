import datetime
import time
import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import HOST, PORT
from app.routers import dietician, gym_buddy, profile, habit_tracker, recommender, gym_trainer, plans, auth, performance, form_analysis, admin
from app.database import init_db_indexes
from app.migrations import run_all_migrations

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "http://localhost:5177",
    "http://127.0.0.1:5177",
]

app = FastAPI(
    title="Fitness Companion API Base",
    description="Backend routing engine powering AI Pose estimation and fitness advice.",
    version="1.0.0"
)


def _apply_cors_headers(request: Request, response: JSONResponse):
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.on_event("startup")
async def startup_event():
    """Verify database connection and initialize indexes."""
    try:
        # Initialize database connection (lazy loading)
        from app.database import get_db
        await get_db()
        print("[DATABASE] MongoDB connection verified ✓")
        
        # Initialize indexes
        await init_db_indexes()
        
        # Run database migrations
        await run_all_migrations()
        print("[STARTUP] Application startup complete ✓")
        
    except Exception as e:
        print(f"[STARTUP_ERROR] Failed to initialize database: {e}")
        print("[WARNING] Application starting but database operations may fail")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🛠️ FIXED: CATCH-ALL MIDDLEWARE SANITIZED TO PREVENT STREAM BUFFERING
@app.middleware("http")
async def record_api_metrics(request: Request, call_next):
    noisy_metric_paths = (
        "/api/gym-trainer/latest-stats/",
        "/api/gym-trainer/completed-workouts/",
        "/api/dietician/nutrition-summary/",
        "/api/habit-tracker/active-day-plan",
    )
    should_record_metric = not any(request.url.path.startswith(path) for path in noisy_metric_paths)
    start_time = time.perf_counter()
    status_code = 500
    error_message = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        error_message = str(exc)
        raise
    finally:
        if should_record_metric:
            try:
                from app.database import api_metrics_col
                await api_metrics_col.insert_one({
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
                    "error": error_message,
                    "timestamp": datetime.datetime.utcnow(),
                })
            except Exception as metrics_error:
                print(f"[METRICS_WARNING] Failed to record API metric: {metrics_error}")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # If the request is a streaming chat, bypass the intercept block to stream instantly
    if "/api/gym-buddy/chat" in request.url.path:
        return await call_next(request)
        
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        print(f"[💥 CRITICAL_CRASH] Server exception on {request.url.path}: {str(e)}")
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal Processing Exception", "details": str(e)}
        )
        return _apply_cors_headers(request, response)

for router in (
    auth.router,
    profile.router,
    dietician.router,
    habit_tracker.router,
    recommender.router,
    gym_buddy.router,
    gym_trainer.router,
    plans.router,
    performance.router,
    form_analysis.router,
    admin.router,
):
    app.include_router(router)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    response = JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": str(exc.detail)}
    )
    return _apply_cors_headers(request, response)

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    print(f"[UNHANDLED_EXCEPTION] {request.method} {request.url.path}: {exc}")
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"status": "error", "message": "Internal server error"}
    )
    return _apply_cors_headers(request, response)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    print(f"[SERVER_START] Deploying environment tracker domain onto http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
