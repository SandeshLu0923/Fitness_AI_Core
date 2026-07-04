import os
import cv2
import datetime
import json
import threading
import time
import queue
import mediapipe as mp
import numpy as np
import joblib
from app.modules.trainer_utils import calculate_angle, WeeklyMacrocyclePlan
from app.modules.tracker_state import update_live_stats
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
    # MediaPipe Hands normalized coordinates. Use both vertical extension and
    # wrist distance so an open palm works even when it is not above shoulder.
    finger_pairs = ((8, 6), (12, 10), (16, 14), (20, 18))
    extended = 0
    for tip_idx, pip_idx in finger_pairs:
        tip = hand_landmarks.landmark[tip_idx]
        pip = hand_landmarks.landmark[pip_idx]
        mcp = hand_landmarks.landmark[tip_idx - 3]
        wrist = hand_landmarks.landmark[0]
        tip_to_wrist = ((tip.x - wrist.x) ** 2 + (tip.y - wrist.y) ** 2) ** 0.5
        pip_to_wrist = ((pip.x - wrist.x) ** 2 + (pip.y - wrist.y) ** 2) ** 0.5
        tip_to_mcp = ((tip.x - mcp.x) ** 2 + (tip.y - mcp.y) ** 2) ** 0.5
        pip_to_mcp = ((pip.x - mcp.x) ** 2 + (pip.y - mcp.y) ** 2) ** 0.5
        vertically_open = tip.y < pip.y - 0.01
        radially_open = tip_to_wrist > pip_to_wrist * 1.08 and tip_to_mcp > pip_to_mcp * 1.08
        if vertically_open or radially_open:
            extended += 1
    return extended


def is_open_palm(hand_landmarks) -> bool:
    fingers = count_extended_fingers(hand_landmarks)
    landmarks = hand_landmarks.landmark
    index_mcp = landmarks[5]
    pinky_mcp = landmarks[17]
    index_tip = landmarks[8]
    pinky_tip = landmarks[20]
    palm_width = ((index_mcp.x - pinky_mcp.x) ** 2 + (index_mcp.y - pinky_mcp.y) ** 2) ** 0.5
    fingertip_spread = ((index_tip.x - pinky_tip.x) ** 2 + (index_tip.y - pinky_tip.y) ** 2) ** 0.5
    return fingers >= 4 and palm_width > 0.045 and fingertip_spread > palm_width * 0.85


def update_shutdown_gesture(hand_results, gesture_state: dict) -> tuple[bool, int, str]:
    """Detect any clear open palm for about five seconds."""
    if not hand_results or not hand_results.multi_hand_landmarks:
        gesture_state["open_started_at"] = None
        return False, 0, "Hold an open palm toward the camera for 5 seconds to stop."

    if not is_open_palm(hand_results.multi_hand_landmarks[0]):
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


def point_distance(a, b) -> float:
    return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)


