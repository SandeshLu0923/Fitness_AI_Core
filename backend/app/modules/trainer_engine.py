import os
import cv2
import datetime
import asyncio
import json
import threading
import time
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe import Image, ImageFormat
import numpy as np
import joblib
from groq import Groq
from pymongo import MongoClient
from app.config import GROQ_API_KEY, GROQ_MODEL, MONGODB_URL
from pymongo.errors import PyMongoError
from app.database import exercise_logs_col
from app.modules.trainer_utils import calculate_angle, WeeklyMacrocyclePlan
from app.modules.trainer_ui import construct_trainer_sidebar
from app.services.pose_state_features import extract_pose_state_features, mediapipe_landmarks_to_points

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "habit_model.joblib")
trained_classifier = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
POSE_STATE_MODEL_PATH = os.path.join(BASE_DIR, "pose_state_model.joblib")
pose_state_artifact = joblib.load(POSE_STATE_MODEL_PATH) if os.path.exists(POSE_STATE_MODEL_PATH) else None
pose_state_model = pose_state_artifact.get("model") if isinstance(pose_state_artifact, dict) else None
EXERCISE_PHASE_MODEL_PATH = os.path.join(BASE_DIR, "exercise_phase_models.joblib")
exercise_phase_artifact = joblib.load(EXERCISE_PHASE_MODEL_PATH) if os.path.exists(EXERCISE_PHASE_MODEL_PATH) else None
exercise_phase_models = exercise_phase_artifact.get("models", {}) if isinstance(exercise_phase_artifact, dict) else {}

# ==========================================================================
# BIOMETRIC CALCULATOR & MACROCYCLE GENERATION INFERENCE ENGINE
# ==========================================================================

def run_mifflin_st_jeor_calories(weight: float, height: float, age: int) -> float:
    return round(((10.0 * weight) + (6.25 * height) - (5.0 * age) + 5.0) * 1.375, 1)

def run_haskell_fox_max_hr(age: int) -> float:
    return float(220 - age)

def predict_skip_probability(bmi: float, max_hr: float, calories: float, hours: float, volume: float, goal_enc: float) -> float:
    if not trained_classifier:
        return 0.0
    feature_vector = np.array([[bmi, max_hr, calories, hours, volume, goal_enc]])
    try:
        return float(trained_classifier.predict_proba(feature_vector)[0][1])
    except (TypeError, ValueError, AttributeError):
        return 0.0


def normalize_exercise_type(exercise_type: str) -> str:
    value = str(exercise_type or "").lower().strip().replace("_", "-")
    if any(term in value for term in ("squat", "bodyweight-squat")):
        return "squat"
    if any(term in value for term in ("pushup", "push-up", "push-up")):
        return "pushup"
    if any(term in value for term in ("jumping-jack", "jumping jack")):
        return "jumping-jacks"
    if any(term in value for term in ("situp", "sit-up", "sit up")):
        return "situp"
    if any(term in value for term in ("pullup", "pull-up", "pull up")):
        return "pullup"
    return value or "squat"


def count_extended_fingers(hand_landmarks) -> int:
    # MediaPipe Hands normalized coordinates: lower y means fingertip is higher/open.
    finger_pairs = ((8, 6), (12, 10), (16, 14), (20, 18))
    extended = 0
    for tip_idx, pip_idx in finger_pairs:
        tip = hand_landmarks.landmark[tip_idx]
        pip = hand_landmarks.landmark[pip_idx]
        if tip.y < pip.y - 0.015:
            extended += 1
    return extended


