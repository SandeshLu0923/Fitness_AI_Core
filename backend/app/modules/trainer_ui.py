import cv2
import numpy as np


def construct_trainer_sidebar(
    exercise_type,
    correct_reps,
    incorrect_reps,
    sets_completed,
    current_direction,
    pose_position_str,
    feedback_text,
    hand_raised_frames,
    target_reps_per_set=None,
    target_sets=None,
    current_set_reps=None,
    current_set=None,
):
    """Construct a compact dark live trainer sidebar."""
    sidebar = np.zeros((640, 480, 3), dtype=np.uint8)
    sidebar[:] = (10, 10, 12)

    cyan = (255, 205, 0)
    green = (90, 220, 90)
    orange = (0, 165, 255)
    muted = (120, 125, 135)
    panel = (24, 24, 28)
    border = (55, 60, 70)
    white = (235, 238, 245)

    cv2.putText(sidebar, "FITNESS AI TRACKER", (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, cyan, 2)

    cv2.rectangle(sidebar, (15, 45), (465, 150), panel, -1)
    cv2.rectangle(sidebar, (15, 45), (465, 150), border, 1)
    cv2.putText(sidebar, f"EXERCISE: {exercise_type.upper()}", (30, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.45, white, 1)
    cv2.putText(sidebar, "COUNT / SETS", (30, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.45, muted, 1)
    cv2.putText(sidebar, f"INCORRECT: {incorrect_reps}", (30, 132), cv2.FONT_HERSHEY_SIMPLEX, 0.42, muted, 1)

    reps_label = f"{correct_reps}"
    if target_reps_per_set:
        reps_label = f"{current_set_reps or 0}/{target_reps_per_set}"
    sets_label = f"{sets_completed}"
    if target_sets:
        sets_label = f"{sets_completed}/{target_sets}"

    cv2.rectangle(sidebar, (230, 80), (335, 135), (18, 38, 24), -1)
    cv2.rectangle(sidebar, (230, 80), (335, 135), green, 2)
    cv2.putText(sidebar, "REPS", (245, 99), cv2.FONT_HERSHEY_SIMPLEX, 0.35, muted, 1)
    cv2.putText(sidebar, reps_label, (248, 126), cv2.FONT_HERSHEY_SIMPLEX, 0.72, green, 2)

    cv2.rectangle(sidebar, (350, 80), (455, 135), (38, 26, 14), -1)
    cv2.rectangle(sidebar, (350, 80), (455, 135), orange, 2)
    cv2.putText(sidebar, "SETS", (365, 99), cv2.FONT_HERSHEY_SIMPLEX, 0.35, muted, 1)
    cv2.putText(sidebar, sets_label, (368, 126), cv2.FONT_HERSHEY_SIMPLEX, 0.72, orange, 2)

    cv2.rectangle(sidebar, (15, 165), (465, 265), panel, -1)
    cv2.rectangle(sidebar, (15, 165), (465, 265), border, 1)
    cv2.putText(sidebar, "MOTION DETECTION", (30, 192), cv2.FONT_HERSHEY_SIMPLEX, 0.45, muted, 1)
    up_box_color = cyan if current_direction == "UP" else (45, 48, 55)
    down_box_color = cyan if current_direction == "DOWN" else (45, 48, 55)
    cv2.rectangle(sidebar, (35, 210), (220, 250), up_box_color, -1)
    cv2.rectangle(sidebar, (260, 210), (445, 250), down_box_color, -1)
    cv2.putText(sidebar, "UP", (113, 237), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0) if current_direction == "UP" else muted, 2)
    cv2.putText(sidebar, "DOWN", (320, 237), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0) if current_direction == "DOWN" else muted, 2)

    cv2.rectangle(sidebar, (15, 280), (465, 505), panel, -1)
    cv2.rectangle(sidebar, (15, 280), (465, 505), border, 1)
    cv2.putText(sidebar, "LIVE FEEDBACK", (30, 307), cv2.FONT_HERSHEY_SIMPLEX, 0.45, muted, 1)
    clean_feedback = str(feedback_text or "")[:58]
    feedback_color = orange if any(term in clean_feedback.lower() for term in ("no full", "error", "lower")) else green
    cv2.putText(sidebar, clean_feedback[:46], (30, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.42, feedback_color, 1)
    if len(clean_feedback) > 46:
        cv2.putText(sidebar, clean_feedback[46:92], (30, 365), cv2.FONT_HERSHEY_SIMPLEX, 0.42, feedback_color, 1)
    cv2.putText(sidebar, f"STATE: {pose_position_str}", (30, 485), cv2.FONT_HERSHEY_SIMPLEX, 0.38, muted, 1)

    cv2.rectangle(sidebar, (15, 525), (465, 625), panel, -1)
    cv2.rectangle(sidebar, (15, 525), (465, 625), border, 1)
    cv2.putText(sidebar, "OPEN PALM SHUTDOWN", (30, 555), cv2.FONT_HERSHEY_SIMPLEX, 0.42, muted, 1)
    progress = min(max(int(hand_raised_frames or 0), 0), 100)
    cv2.rectangle(sidebar, (30, 575), (450, 598), (35, 38, 45), -1)
    if progress > 0:
        cv2.rectangle(sidebar, (30, 575), (30 + int(420 * progress / 100), 598), orange, -1)
    cv2.putText(sidebar, "Hold open palm 5s or press Q", (30, 615), cv2.FONT_HERSHEY_SIMPLEX, 0.35, muted, 1)

    return sidebar
