import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.services.pose_state_features import (
    extract_pose_state_features,
    landmarks_row_to_points,
    pose_state_feature_names,
)


EXERCISE_LABELS = {
    "squat": "squats",
    "pushup": "pushups",
    "pullup": "pullups",
    "jumping-jacks": "jumping_jacks",
    "situp": "situp",
}


PointMap = Dict[str, Tuple[float, float, float]]


def jitter_points(points: PointMap, rng: np.random.Generator, scale: float = 0.015) -> PointMap:
    return {
        name: (
            value[0] + float(rng.normal(0, scale)),
            value[1] + float(rng.normal(0, scale)),
            value[2] + float(rng.normal(0, scale / 2)),
        )
        for name, value in points.items()
    }


def interpolate_points(a: PointMap, b: PointMap, alpha: float, rng: np.random.Generator) -> PointMap:
    points: PointMap = {}
    for name in a:
        points[name] = (
            (a[name][0] * (1 - alpha)) + (b[name][0] * alpha) + float(rng.normal(0, 0.01)),
            (a[name][1] * (1 - alpha)) + (b[name][1] * alpha) + float(rng.normal(0, 0.01)),
            (a[name][2] * (1 - alpha)) + (b[name][2] * alpha) + float(rng.normal(0, 0.006)),
        )
    return points


def mirror_points(points: PointMap) -> PointMap:
    mirrored: PointMap = {}
    swap = {
        "left_shoulder": "right_shoulder",
        "right_shoulder": "left_shoulder",
        "left_elbow": "right_elbow",
        "right_elbow": "left_elbow",
        "left_wrist": "right_wrist",
        "right_wrist": "left_wrist",
        "left_hip": "right_hip",
        "right_hip": "left_hip",
        "left_knee": "right_knee",
        "right_knee": "left_knee",
        "left_ankle": "right_ankle",
        "right_ankle": "left_ankle",
    }
    for name, value in points.items():
        target = swap.get(name, name)
        mirrored[target] = (1.0 - value[0], value[1], -value[2])
    return mirrored


def feature(points: PointMap) -> np.ndarray:
    return extract_pose_state_features(points)


def build_exercise_dataset(
    rows: List[dict],
    all_other_points: List[PointMap],
    exercise_prefix: str,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    up_points = [landmarks_row_to_points(row) for row in rows if str(row["pose"]).endswith("_up")]
    down_points = [landmarks_row_to_points(row) for row in rows if str(row["pose"]).endswith("_down")]
    samples: List[np.ndarray] = []
    labels: List[str] = []

    for label, points_list in (("UP", up_points), ("DOWN", down_points)):
        for points in points_list:
            for variant in (points, mirror_points(points), jitter_points(points, rng)):
                samples.append(feature(variant))
                labels.append(label)

    pair_count = min(len(up_points), len(down_points), 220)
    for index in range(pair_count):
        up = up_points[index % len(up_points)]
        down = down_points[(index * 7) % len(down_points)]
        for alpha in (0.35, 0.5, 0.65):
            samples.append(feature(interpolate_points(up, down, alpha, rng)))
            labels.append("MID")

    invalid_pool = all_other_points.copy()
    rng.shuffle(invalid_pool)
    for points in invalid_pool[: max(80, min(240, len(up_points) + len(down_points)))]:
        samples.append(feature(jitter_points(points, rng, scale=0.02)))
        labels.append("INVALID")

    return np.vstack(samples), np.asarray(labels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train synthetic phase classifiers for supported exercises.")
    parser.add_argument(
        "--dataset-dir",
        default=str(Path(__file__).resolve().parents[3] / "archive (4)"),
        help="Directory containing labels.csv and landmarks.csv.",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "exercise_phase_models.joblib"),
        help="Output joblib path.",
    )
    args = parser.parse_args()

    rng = np.random.default_rng(42)
    dataset_dir = Path(args.dataset_dir)
    labels = pd.read_csv(dataset_dir / "labels.csv")
    landmarks = pd.read_csv(dataset_dir / "landmarks.csv")
    merged = labels.merge(landmarks, on="pose_id", validate="one_to_one").sort_values("pose_id")
    records = merged.to_dict(orient="records")
    all_points = [landmarks_row_to_points(row) for row in records]

    models = {}
    summaries = {}
    for canonical, prefix in EXERCISE_LABELS.items():
        rows = [row for row in records if str(row["pose"]).startswith(f"{prefix}_")]
        other_points = [landmarks_row_to_points(row) for row in records if not str(row["pose"]).startswith(f"{prefix}_")]
        X, y = build_exercise_dataset(rows, other_points, prefix, rng)

        model = Pipeline([
            ("scaler", StandardScaler()),
            ("classifier", ExtraTreesClassifier(
                n_estimators=220,
                random_state=42,
                class_weight="balanced",
                min_samples_leaf=2,
                n_jobs=-1,
            )),
        ])

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, stratify=y, random_state=42
        )
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        holdout_accuracy = accuracy_score(y_test, predictions)
        report = classification_report(y_test, predictions, output_dict=True, zero_division=0)
        model.fit(X, y)

        models[canonical] = model
        summaries[canonical] = {
            "samples": int(len(y)),
            "holdout_accuracy": float(holdout_accuracy),
            "class_counts": pd.Series(y).value_counts().sort_index().to_dict(),
            "classification_report": report,
        }

    artifact = {
        "models": models,
        "feature_names": pose_state_feature_names(),
        "labels": ["DOWN", "INVALID", "MID", "UP"],
        "exercise_labels": EXERCISE_LABELS,
        "training_summary": {
            "dataset_dir": str(dataset_dir),
            "models": summaries,
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_path)

    print(json.dumps(artifact["training_summary"], indent=2))
    print(f"Saved phase models to {output_path}")


if __name__ == "__main__":
    main()
