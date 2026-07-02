# Fitness AI Core - Comprehensive Project Report

## 1. Project Overview

Fitness AI Core is a unified AI fitness assistant for personal training, nutrition, habit tracking, gym discovery, and conversational coaching. The system combines a React dashboard, FastAPI backend, MongoDB persistence, Groq-powered chat/planning, and OpenCV/MediaPipe exercise tracking.

The current implementation focuses on:

- personalized workout and diet planning
- conversational AI fitness companion
- day-wise plans and progress tracking
- nutrition intake logging
- five-exercise vision tracking
- nearby gym search
- user/admin dashboard separation
- admin KPIs and analytics

IoT/smart gym integration is intentionally out of scope.

## 2. Current Feature Status

### Implemented

- User registration/login with role-aware user/admin flow.
- Admin login and admin-only dashboard.
- Separate user and admin database collections.
- AI chat companion with session-specific history.
- Recent chat sessions and pinned chat handling.
- Workout plan generation, update, and active-plan replacement.
- Diet plan generation and day-wise display.
- Grocery list section for diet plans.
- Dashboard nutrition intake summary and meal logging.
- Weekly and monthly workout history summaries.
- Date-aware workout and diet plan starts.
- Skipped-day workout shifting.
- Daily challenge activation and completed challenge tracking.
- Nearby gym search by city and user location.
- Fitness tracker desktop window using OpenCV and MediaPipe.
- Five supported exercise tracker scope: squats, pushups, pullups, jumping jacks, situps.
- Synthetic exercise phase models for `UP`, `MID`, `DOWN`, `INVALID`.
- Admin KPI and chart data endpoints.
- Backend request log reduction and polling metric filtering.

### Partially Implemented / Needs Future Work

- Production-grade form correction for all five supported exercises.
- Mobile/browser-based pose tracking.
- Full real-world dataset collection from user sessions.
- More robust sequence models for rep counting.
- Real-time performance profiling in the trainer window.
- Fine-grained admin charts with richer visualization polish.

## 3. Architecture

### Backend

Pattern:

```text
Router -> Service -> Repository -> Database
```

Main areas:

- `routers/`: HTTP route definitions.
- `services/`: business logic, LLM orchestration, analytics, profile handling.
- `repositories/`: MongoDB data access.
- `modules/`: OpenCV trainer engine, trainer UI, workout utilities.
- `scripts/`: model training and utility scripts.
- `database.py`: database clients, collection references, indexes, migration helpers.

### Frontend

The frontend is a React/Vite application organized by feature components:

- Dashboard
- AI chat trainer
- Workout history
- Diet plans
- Find gym
- Challenges
- Settings
- Admin dashboard

Authentication state is held in `sessionStorage` to avoid cross-browser/window role leakage.

## 4. Database Design

User database stores user-facing app data:

- users
- chats
- chat_sessions
- pinned_chats
- workout_plans
- diet_plans
- exercise_logs
- meals
- mood_logs
- gyms
- weekly_summaries
- monthly_summaries
- completed_challenges

Admin database stores admin-only operational data:

- admin_users
- api_metrics
- ai_inference_logs
- user_activity_logs

Legacy admin collections were migrated out of the user database.

## 5. AI Chat Model Behavior

The chat model is designed to act as a professional assistant and gym companion, not only a plan generator.

Supported behavior:

- normal fitness conversation without fetching large plan data
- workout/diet plan context only when the user asks for plan-related data
- current-day workout/diet fetches
- new plan generation with user approval
- plan update handling
- session-local memory
- pinned and recent chat handling

This reduces unnecessary prompt size and helps avoid large request payload errors.

## 6. Workout Planning

Workout plans are date-aware. A plan created today starts from today's weekday/date, not from Monday by default.

Implemented behaviors:

- active plan replacement rather than storing many stale active plans
- current day workout display on dashboard
- remaining-day modification when user updates plan midway
- skipped-day shifting into the next available/rest slot
- completed workout movement from today's active section to completed section
- weekly/monthly workout summaries