def classify_geometry_state(canonical_exercise: str, lm_map: dict) -> tuple[str | None, str | None]:
    """Fast landmark geometry fallback/validator for supported exercises."""
    if canonical_exercise == "squat" and ((23 in lm_map and 25 in lm_map and 27 in lm_map) or (24 in lm_map and 26 in lm_map and 28 in lm_map)):
        leg = (23, 25, 27) if 23 in lm_map and 25 in lm_map and 27 in lm_map else (24, 26, 28)
        knee_angle = calculate_angle(lm_map[leg[0]], lm_map[leg[1]], lm_map[leg[2]])
        if knee_angle < 125.0:
            return "DOWN", "Depth detected. Keep chest up and push through heels."
        if knee_angle > 155.0:
            return "UP", "Standing tall. Begin the next controlled rep."
        return None, f"Squat angle {int(knee_angle)} deg. Go lower for a full rep."

    if canonical_exercise == "pushup" and ((11 in lm_map and 13 in lm_map and 15 in lm_map) or (12 in lm_map and 14 in lm_map and 16 in lm_map)):
        arm = (11, 13, 15) if 11 in lm_map and 13 in lm_map and 15 in lm_map else (12, 14, 16)
        elbow_angle = calculate_angle(lm_map[arm[0]], lm_map[arm[1]], lm_map[arm[2]])
        shoulder = lm_map[arm[0]]
        hip = lm_map[23] if 23 in lm_map else lm_map.get(24)
        body_ready = hip is None or abs(shoulder[1] - hip[1]) < 95
        if not body_ready:
            return None, "Keep shoulder, hip, and legs in one straight push-up line."
        if elbow_angle < 105.0:
            return "DOWN", "Push-up depth detected. Press back up with a straight body."
        if elbow_angle > 158.0:
            return "UP", "Arms extended. Keep core tight before the next rep."
        return None, f"Elbow angle {int(elbow_angle)} deg. Move through the full push-up range."

    if canonical_exercise == "situp" and ((11 in lm_map and 23 in lm_map and 25 in lm_map) or (12 in lm_map and 24 in lm_map and 26 in lm_map)):
        side = (11, 23, 25) if 11 in lm_map and 23 in lm_map and 25 in lm_map else (12, 24, 26)
        hip_angle = calculate_angle(lm_map[side[0]], lm_map[side[1]], lm_map[side[2]])
        if hip_angle < 105.0:
            return "UP", "Sit-up top position detected."
        if hip_angle > 135.0:
            return "DOWN", "Sit-up lower position detected."
        return None, f"Sit-up angle {int(hip_angle)} deg. Move through full range."

    if canonical_exercise == "pullup" and ((11 in lm_map and 13 in lm_map and 15 in lm_map) or (12 in lm_map and 14 in lm_map and 16 in lm_map)):
        arm = (11, 13, 15) if 11 in lm_map and 13 in lm_map and 15 in lm_map else (12, 14, 16)
        elbow_angle = calculate_angle(lm_map[arm[0]], lm_map[arm[1]], lm_map[arm[2]])
        if elbow_angle < 95.0:
            return "UP", "Pull-up top position detected."
        if elbow_angle > 145.0:
            return "DOWN", "Pull-up hang position detected."
        return None, f"Pull-up elbow angle {int(elbow_angle)} deg. Continue the rep."

    if canonical_exercise == "jumping-jacks" and 11 in lm_map and 12 in lm_map and 15 in lm_map and 16 in lm_map:
        shoulder_y = (lm_map[11][1] + lm_map[12][1]) / 2
        wrist_y = (lm_map[15][1] + lm_map[16][1]) / 2
        hand_spread = point_distance(lm_map[15], lm_map[16])
        shoulder_spread = point_distance(lm_map[11], lm_map[12])
        if wrist_y < shoulder_y - 20 and hand_spread > shoulder_spread * 1.15:
            return "UP", "Jumping jack arms-up position detected."
        if wrist_y > shoulder_y + 65:
            return "DOWN", "Jumping jack arms-down position detected."
        return None, "Raise and lower arms through full jumping-jack range."

    return None, None


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
    last_sidebar = None

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

    def build_live_stats_payload(session_active: bool = True):
        total_reps = int(correct_reps + incorrect_reps)
        progress_percent = round(min((total_reps / max(target_total_reps, 1)) * 100, 100), 2)
        return {
            "user_id": user_id,
            "type": "live_tracking",
            "session_id": session_id,
            "session_active": session_active,
            "timestamp": datetime.datetime.utcnow(),
            "date": datetime.date.today().isoformat(),
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
        }

    def save_live_stats(session_active: bool = True, force: bool = False):
        payload = build_live_stats_payload(session_active)
        update_live_stats(payload)

    try:
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
        shutdown_requested = False
        refresh_progress()
        save_live_stats(session_active=True, force=True)

        print(f"[ENGINE_INFO] Starting training loop for exercise: {canonical_exercise}")

        cv2.namedWindow("FITNESS AI - TRAINER CORE ENGINE", cv2.WINDOW_NORMAL)
        while cap.isOpened():
            if stop_event and stop_event.is_set():
                print("[ENGINE_INFO] Stop event received, terminating tracker loop")
                shutdown_requested = True
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
                    if hand_tracker and frame_count % 10 == 0:
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

                        candidate_state = None
                        geometry_state, geometry_feedback = classify_geometry_state(canonical_exercise, lm_map)

                        phase_threshold = 0.48 if canonical_exercise in {"pullup", "situp"} else 0.52
                        model_threshold = 0.46 if canonical_exercise in {"jumping-jacks", "situp", "pullup"} else 0.58
                        phase_state, phase_confidence = classify_exercise_phase(
                            pose_results.pose_landmarks.landmark,
                            canonical_exercise,
                        )
                        needs_model_fallback = not (
                            phase_state in {"UP", "DOWN", "MID", "INVALID"}
                            and phase_confidence >= phase_threshold
                        )
                        model_state, model_confidence = (None, 0.0)
                        if needs_model_fallback:
                            model_state, model_confidence = classify_pose_state(
                                pose_results.pose_landmarks.landmark,
                                canonical_exercise,
                            )

                        if not pose_ready:
                            feedback_text = "No full pose detected. Step back and keep your whole body visible."
                        elif canonical_exercise == "pushup" and geometry_state:
                            candidate_state = geometry_state
                            feedback_text = geometry_feedback or "Push-up state detected."
                        elif phase_state in {"UP", "DOWN"} and phase_confidence >= phase_threshold:
                            if geometry_state and geometry_state != phase_state and phase_confidence < 0.72:
                                candidate_state = geometry_state
                                feedback_text = geometry_feedback or f"{display_exercise} {geometry_state.lower()} state detected."
                            else:
                                candidate_state = phase_state
                                feedback_text = f"{display_exercise} {phase_state.lower()} phase ({phase_confidence:.0%})."
                        elif phase_state in {"MID", "INVALID"} and phase_confidence >= phase_threshold:
                            if geometry_state:
                                candidate_state = geometry_state
                                feedback_text = geometry_feedback or f"{display_exercise} {geometry_state.lower()} state detected."
                            else:
                                feedback_text = f"{display_exercise} {phase_state.lower()} phase. Complete the full range."
                        elif model_state and model_confidence >= model_threshold:
                            if geometry_state and geometry_state != model_state and model_confidence < 0.68:
                                candidate_state = geometry_state
                                feedback_text = geometry_feedback or f"{display_exercise} {geometry_state.lower()} state detected."
                            else:
                                candidate_state = model_state
                                feedback_text = f"{display_exercise} {model_state.lower()} state detected ({model_confidence:.0%} confidence)."
                        elif geometry_state:
                            candidate_state = geometry_state
                            feedback_text = geometry_feedback or f"{display_exercise} {geometry_state.lower()} state detected."
                        elif geometry_feedback:
                            feedback_text = geometry_feedback
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
                        save_live_stats(session_active=False, force=True)
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
                save_live_stats(session_active=False, force=True)
                print("[ENGINE_INFO] Exercise target completed, terminating tracker loop")
                break

            if last_sidebar is None or rep_completed or shutdown_progress > 0 or frame_count % 4 == 0:
                last_sidebar = construct_trainer_sidebar(
                    display_exercise, correct_reps, incorrect_reps, sets_completed,
                    current_direction, pose_position_str, feedback_text, shutdown_progress,
                    target_reps_per_set, target_sets, current_set_reps, current_set
                )

            master_canvas = np.hstack((display_frame, last_sidebar))
            cv2.imshow("FITNESS AI - TRAINER CORE ENGINE", master_canvas)

            key = cv2.waitKey(30) & 0xFF
            if key in (27, ord('q'), ord('Q')):
                print("[ENGINE_INFO] Shutdown triggered by user via keyboard")
                shutdown_requested = True
                break

            try:
                if cv2.getWindowProperty("FITNESS AI - TRAINER CORE ENGINE", cv2.WND_PROP_VISIBLE) < 1:
                    print("[ENGINE_INFO] Tracker window closed by user")
                    shutdown_requested = True
                    break
            except cv2.error:
                shutdown_requested = True
                break

        save_live_stats(session_active=False, force=True)
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
            cv2.destroyAllWindows()
        except Exception:
            pass