def update_shutdown_gesture(hand_results, gesture_state: dict) -> tuple[bool, int, str]:
    """Detect an open palm facing the camera for about five seconds."""
    if not hand_results or not hand_results.multi_hand_landmarks:
        gesture_state["open_started_at"] = None
        return False, 0, "Hold an open palm toward the camera for 5 seconds to stop."

    fingers = count_extended_fingers(hand_results.multi_hand_landmarks[0])
    if fingers < 4:
        gesture_state["open_started_at"] = None
        return False, 0, "Hold an open palm toward the camera for 5 seconds to stop."

    now = time.time()
    if not gesture_state.get("open_started_at"):
        gesture_state["open_started_at"] = now

    elapsed = now - gesture_state["open_started_at"]
    progress = min(100, int((elapsed / 5.0) * 100))
    if elapsed >= 5.0:
        return True, 100, "Open-palm shutdown confirmed."
    return False, progress, f"Keep palm open to stop: {5.0 - elapsed:.1f}s"


def classify_pose_state(landmarks, canonical_exercise: str) -> tuple[str | None, float]:
    if pose_state_model is None:
        return None, 0.0
    exercise_prefix = {
        "squat": "squats",
        "pushup": "pushups",
        "jumping-jacks": "jumping_jacks",
        "situp": "situp",
        "pullup": "pullups",
    }.get(canonical_exercise)
    if not exercise_prefix:
        return None, 0.0

    try:
        points = mediapipe_landmarks_to_points(landmarks)
        features = extract_pose_state_features(points).reshape(1, -1)
        probabilities = pose_state_model.predict_proba(features)[0]
        classes = list(pose_state_model.classes_)
        best_index = int(np.argmax(probabilities))
        predicted_label = str(classes[best_index])
        confidence = float(probabilities[best_index])

        if not predicted_label.startswith(f"{exercise_prefix}_"):
            matching = [
                (str(label), float(probabilities[idx]))
                for idx, label in enumerate(classes)
                if str(label).startswith(f"{exercise_prefix}_")
            ]
            if not matching:
                return None, confidence
            predicted_label, confidence = max(matching, key=lambda item: item[1])

        state = predicted_label.rsplit("_", 1)[-1].upper()
        return state if state in {"UP", "DOWN"} else None, confidence
    except Exception as exc:
        print(f"[POSE_CLASSIFIER_WARNING] {exc}")
        return None, 0.0


def classify_exercise_phase(landmarks, canonical_exercise: str) -> tuple[str | None, float]:
    model = exercise_phase_models.get(canonical_exercise)
    if model is None:
        return None, 0.0
    try:
        points = mediapipe_landmarks_to_points(landmarks)
        features = extract_pose_state_features(points).reshape(1, -1)
        probabilities = model.predict_proba(features)[0]
        classes = list(model.classes_)
        best_index = int(np.argmax(probabilities))
        phase = str(classes[best_index]).upper()
        confidence = float(probabilities[best_index])
        if phase not in {"UP", "DOWN", "MID", "INVALID"}:
            return None, confidence
        return phase, confidence
    except Exception as exc:
        print(f"[PHASE_CLASSIFIER_WARNING] {exc}")
        return None, 0.0


def has_required_pose_visibility(landmarks, canonical_exercise: str, min_visibility: float = 0.45) -> bool:
    def visible(indices):
        return all(landmarks[idx].visibility >= min_visibility for idx in indices)

    if canonical_exercise == "squat":
        return visible((23, 25, 27)) or visible((24, 26, 28))
    if canonical_exercise == "pushup":
        return (visible((11, 13, 15)) or visible((12, 14, 16))) and (visible((23,)) or visible((24,)))
    if canonical_exercise == "jumping-jacks":
        return visible((11, 12, 15, 16))
    if canonical_exercise == "situp":
        return (visible((11, 23, 25)) or visible((12, 24, 26)))
    if canonical_exercise == "pullup":
        return visible((11, 13, 15)) or visible((12, 14, 16))
    return False

# NOTE: Gemini macrocycle generation replaced by Groq integration in habit_tracker service
# To generate macrocycles, use habit_tracker_service.generate_macrocycle_with_groq()
# This ensures consistency with rest of LLM infrastructure
# ==========================================================================
# PRESERVED OPENCV COMPUTER VISION REPS TRACKING MODULE
# ==========================================================================