## 7. Diet Planning and Nutrition

Diet plans are displayed in a day-wise structured format with grocery list as a separate view.

Implemented behaviors:

- current day diet display
- day-wise diet plan navigation
- grocery list section
- dashboard nutrition intake summary
- meal logging by text input
- "followed today's diet plan" shortcut

Nutrition intake uses meal logs and estimated nutrition from user input or the active diet plan.

## 8. Vision-Based Exercise Tracking

### Supported Exercises

The current official tracking scope is:

- squats
- pushups
- pullups
- jumping jacks
- situps

Other exercises should not be considered model-supported yet.

### Current Pipeline

```text
Camera frame
-> MediaPipe landmarks
-> feature extraction
-> synthetic phase model
-> legacy pose-state fallback
-> geometry fallback
-> state-machine rep counter
-> live stats persistence
-> dashboard progress
```

### Synthetic Phase Models

The synthetic phase model artifact is:

```text
backend/app/exercise_phase_models.joblib
```

Training script:

```text
backend/app/scripts/train_exercise_phase_models.py
```

The model creates synthetic samples from the existing five-exercise landmark dataset:

- mirrored landmarks
- jittered landmarks
- interpolated `MID` poses
- invalid samples from other exercises

Classes:

- `UP`
- `MID`
- `DOWN`
- `INVALID`

Current trained holdout accuracy:

- Squat: about 93.5%
- Pushup: about 95.3%
- Pullup: about 88.9%
- Jumping jacks: about 94.7%
- Situp: about 94.2%

### Performance Notes

The tracker window remains portrait, but MediaPipe runs on a smaller internal portrait frame to reduce lag. Pose detection still runs every frame to preserve rep accuracy. Hand detection for shutdown runs less frequently because it does not need frame-level precision.

The largest remaining bottleneck is MediaPipe pose inference on CPU.

## 9. Admin Dashboard

Implemented admin dashboard concepts:

- total active users
- AI inference volume
- model accuracy proxy
- backend latency
- retention
- peak activity hours
- error rate
- user growth trend
- feature distribution
- server load
- behavioral prediction trends
- API response time distribution

High-frequency polling endpoints are excluded from metrics logging to avoid noisy admin metrics.

## 10. Known Limitations

- OpenCV tracker is desktop-only.
- Pullup phase model has the lowest accuracy among the five supported exercises.
- Synthetic data improves robustness but does not replace real user video/landmark sequences.
- Full form correction requires more labeled bad-form data.
- Browser/mobile pose tracking requires a separate frontend MediaPipe implementation.
- Current tracker supports only five exercises officially.

## 11. Recommended Roadmap

### Short Term

- Stabilize the five supported exercise trackers.
- Add visual confidence/debug display in trainer window.
- Add test sequences for each supported exercise.
- Collect real landmark sessions from users.

### Medium Term

- Add real sequence-level labels:
  - rep start
  - rep end
  - valid/invalid rep
  - form issue
- Train sequence-aware models.
- Improve pullup dataset coverage.
- Add bad-form classifiers for the five supported exercises.

### Long Term

- Add browser-based pose tracking for mobile.
- Expand exercise support only after collecting data.
- Add model monitoring and user verification feedback.
- Introduce lighter sequence models or temporal CNN/LSTM models.

## 12. Verification Commands

Backend compile:

```powershell
python -m py_compile backend/app/main.py backend/app/modules/trainer_engine.py backend/app/scripts/train_exercise_phase_models.py
```

Frontend build:

```powershell
cd frontend
npm.cmd run build
```

Retrain exercise phase models:

```powershell
$env:PYTHONPATH='backend'
python -m app.scripts.train_exercise_phase_models
```

## 13. Final Status

The project is now consolidated around:

- one README
- one comprehensive report
- active source files
- trained model artifacts

The old phase/fix/audit Markdown files were removed to reduce confusion and keep documentation maintainable.
