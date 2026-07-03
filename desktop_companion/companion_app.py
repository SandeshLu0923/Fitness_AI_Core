import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from app.routers import gym_trainer

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://fitness-ai-core.vercel.app",
]

extra_origin = os.getenv("FITNESS_AI_WEB_ORIGIN")
if extra_origin:
    ALLOWED_ORIGINS.append(extra_origin)

app = FastAPI(
    title="Fitness AI Desktop Tracker Companion",
    description="Local webcam tracker service for Fitness AI Core.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gym_trainer.router)


@app.on_event("startup")
async def startup_event():
    print("[COMPANION] Desktop tracker companion is ready.")


@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Fitness AI Desktop Tracker Companion",
        "tracker": "opencv-mediapipe",
    }
