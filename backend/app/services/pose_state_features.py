import math
from typing import Dict, Iterable, List, Mapping, Tuple

import numpy as np

Point3D = Tuple[float, float, float]

ANGLE_TRIPLES: Tuple[Tuple[str, str, str], ...] = (
    ("right_elbow", "right_shoulder", "right_hip"),
    ("left_elbow", "left_shoulder", "left_hip"),
    ("right_knee", "mid_hip", "left_knee"),
    ("right_hip", "right_knee", "right_ankle"),
    ("left_hip", "left_knee", "left_ankle"),
    ("right_wrist", "right_elbow", "right_shoulder"),
    ("left_wrist", "left_elbow", "left_shoulder"),
)

DISTANCE_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("left_shoulder", "left_wrist"),
    ("right_shoulder", "right_wrist"),
    ("left_hip", "left_ankle"),
    ("right_hip", "right_ankle"),
    ("left_hip", "left_wrist"),
    ("right_hip", "right_wrist"),
    ("left_shoulder", "left_ankle"),
    ("right_shoulder", "right_ankle"),
    ("left_hip", "right_wrist"),
    ("right_hip", "left_wrist"),
    ("left_elbow", "right_elbow"),
    ("left_knee", "right_knee"),
    ("left_wrist", "right_wrist"),
    ("left_ankle", "right_ankle"),
    ("left_hip", "avg_left_wrist_left_ankle"),
    ("right_hip", "avg_right_wrist_right_ankle"),
)


def pose_state_feature_names() -> List[str]:
    names: List[str] = []
    names.extend("_".join(triple) + "_angle" for triple in ANGLE_TRIPLES)
    for start, end in DISTANCE_PAIRS:
        names.append(f"{start}_{end}_distance")
    for start, end in DISTANCE_PAIRS:
        names.extend((
            f"x_{start}_{end}",
            f"y_{start}_{end}",
            f"z_{start}_{end}",
        ))
    return names


def extract_pose_state_features(points: Mapping[str, Point3D]) -> np.ndarray:
    scale = _body_scale(points)
    features: List[float] = []

    for a, b, c in ANGLE_TRIPLES:
        features.append(_angle(_point(points, a), _point(points, b), _point(points, c)))

    for start, end in DISTANCE_PAIRS:
        delta = _delta(_point(points, start), _point(points, end))
        features.append(_norm(delta) / scale)

    for start, end in DISTANCE_PAIRS:
        dx, dy, dz = _delta(_point(points, start), _point(points, end))
        features.extend((dx / scale, dy / scale, dz / scale))

    return np.asarray(features, dtype=np.float32)


def landmarks_row_to_points(row: Mapping[str, float]) -> Dict[str, Point3D]:
    names = (
        "nose",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    )
    points = {
        name: (
            float(row[f"x_{name}"]),
            float(row[f"y_{name}"]),
            float(row[f"z_{name}"]),
        )
        for name in names
    }
    _add_derived_points(points)
    return points


def mediapipe_landmarks_to_points(landmarks: Iterable[object]) -> Dict[str, Point3D]:
    indexed = list(landmarks)
    mp_index = {
        "nose": 0,
        "left_shoulder": 11,
        "right_shoulder": 12,
        "left_elbow": 13,
        "right_elbow": 14,
        "left_wrist": 15,
        "right_wrist": 16,
        "left_hip": 23,
        "right_hip": 24,
        "left_knee": 25,
        "right_knee": 26,
        "left_ankle": 27,
        "right_ankle": 28,
    }
    points: Dict[str, Point3D] = {}
    for name, idx in mp_index.items():
        lm = indexed[idx]
        points[name] = (float(lm.x), float(lm.y), float(lm.z))
    _add_derived_points(points)
    return points


def _add_derived_points(points: Dict[str, Point3D]) -> None:
    points["mid_hip"] = _avg(points["left_hip"], points["right_hip"])
    points["avg_left_wrist_left_ankle"] = _avg(points["left_wrist"], points["left_ankle"])
    points["avg_right_wrist_right_ankle"] = _avg(points["right_wrist"], points["right_ankle"])


def _point(points: Mapping[str, Point3D], name: str) -> Point3D:
    return points[name]


def _avg(a: Point3D, b: Point3D) -> Point3D:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0)


def _delta(a: Point3D, b: Point3D) -> Point3D:
    return (b[0] - a[0], b[1] - a[1], b[2] - a[2])


def _norm(v: Point3D) -> float:
    return math.sqrt((v[0] * v[0]) + (v[1] * v[1]) + (v[2] * v[2]))


def _angle(a: Point3D, b: Point3D, c: Point3D) -> float:
    ba = np.asarray(a, dtype=np.float32) - np.asarray(b, dtype=np.float32)
    bc = np.asarray(c, dtype=np.float32) - np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(ba) * np.linalg.norm(bc))
    if denom <= 1e-8:
        return 180.0
    cosine = float(np.dot(ba, bc) / denom)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def _body_scale(points: Mapping[str, Point3D]) -> float:
    shoulder_width = _norm(_delta(points["left_shoulder"], points["right_shoulder"]))
    hip_width = _norm(_delta(points["left_hip"], points["right_hip"]))
    torso_left = _norm(_delta(points["left_shoulder"], points["left_hip"]))
    torso_right = _norm(_delta(points["right_shoulder"], points["right_hip"]))
    scale = max(shoulder_width, hip_width, (torso_left + torso_right) / 2.0)
    return scale if scale > 1e-6 else 1.0