def launch_native_opencv_tracker(user_id: str, exercise_type: str, stop_event: threading.Event | None = None):
    """Launch pose detection tracking using MediaPipe PoseLandmarker."""
    print(f"\n[ENGINE_START] Executing tracking system workflow process loop for: {user_id}")
    
    # 🔧 FIX: Use a shared event loop context instead of creating new loops
    loop = None
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop - create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        # Attempt to initialize webcam
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[ENGINE_ERROR] Webcam hardware is unavailable.")
            return
            
        print("[ENGINE_INFO] Camera opened successfully")
        
        # Try to initialize MediaPipe - if it fails, still run in demo mode
        pose_landmarker = None
        try:
            print("[ENGINE_INFO] Initializing PoseLandmarker from MediaPipe tasks...")
            from mediapipe.tasks.python.vision import PoseLandmarkerOptions, RunningMode
            
            options = PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(),
                running_mode=RunningMode.IMAGE,
                num_poses=1
            )
            pose_landmarker = vision.PoseLandmarker.create_from_options(options)
            print("[ENGINE_INFO] ✓ PoseLandmarker initialized successfully")
            
        except Exception as e:
            print(f"[ENGINE_WARNING] PoseLandmarker initialization failed: {type(e).__name__}")
            print(f"[ENGINE_INFO] Running in demo/simulation mode without real pose detection")
            # Continue anyway - we can run in demo mode
        
        # Initialize tracking variables
        correct_reps = 0
        incorrect_reps = 0
        sets_completed = 0
        current_direction = "UP"  
        feedback_text = "Demo mode: No pose detection available"
        pose_position_str = "UP"
        hand_raised_frames = 0
        current_rep_had_error = False  
        frame_count = 0
        last_timestamp_ms = 0

        print(f"[ENGINE_INFO] Starting training loop for exercise: {exercise_type}")
        
        while cap.isOpened():
            if stop_event and stop_event.is_set():
                print("[ENGINE_INFO] Stop event received, terminating tracker loop")
                break

            ret, frame = cap.read()
            if not ret: 
                print("[ENGINE_INFO] Video stream ended")
                break

            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (480, 640))
            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            frame_count += 1
            
            # Try pose detection if available
            if pose_landmarker:
                try:
                    # 🔧 FIX: Add frame delay to prevent timestamp conflicts
                    # MediaPipe requires strictly monotonically increasing timestamps
                    current_timestamp_ms = int((datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds() * 1000)
                    
                    # Ensure timestamps only increase
                    if current_timestamp_ms <= last_timestamp_ms:
                        current_timestamp_ms = last_timestamp_ms + 1
                    last_timestamp_ms = current_timestamp_ms
                    
                    # 🔧 FIX: Add small frame processing delay to reduce computational strain
                    cv2.waitKey(10)  # ~30fps processing
                    
                    mp_image = Image(image_format=ImageFormat.SRGB, data=rgb_frame)
                    results = pose_landmarker.detect(mp_image)
                    
                    if results and results.pose_landmarks and len(results.pose_landmarks) > 0:
                        if frame_count % 30 == 0:
                            print(f"[POSE_DEBUG] ✓ Frame {frame_count}: Detected pose")
                        
                        landmarks = results.pose_landmarks[0]
                        lm_map = {}
                        
                        for idx, landmark in enumerate(landmarks):
                            if landmark.visibility > 0.3:
                                lm_map[idx] = (landmark.x * w, landmark.y * h)
                        
                        if len(lm_map) >= 5:
                            # Process landmarks for rep counting
                            if exercise_type.lower() == "squat" and 23 in lm_map and 25 in lm_map and 27 in lm_map:
                                knee_angle = calculate_angle(lm_map[23], lm_map[25], lm_map[27])
                                
                                if knee_angle < 120.0: 
                                    pose_position_str = "DOWN"
                                elif knee_angle > 155.0: 
                                    pose_position_str = "UP"
                                
                                if pose_position_str == "DOWN":
                                    feedback_text = "Squat depth good. Push back up."
                            
                            # Rep counting logic
                            if pose_position_str == "DOWN" and current_direction == "UP":
                                current_direction = "DOWN"
                            elif pose_position_str == "UP" and current_direction == "DOWN":
                                current_direction = "UP"
                                correct_reps += 1
                                total_reps = correct_reps + incorrect_reps
                                
                                if total_reps > 0 and total_reps % 10 == 0:
                                    sets_completed += 1
                                
                                print(f"[REP_COUNTER] Reps: {total_reps} | Sets: {sets_completed}")
                                
                                # Save intermediate data
                                if total_reps > 0 and total_reps % 5 == 0:
                                    try:
                                        intermediate_log = {
                                            "user_id": user_id,
                                            "timestamp": datetime.datetime.utcnow(),
                                            "correct_reps": int(correct_reps),
                                            "incorrect_reps": int(incorrect_reps),
                                            "exercises": [{
                                                "name": exercise_type.capitalize(),
                                                "sets_completed": int(sets_completed),
                                                "correct_reps": int(correct_reps),
                                                "incorrect_reps": int(incorrect_reps),
                                            }]
                                        }
                                        # 🔧 FIX: Use thread-safe loop execution
                                        if loop and not loop.is_closed():
                                            asyncio.run_coroutine_threadsafe(
                                                exercise_logs_col.insert_one(intermediate_log),
                                                loop
                                            )
                                        print(f"[INTERMEDIATE_SAVE] Saved at {total_reps} reps")
                                    except Exception as e:
                                        print(f"[SAVE_WARNING] Save failed: {e}")
                    else:
                        feedback_text = "No pose detected - adjust angle"
                        
                except Exception as e:
                    if frame_count % 60 == 0:
                        print(f"[ENGINE_WARNING] Pose detection error (frame {frame_count}): {type(e).__name__}")
            else:
                # Demo mode: simulate reps for testing
                feedback_text = "Demo Mode (no pose detection)"
                if frame_count % 60 == 0:
                    print(f"[DEMO_MODE] Frame {frame_count}: Running in demo mode")

            # UI rendering
            sidebar = construct_trainer_sidebar(
                exercise_type, correct_reps, incorrect_reps, sets_completed, 
                current_direction, pose_position_str, feedback_text, hand_raised_frames
            )

            master_canvas = np.hstack((frame, sidebar))
            cv2.imshow("FITNESS AI - TRAINER CORE ENGINE", master_canvas)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q') or key == ord('Q'): 
                print("[ENGINE_INFO] Shutdown triggered by user")
                break
                
            try:
                if cv2.getWindowProperty("FITNESS AI - TRAINER CORE ENGINE", cv2.WND_PROP_VISIBLE) < 1: 
                    break
            except cv2.error:
                break

        cap.release()
        cv2.destroyAllWindows()
        
        # Final database save
        if (correct_reps + incorrect_reps) > 0:
            try:
                final_log = {
                    "user_id": user_id,
                    "timestamp": datetime.datetime.utcnow(),
                    "correct_reps": int(correct_reps),
                    "incorrect_reps": int(incorrect_reps),
                    "exercises": [{
                        "name": exercise_type.capitalize(),
                        "sets_completed": int(sets_completed if sets_completed > 0 else 1),
                        "correct_reps": int(correct_reps),
                        "incorrect_reps": int(incorrect_reps),
                    }]
                }
                # 🔧 FIX: Use thread-safe loop execution
                if loop and not loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(
                        exercise_logs_col.insert_one(final_log),
                        loop
                    )
                    # Wait for completion with timeout
                    try:
                        future.result(timeout=5)
                    except Exception as e:
                        print(f"[DATABASE_TIMEOUT] Save operation timed out: {e}")
                print(f"[DATABASE_LOG_FINAL] Session complete! Reps: {correct_reps}, Sets: {sets_completed}")
            except PyMongoError as e:
                print(f"[DATABASE_ERROR] Final logging failed: {e}")
                
    except Exception as e:
        print(f"[ENGINE_FATAL] Unexpected error in launch_native_opencv_tracker: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure resources are cleaned up
        try:
            cap.release()
            cv2.destroyAllWindows()
        except:
            pass
        
        # Clean up event loop if created
        if loop and not loop.is_closed():
            try:
                loop.close()
            except:
                pass


def launch_native_opencv_tracker(
    user_id: str,
    exercise_type: str,
    stop_event: threading.Event | None = None,
    target_reps_per_set: int = 10,
    target_sets: int = 1,
):
    """Launch pose detection tracking using MediaPipe Pose and Hands."""
    print(f"\n[ENGINE_START] Executing tracking system workflow process loop for: {user_id}")

    canonical_exercise = normalize_exercise_type(exercise_type)
    display_exercise = canonical_exercise.replace("-", " ").title()
    target_reps_per_set = max(1, int(target_reps_per_set or 10))
    target_sets = max(1, int(target_sets or 1))
    target_total_reps = target_reps_per_set * target_sets
    session_id = f"{user_id}-{canonical_exercise}-{int(datetime.datetime.utcnow().timestamp())}"
    sync_client = None
    sync_exercise_logs = None
    cap = None
    pose_tracker = None
    hand_tracker = None

    correct_reps = 0
    incorrect_reps = 0
    sets_completed = 0
    current_direction = "UP"
    feedback_text = "Initializing pose detection..."
    pose_position_str = "UP"
    shutdown_progress = 0
    current_set = 1
    current_set_reps = 0
    exercise_completed = False
    stable_state = "UP"
    down_frames = 0
    up_frames = 0
    had_valid_down = False
    stable_required_frames = 3 if canonical_exercise in {"jumping-jacks", "situp", "pullup"} else 4

    def refresh_progress():
        nonlocal sets_completed, current_set, current_set_reps, exercise_completed
        total_reps = int(correct_reps + incorrect_reps)
        sets_completed = min(total_reps // target_reps_per_set, target_sets)
        remaining_reps = total_reps - (sets_completed * target_reps_per_set)
        exercise_completed = total_reps >= target_total_reps
        if exercise_completed:
            sets_completed = target_sets
            current_set = target_sets
            current_set_reps = target_reps_per_set
        else:
            current_set = min(sets_completed + 1, target_sets)
            current_set_reps = min(remaining_reps, target_reps_per_set)

    def save_live_stats(session_active: bool = True):
        if sync_exercise_logs is None:
            return
        total_reps = int(correct_reps + incorrect_reps)
        progress_percent = round(min((total_reps / max(target_total_reps, 1)) * 100, 100), 2)
        sync_exercise_logs.replace_one(
            {"user_id": user_id, "type": "live_tracking", "session_id": session_id},
            {
                "user_id": user_id,
                "type": "live_tracking",
                "session_id": session_id,
                "session_active": session_active,
                "timestamp": datetime.datetime.utcnow(),
                "exercise_name": display_exercise,
                "exercise_type": canonical_exercise,
                "sets_completed": int(sets_completed),
                "target_sets": int(target_sets),
                "target_reps_per_set": int(target_reps_per_set),
                "current_set": int(current_set),
                "current_set_reps": int(current_set_reps),
                "correct_reps": int(correct_reps),
                "incorrect_reps": int(incorrect_reps),
                "total_reps": total_reps,
                "target_total_reps": int(target_total_reps),
                "progress_percent": progress_percent,
                "exercise_completed": bool(exercise_completed),
                "accuracy": round((correct_reps / max(total_reps, 1)) * 100, 2) if total_reps else 0,
                "feedback": feedback_text,
                "position_state": pose_position_str,
            },
            upsert=True,
        )

    try:
        try:
            sync_client = MongoClient(
                MONGODB_URL,
                tlsAllowInvalidCertificates=True,
                serverSelectionTimeoutMS=5000,
                socketTimeoutMS=10000,
                connectTimeoutMS=10000,
                retryWrites=False,
            )
            sync_exercise_logs = sync_client.fitness_ai.exercise_logs
            previous_progress = sync_exercise_logs.find_one(
                {
                    "user_id": user_id,
                    "type": "live_tracking",
                    "exercise_type": canonical_exercise,
                    "exercise_completed": {"$ne": True},
                },
                sort=[("timestamp", -1)],
            )
            if previous_progress:
                correct_reps = int(previous_progress.get("correct_reps") or 0)
                incorrect_reps = int(previous_progress.get("incorrect_reps") or 0)
                refresh_progress()
                feedback_text = f"Resuming {display_exercise}: set {current_set}/{target_sets}, rep {current_set_reps}/{target_reps_per_set}."
        except Exception as db_error:
            print(f"[ENGINE_WARNING] Live stats DB connection unavailable: {db_error}")

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[ENGINE_ERROR] Webcam hardware is unavailable.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        print("[ENGINE_INFO] Camera opened successfully")

        try:
            print("[ENGINE_INFO] Initializing MediaPipe Pose and Hands...")
            pose_tracker = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=0,
                smooth_landmarks=True,
                min_detection_confidence=0.55,
                min_tracking_confidence=0.55,
            )
            hand_tracker = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.6,
            )
            print("[ENGINE_INFO] MediaPipe Pose and Hands initialized successfully")
        except Exception as e:
            print(f"[ENGINE_WARNING] MediaPipe initialization failed: {type(e).__name__}: {e}")
            print("[ENGINE_INFO] Running in demo/simulation mode without real pose detection")

        frame_count = 0
        shutdown_gesture_state = {"open_started_at": None}
        last_hand_results = None
        refresh_progress()
        save_live_stats(session_active=True)

        print(f"[ENGINE_INFO] Starting training loop for exercise: {canonical_exercise}")

        while cap.isOpened():
            if stop_event and stop_event.is_set():
                print("[ENGINE_INFO] Stop event received, terminating tracker loop")
                break

            ret, frame = cap.read()
            if not ret:
                print("[ENGINE_INFO] Video stream ended")
                break

            frame = cv2.flip(frame, 1)
            display_frame = cv2.resize(frame, (480, 640))
            inference_frame = cv2.resize(frame, (360, 480))
            h, w, _ = inference_frame.shape
            rgb_frame = cv2.cvtColor(inference_frame, cv2.COLOR_BGR2RGB)
            frame_count += 1
            rep_completed = False

            if pose_tracker:
                try:
                    pose_results = pose_tracker.process(rgb_frame)
                    if hand_tracker and frame_count % 3 == 0:
                        last_hand_results = hand_tracker.process(rgb_frame)
                    hand_results = last_hand_results
                    shutdown_confirmed, shutdown_progress, shutdown_text = update_shutdown_gesture(hand_results, shutdown_gesture_state)

                    if pose_results and pose_results.pose_landmarks:
                        pose_ready = has_required_pose_visibility(
                            pose_results.pose_landmarks.landmark,
                            canonical_exercise,
                        )
                        lm_map = {}
                        for idx, landmark in enumerate(pose_results.pose_landmarks.landmark):
                            if landmark.visibility > 0.45:
                                lm_map[idx] = (landmark.x * w, landmark.y * h)

                        phase_state, phase_confidence = classify_exercise_phase(
                            pose_results.pose_landmarks.landmark,
                            canonical_exercise,
                        )
                        model_state, model_confidence = classify_pose_state(
                            pose_results.pose_landmarks.landmark,
                            canonical_exercise,
                        )
                        candidate_state = None

                        phase_threshold = 0.48 if canonical_exercise in {"pullup", "situp"} else 0.52
                        model_threshold = 0.46 if canonical_exercise in {"jumping-jacks", "situp", "pullup"} else 0.58

                        if not pose_ready:
                            feedback_text = "No full pose detected. Step back and keep your whole body visible."
                        elif phase_state in {"UP", "DOWN"} and phase_confidence >= phase_threshold:
                            candidate_state = phase_state
                            feedback_text = f"{display_exercise} {phase_state.lower()} phase ({phase_confidence:.0%})."
                        elif phase_state in {"MID", "INVALID"} and phase_confidence >= phase_threshold:
                            feedback_text = f"{display_exercise} {phase_state.lower()} phase. Complete the full range."
                        elif model_state and model_confidence >= model_threshold:
                            candidate_state = model_state
                            feedback_text = f"{display_exercise} {model_state.lower()} state detected ({model_confidence:.0%} confidence)."
                        elif canonical_exercise == "squat" and ((23 in lm_map and 25 in lm_map and 27 in lm_map) or (24 in lm_map and 26 in lm_map and 28 in lm_map)):
                            leg = (23, 25, 27) if 23 in lm_map and 25 in lm_map and 27 in lm_map else (24, 26, 28)
                            knee_angle = calculate_angle(lm_map[leg[0]], lm_map[leg[1]], lm_map[leg[2]])
                            if knee_angle < 125.0:
                                candidate_state = "DOWN"
                                feedback_text = "Depth detected. Keep chest up and push through heels."
                            elif knee_angle > 155.0:
                                candidate_state = "UP"
                                feedback_text = "Standing tall. Begin the next controlled rep."
                            else:
                                feedback_text = f"Squat angle {int(knee_angle)} deg. Go lower for a full rep."
                        elif pose_ready and canonical_exercise == "pushup" and ((11 in lm_map and 13 in lm_map and 15 in lm_map) or (12 in lm_map and 14 in lm_map and 16 in lm_map)):
                            arm = (11, 13, 15) if 11 in lm_map and 13 in lm_map and 15 in lm_map else (12, 14, 16)
                            elbow_angle = calculate_angle(lm_map[arm[0]], lm_map[arm[1]], lm_map[arm[2]])
                            if elbow_angle < 95.0:
                                candidate_state = "DOWN"
                                feedback_text = "Push-up depth detected. Press back up with a straight line."
                            elif elbow_angle > 155.0:
                                candidate_state = "UP"
                                feedback_text = "Arms extended. Keep core tight."
                            else:
                                feedback_text = f"Elbow angle {int(elbow_angle)} deg. Move with control."
                        elif pose_ready and canonical_exercise == "situp" and ((11 in lm_map and 23 in lm_map and 25 in lm_map) or (12 in lm_map and 24 in lm_map and 26 in lm_map)):
                            side = (11, 23, 25) if 11 in lm_map and 23 in lm_map and 25 in lm_map else (12, 24, 26)
                            hip_angle = calculate_angle(lm_map[side[0]], lm_map[side[1]], lm_map[side[2]])
                            if hip_angle < 105.0:
                                candidate_state = "UP"
                                feedback_text = "Sit-up top position detected."
                            elif hip_angle > 135.0:
                                candidate_state = "DOWN"
                                feedback_text = "Sit-up lower position detected."
                            else:
                                feedback_text = f"Sit-up angle {int(hip_angle)} deg. Move through full range."
                        elif pose_ready and canonical_exercise == "pullup" and ((11 in lm_map and 13 in lm_map and 15 in lm_map) or (12 in lm_map and 14 in lm_map and 16 in lm_map)):
                            arm = (11, 13, 15) if 11 in lm_map and 13 in lm_map and 15 in lm_map else (12, 14, 16)
                            elbow_angle = calculate_angle(lm_map[arm[0]], lm_map[arm[1]], lm_map[arm[2]])
                            if elbow_angle < 95.0:
                                candidate_state = "UP"
                                feedback_text = "Pull-up top position detected."
                            elif elbow_angle > 145.0:
                                candidate_state = "DOWN"
                                feedback_text = "Pull-up hang position detected."
                            else:
                                feedback_text = f"Pull-up elbow angle {int(elbow_angle)} deg. Continue the rep."
                        elif pose_ready and canonical_exercise == "jumping-jacks" and 11 in lm_map and 12 in lm_map and 15 in lm_map and 16 in lm_map:
                            shoulder_y = (lm_map[11][1] + lm_map[12][1]) / 2
                            wrist_y = (lm_map[15][1] + lm_map[16][1]) / 2
                            if wrist_y < shoulder_y - 20:
                                candidate_state = "UP"
                                feedback_text = "Jumping jack arms-up position detected."
                            elif wrist_y > shoulder_y + 70:
                                candidate_state = "DOWN"
                                feedback_text = "Jumping jack arms-down position detected."
                            else:
                                feedback_text = "Raise and lower arms through full jumping-jack range."
                        else:
                            feedback_text = f"Waiting for a confident {display_exercise} up/down state."

                        if candidate_state == "DOWN":
                            down_frames += 1
                            up_frames = 0
                        elif candidate_state == "UP":
                            up_frames += 1
                            down_frames = 0
                        else:
                            down_frames = max(0, down_frames - 1)
                            up_frames = max(0, up_frames - 1)

                        if down_frames >= stable_required_frames:
                            stable_state = "DOWN"
                            pose_position_str = "DOWN"
                            current_direction = "DOWN"
                            had_valid_down = True
                        elif up_frames >= stable_required_frames:
                            stable_state = "UP"
                            pose_position_str = "UP"

                        if stable_state == "UP" and current_direction == "DOWN" and had_valid_down:
                            current_direction = "UP"
                            had_valid_down = False
                            correct_reps += 1
                            total_reps = correct_reps + incorrect_reps
                            refresh_progress()
                            rep_completed = True
                            print(f"[REP_COUNTER] Reps: {total_reps} | Sets: {sets_completed}")
                            if exercise_completed:
                                feedback_text = f"Target complete: {target_sets} sets x {target_reps_per_set} reps."
                    else:
                        feedback_text = "No full pose detected. Step back and keep your whole body in frame."

                    if shutdown_progress > 0:
                        feedback_text = shutdown_text
                    if shutdown_confirmed:
                        print("[ENGINE_INFO] Shutdown triggered by palm-to-fist gesture")
                        save_live_stats(session_active=False)
                        break
                except Exception as e:
                    if frame_count % 60 == 0:
                        print(f"[ENGINE_WARNING] Pose detection error (frame {frame_count}): {type(e).__name__}: {e}")
                    feedback_text = "Pose detection error. Adjust lighting and camera angle."
            else:
                feedback_text = "Demo Mode (no pose detection)"

            if rep_completed or frame_count % 30 == 0:
                save_live_stats(session_active=True)
            if exercise_completed:
                save_live_stats(session_active=False)
                print("[ENGINE_INFO] Exercise target completed, terminating tracker loop")
                break

            sidebar = construct_trainer_sidebar(
                display_exercise, correct_reps, incorrect_reps, sets_completed,
                current_direction, pose_position_str, feedback_text, shutdown_progress,
                target_reps_per_set, target_sets, current_set_reps, current_set
            )

            master_canvas = np.hstack((display_frame, sidebar))
            cv2.imshow("FITNESS AI - TRAINER CORE ENGINE", master_canvas)

            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q') or key == ord('Q'):
                print("[ENGINE_INFO] Shutdown triggered by user")
                break

            try:
                if cv2.getWindowProperty("FITNESS AI - TRAINER CORE ENGINE", cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break

        save_live_stats(session_active=False)
        print(f"[DATABASE_LOG_FINAL] Session complete! Reps: {correct_reps}, Sets: {sets_completed}")
    except Exception as e:
        print(f"[ENGINE_FATAL] Unexpected error in launch_native_opencv_tracker: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            if cap:
                cap.release()
            if pose_tracker:
                pose_tracker.close()
            if hand_tracker:
                hand_tracker.close()
            if sync_client:
                sync_client.close()
            cv2.destroyAllWindows()
        except Exception:
            pass
