import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

def generate_trainer_matrix_data(samples=2500):
    """
    Features expected by our 3-Phase pipeline:
    [bmi, target_max_hr, predicted_maintenance_calories, hours_elapsed, volume_delta, goal_encoded]
    """
    np.random.seed(42)
    X, y = [], []

    for _ in range(samples):
        goal_encoded = np.random.randint(0, 3) # 0: Loss, 1: Gain, 2: Fitness
        archetype = np.random.choice(["consistent", "overtraining_risk", "extended_absence"])

        if archetype == "overtraining_risk":
            features = [
                np.random.uniform(25.0, 31.0),  # BMI
                np.random.uniform(185.0, 195.0), # Max HR Ceiling
                np.random.uniform(2800.0, 3400.0), # Calorie baseline
                np.random.uniform(72.0, 120.0),  # Hours elapsed since last session
                np.random.uniform(-1200.0, -400.0) # Major drop in lifted volume
            ]
            will_skip = 1 if np.random.rand() > 0.15 else 0
        elif archetype == "extended_absence":
            features = [
                np.random.uniform(22.0, 27.0),
                np.random.uniform(175.0, 185.0),
                np.random.uniform(2000.0, 2600.0),
                np.random.uniform(120.0, 240.0), # Long multi-day gap
                np.random.uniform(-200.0, 100.0),
            ]
            will_skip = 1 if np.random.rand() > 0.25 else 0
        else: # Consistent
            features = [
                np.random.uniform(19.0, 24.0),
                np.random.uniform(170.0, 190.0),
                np.random.uniform(2200.0, 3000.0),
                np.random.uniform(24.0, 48.0),   # Healthy recovery window
                np.random.uniform(0.0, 500.0)     # Progressive overload progression
            ]
            will_skip = 0 if np.random.rand() > 0.05 else 1

        features.append(float(goal_encoded))
        X.append(features)
        y.append(will_skip)

    return np.array(X), np.array(y)

def train_and_export_brain():
    X, y = generate_trainer_matrix_data()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, max_depth=8, class_weight="balanced", random_state=42)
    model.fit(X_train, y_train)
    joblib.dump(model, "app/habit_model.joblib")
    print("Serialized system trainer brain exported successfully.")

if __name__ == "__main__":
    train_and_export_brain()
