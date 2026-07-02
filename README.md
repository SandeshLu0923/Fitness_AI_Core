# Fitness AI Core

Fitness AI Core is an AI-powered gym and fitness assistant that combines conversational coaching, workout and diet planning, vision-based exercise tracking, gym discovery, nutrition intake tracking, reports, notifications, and admin analytics.

## Features

- AI gym buddy chat with session-specific memory, pinned chats, recent sessions, workout/diet plan handling, and motivational guidance.
- AI diet coach with structured day-wise diet plans, grocery lists, and dashboard nutrition intake logging.
- AI workout planner with active 7-day plans, date-aware scheduling, skipped-day shifting, daily challenges, weekly/monthly progress, and goal plans.
- Vision-based trainer for five supported exercises: squats, pushups, pullups, jumping jacks, and situps.
- Synthetic phase models for exercise tracking with `UP`, `MID`, `DOWN`, and `INVALID` phases.
- Nearby gym finder using city search and user location.
- User/admin authentication with separate user and admin database boundaries.
- Admin dashboard with active users, inference volume, latency, feature usage, behavioral predictions, and API metrics.

## Tech Stack

Backend:
- FastAPI
- MongoDB / Motor / PyMongo
- Groq LLM API
- MediaPipe
- OpenCV
- scikit-learn / joblib

Frontend:
- React
- TypeScript
- Vite
- Tailwind CSS
- Lucide icons
- Axios

## Project Structure

```text
backend/
  app/
    modules/          # OpenCV trainer, UI sidebar, workout utilities
    repositories/     # Database access layer
    routers/          # FastAPI routes
    scripts/          # Training and utility scripts
    services/         # Business logic and AI services
    database.py       # MongoDB collections and startup setup
    main.py           # FastAPI app entrypoint
frontend/
  src/
    components/       # Dashboard, chat, diet, gym, history, admin UI
    api/              # Frontend API helpers
docs/                 # Removed during cleanup; see comprehensive report
```

## Environment

Create backend environment values in `backend/.env`:

```env
MONGODB_URL=mongodb://localhost:27017
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.1-8b-instant
JWT_SECRET_KEY=replace_with_secure_secret
```

Frontend environment can use:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Setup

Backend:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Build frontend:

```powershell
cd frontend
npm.cmd run build
```

## Exercise Tracking

The current production-supported tracker scope is five exercises:

- Squat
- Pushup
- Pullup
- Jumping jack
- Situp

The tracker uses:

- MediaPipe pose landmarks
- Synthetic exercise phase classifiers
- legacy pose-state fallback classifier
- exercise-specific geometry fallback
- state-machine rep counting

The synthetic phase model artifact is:

```text
backend/app/exercise_phase_models.joblib
```

To retrain:

```powershell
$env:PYTHONPATH='backend'
python -m app.scripts.train_exercise_phase_models
```

## Common Commands

Compile backend files:

```powershell
python -m py_compile backend/app/main.py backend/app/modules/trainer_engine.py
```

Run frontend type/build check:

```powershell
cd frontend
npm.cmd run build
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

## Notes

- OpenCV desktop trainer is desktop-only. Browser/mobile pose tracking would require a separate browser-based MediaPipe implementation.
- The five-exercise model is the supported scope. Additional exercises should be added only after collecting or generating validated landmark sequences.
- Admin collections are stored separately in the admin database.
- Hot polling endpoints are excluded from API metrics to reduce unnecessary metric/log volume.

## Full Report

See [COMPREHENSIVE_PROJECT_REPORT.md](COMPREHENSIVE_PROJECT_REPORT.md) for architecture, feature status, implementation notes, model details, limitations, and roadmap.
