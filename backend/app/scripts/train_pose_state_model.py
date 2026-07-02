import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.services.pose_state_features import (
    extract_pose_state_features,
    landmarks_row_to_points,
    pose_state_feature_names,
)


def build_feature_matrix(labels: pd.DataFrame, landmarks: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    merged = labels.merge(landmarks, on="pose_id", validate="one_to_one").sort_values("pose_id")
    features = [
        extract_pose_state_features(landmarks_row_to_points(row))
        for row in merged.to_dict(orient="records")
    ]
    return np.vstack(features), merged["pose"].to_numpy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the 10-state exercise pose classifier.")
    parser.add_argument(
        "--dataset-dir",
        default=str(Path(__file__).resolve().parents[3] / "archive (4)"),
        help="Directory containing labels.csv and landmarks.csv.",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "pose_state_model.joblib"),
        help="Output joblib path.",
    )
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    labels = pd.read_csv(dataset_dir / "labels.csv")
    landmarks = pd.read_csv(dataset_dir / "landmarks.csv")
    X, y = build_feature_matrix(labels, landmarks)

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", ExtraTreesClassifier(
            n_estimators=600,
            random_state=42,
            class_weight="balanced",
            min_samples_leaf=2,
            n_jobs=-1,
        )),
    ])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=42
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    holdout_accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, digits=3, output_dict=True)

    model.fit(X, y)
    artifact = {
        "model": model,
        "feature_names": pose_state_feature_names(),
        "labels": sorted(labels["pose"].unique().tolist()),
        "training_summary": {
            "dataset_dir": str(dataset_dir),
            "samples": int(len(y)),
            "classes": int(len(set(y))),
            "cv_accuracy_mean": float(scores.mean()),
            "cv_accuracy_std": float(scores.std()),
            "holdout_accuracy": float(holdout_accuracy),
            "class_counts": labels["pose"].value_counts().sort_index().to_dict(),
            "classification_report": report,
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_path)

    print(json.dumps(artifact["training_summary"], indent=2))
    print(f"Saved model to {output_path}")


if __name__ == "__main__":
    main()
