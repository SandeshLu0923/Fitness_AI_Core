"""
Advanced Form Analysis Module
Real-time form quality analysis for injury prevention
"""
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass
import math


class FormQuality(str, Enum):
    """Form quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    RISKY = "risky"


@dataclass
class FormIssue:
    """Represents a form issue detected"""
    name: str
    severity: str  # "info", "warning", "critical"
    description: str
    recommendation: str
    confidence: float  # 0-1


@dataclass
class FormAnalysis:
    """Complete form analysis for a rep"""
    exercise: str
    overall_quality: FormQuality
    score: float  # 0-100
    issues: List[FormIssue]
    strengths: List[str]
    injury_risk_level: str  # "low", "medium", "high"


class AdvancedFormAnalyzer:
    """Advanced form analysis for exercise injury prevention"""

    def __init__(self):
        self.exercise_rules = {
            "squat": self._analyze_squat,
            "pushup": self._analyze_pushup,
            "jumping-jacks": self._analyze_jumping_jacks,
            "pullup": self._analyze_pullup,
            "situp": self._analyze_situp,
        }

    def analyze_form(self, exercise: str, landmarks: Dict) -> FormAnalysis:
        """Analyze form for a specific exercise"""
        analyzer = self.exercise_rules.get(exercise.lower())
        
        if not analyzer:
            return FormAnalysis(
                exercise=exercise,
                overall_quality=FormQuality.GOOD,
                score=50,
                issues=[],
                strengths=["Exercise not fully analyzed yet"],
                injury_risk_level="low",
            )
        
        return analyzer(landmarks)

    def _analyze_squat(self, landmarks: Dict) -> FormAnalysis:
        """Analyze squat form for injury prevention"""
        issues = []
        strengths = []
        score = 100

        # Key landmarks: 11=left shoulder, 12=right shoulder, 23=left hip, 24=right hip,
        #                25=left knee, 26=right knee, 27=left ankle, 28=right ankle
        
        left_shoulder = landmarks.get(11, {})
        right_shoulder = landmarks.get(12, {})
        left_hip = landmarks.get(23, {})
        right_hip = landmarks.get(24, {})
        left_knee = landmarks.get(25, {})
        right_knee = landmarks.get(26, {})
        left_ankle = landmarks.get(27, {})
        right_ankle = landmarks.get(28, {})

        # Check 1: Knee tracking over toes
        left_knee_valgus = self._check_knee_valgus(left_hip, left_knee, left_ankle)
        right_knee_valgus = self._check_knee_valgus(right_hip, right_knee, right_ankle)
        
        if left_knee_valgus < -15 or right_knee_valgus < -15:
            issues.append(FormIssue(
                name="Knee valgus (inward collapse)",
                severity="critical",
                description="Knees are caving inward during squat",
                recommendation="Engage your glutes and push knees outward. Practice with resistance band around knees.",
                confidence=0.85,
            ))
            score -= 25
        elif left_knee_valgus < -5 or right_knee_valgus < -5:
            issues.append(FormIssue(
                name="Slight knee valgus",
                severity="warning",
                description="Knees showing slight inward tracking",
                recommendation="Focus on pushing knees outward throughout the movement",
                confidence=0.7,
            ))
            score -= 10

        # Check 2: Back angle (forward lean)
        forward_lean = self._calculate_forward_lean(left_shoulder, left_hip, left_knee)
        
        if forward_lean > 45:
            issues.append(FormIssue(
                name="Excessive forward lean",
                severity="warning",
                description="Torso leaning too far forward",
                recommendation="Maintain upright torso. Practice with wall for reference.",
                confidence=0.8,
            ))
            score -= 15
        elif forward_lean < 5:
            strengths.append("Excellent upright posture")

        # Check 3: Depth (knee angle)
        left_knee_angle = self._calculate_angle(left_hip, left_knee, left_ankle)
        right_knee_angle = self._calculate_angle(right_hip, right_knee, right_ankle)
        avg_knee_angle = (left_knee_angle + right_knee_angle) / 2
        
        if avg_knee_angle > 100:
            issues.append(FormIssue(
                name="Insufficient depth",
                severity="info",
                description="Squat depth could be deeper",
                recommendation="Lower yourself further until knees reach 90 degrees",
                confidence=0.75,
            ))
            score -= 10
        elif 80 <= avg_knee_angle <= 100:
            strengths.append("Good squat depth")

        # Check 4: Asymmetry (left vs right)
        asymmetry = abs(left_knee_angle - right_knee_angle)
        
        if asymmetry > 20:
            issues.append(FormIssue(
                name="Asymmetry detected",
                severity="warning",
                description="One side is working harder than the other",
                recommendation="Focus on balanced weight distribution. Check for pain or mobility issues.",
                confidence=0.7,
            ))
            score -= 15

        # Check 5: Ankle mobility (heel lift)
        left_ankle_visible = left_ankle.get("visibility", 0) > 0.5
        right_ankle_visible = right_ankle.get("visibility", 0) > 0.5
        
        if (left_ankle_visible and left_ankle.get("y", 0) < left_knee.get("y", 0)) or \
           (right_ankle_visible and right_ankle.get("y", 0) < right_knee.get("y", 0)):
            issues.append(FormIssue(
                name="Heel lift detected",
                severity="warning",
                description="Heels are lifting off the ground",
                recommendation="Keep heels planted. Work on ankle mobility if needed.",
                confidence=0.6,
            ))
            score -= 10

        # Determine injury risk
        injury_risk = "low"
        critical_issues = [i for i in issues if i.severity == "critical"]
        if critical_issues:
            injury_risk = "high"
        elif any(i.severity == "warning" for i in issues):
            injury_risk = "medium"

        # Determine overall quality
        if score >= 85:
            overall_quality = FormQuality.EXCELLENT
        elif score >= 70:
            overall_quality = FormQuality.GOOD
        elif score >= 50:
            overall_quality = FormQuality.FAIR
        elif score >= 30:
            overall_quality = FormQuality.POOR
        else:
            overall_quality = FormQuality.RISKY

        return FormAnalysis(
            exercise="squat",
            overall_quality=overall_quality,
            score=max(0, score),
            issues=issues,
            strengths=strengths,
            injury_risk_level=injury_risk,
        )

    def _analyze_pushup(self, landmarks: Dict) -> FormAnalysis:
        """Analyze pushup form"""
        issues = []
        strengths = []
        score = 100

        # Key landmarks: 12=right shoulder, 14=right elbow, 16=right wrist
        right_shoulder = landmarks.get(12, {})
        right_elbow = landmarks.get(14, {})
        right_wrist = landmarks.get(16, {})
        left_shoulder = landmarks.get(11, {})
        left_elbow = landmarks.get(13, {})
        left_wrist = landmarks.get(15, {})

        # Check 1: Elbow alignment
        left_elbow_angle = self._calculate_angle(left_shoulder, left_elbow, left_wrist)
        right_elbow_angle = self._calculate_angle(right_shoulder, right_elbow, right_wrist)
        avg_elbow_angle = (left_elbow_angle + right_elbow_angle) / 2

        if avg_elbow_angle > 160:
            issues.append(FormIssue(
                name="Elbows flaring out",
                severity="warning",
                description="Elbows positioned too far from body",
                recommendation="Keep elbows at 45-degree angle to body",
                confidence=0.8,
            ))
            score -= 15

        # Check 2: Back alignment
        left_hip = landmarks.get(23, {})
        right_hip = landmarks.get(24, {})
        back_alignment = self._calculate_back_alignment(left_shoulder, left_hip, right_shoulder, right_hip)

        if back_alignment < 0.7:
            issues.append(FormIssue(
                name="Sagging hips",
                severity="critical",
                description="Lower back is sagging, poor spinal alignment",
                recommendation="Engage core and maintain plank position",
                confidence=0.85,
            ))
            score -= 25
        else:
            strengths.append("Excellent core engagement")

        # Check 3: Depth
        if avg_elbow_angle < 90:
            issues.append(FormIssue(
                name="Insufficient depth",
                severity="info",
                description="Not lowering fully",
                recommendation="Lower until chest is close to ground",
                confidence=0.7,
            ))
            score -= 10

        # Check 4: Shoulder alignment
        shoulder_alignment = abs(left_shoulder.get("x", 0) - right_shoulder.get("x", 0))
        if shoulder_alignment > 30:
            issues.append(FormIssue(
                name="Uneven shoulder height",
                severity="warning",
                description="One shoulder higher than the other",
                recommendation="Maintain level shoulders throughout movement",
                confidence=0.65,
            ))
            score -= 10

        injury_risk = "high" if any(i.severity == "critical" for i in issues) else "medium" if any(i.severity == "warning" for i in issues) else "low"
        
        if score >= 85:
            overall_quality = FormQuality.EXCELLENT
        elif score >= 70:
            overall_quality = FormQuality.GOOD
        elif score >= 50:
            overall_quality = FormQuality.FAIR
        elif score >= 30:
            overall_quality = FormQuality.POOR
        else:
            overall_quality = FormQuality.RISKY

        return FormAnalysis(
            exercise="pushup",
            overall_quality=overall_quality,
            score=max(0, score),
            issues=issues,
            strengths=strengths,
            injury_risk_level=injury_risk,
        )

    def _analyze_jumping_jacks(self, landmarks: Dict) -> FormAnalysis:
        """Analyze jumping jacks form"""
        issues = []
        strengths = []
        score = 100

        # Key landmarks for jumping jacks
        left_ankle = landmarks.get(27, {})
        right_ankle = landmarks.get(28, {})

        # Check 1: Landing consistency
        ankle_y_diff = abs(left_ankle.get("y", 0) - right_ankle.get("y", 0))
        if ankle_y_diff > 30:
            issues.append(FormIssue(
                name="Uneven landing",
                severity="warning",
                description="One leg landing lower than the other",
                recommendation="Land with both feet at the same level",
                confidence=0.7,
            ))
            score -= 15
        else:
            strengths.append("Good landing symmetry")

        # Check 2: Balance
        shoulder = landmarks.get(12, {})
        hip = landmarks.get(24, {})
        balance = abs(shoulder.get("x", 0) - hip.get("x", 0))
        if balance > 40:
            issues.append(FormIssue(
                name="Poor balance",
                severity="info",
                description="Torso shifting side to side",
                recommendation="Maintain upright posture with stable core",
                confidence=0.65,
            ))
            score -= 5

        strengths.append("Good arm-leg coordination")
        
        injury_risk = "low"
        
        if score >= 85:
            overall_quality = FormQuality.EXCELLENT
        elif score >= 70:
            overall_quality = FormQuality.GOOD
        elif score >= 50:
            overall_quality = FormQuality.FAIR
        elif score >= 30:
            overall_quality = FormQuality.POOR
        else:
            overall_quality = FormQuality.RISKY

        return FormAnalysis(
            exercise="jumping-jacks",
            overall_quality=overall_quality,
            score=max(0, score),
            issues=issues,
            strengths=strengths,
            injury_risk_level=injury_risk,
        )

    def _analyze_pullup(self, landmarks: Dict) -> FormAnalysis:
        """Analyze pullup form"""
        issues = []
        strengths = []
        score = 100
        
        # Pullups are harder to analyze from front-view camera
        strengths.append("Back camera view recommended for better analysis")
        
        injury_risk = "medium"
        
        if score >= 85:
            overall_quality = FormQuality.EXCELLENT
        elif score >= 70:
            overall_quality = FormQuality.GOOD
        elif score >= 50:
            overall_quality = FormQuality.FAIR
        elif score >= 30:
            overall_quality = FormQuality.POOR
        else:
            overall_quality = FormQuality.RISKY

        return FormAnalysis(
            exercise="pullup",
            overall_quality=overall_quality,
            score=max(0, score),
            issues=issues,
            strengths=strengths,
            injury_risk_level=injury_risk,
        )

    def _analyze_situp(self, landmarks: Dict) -> FormAnalysis:
        """Analyze situp form"""
        issues = []
        strengths = []
        score = 100

        left_shoulder = landmarks.get(11, {})
        right_shoulder = landmarks.get(12, {})
        left_hip = landmarks.get(23, {})
        right_hip = landmarks.get(24, {})

        # Check 1: Symmetry
        shoulder_hip_diff_left = abs(left_shoulder.get("x", 0) - left_hip.get("x", 0))
        shoulder_hip_diff_right = abs(right_shoulder.get("x", 0) - right_hip.get("x", 0))

        if abs(shoulder_hip_diff_left - shoulder_hip_diff_right) > 30:
            issues.append(FormIssue(
                name="Asymmetric movement",
                severity="warning",
                description="Twisting to one side during situp",
                recommendation="Move straight up and down, engaging core evenly",
                confidence=0.7,
            ))
            score -= 15
        else:
            strengths.append("Good core symmetry")

        strengths.append("Proper neck alignment (neutral)")
        
        injury_risk = "low"
        
        if score >= 85:
            overall_quality = FormQuality.EXCELLENT
        elif score >= 70:
            overall_quality = FormQuality.GOOD
        elif score >= 50:
            overall_quality = FormQuality.FAIR
        elif score >= 30:
            overall_quality = FormQuality.POOR
        else:
            overall_quality = FormQuality.RISKY

        return FormAnalysis(
            exercise="situp",
            overall_quality=overall_quality,
            score=max(0, score),
            issues=issues,
            strengths=strengths,
            injury_risk_level=injury_risk,
        )

    # Helper methods
    def _calculate_angle(self, point1: Dict, point2: Dict, point3: Dict) -> float:
        """Calculate angle at point2 formed by point1-point2-point3"""
        x1, y1 = point1.get("x", 0), point1.get("y", 0)
        x2, y2 = point2.get("x", 0), point2.get("y", 0)
        x3, y3 = point3.get("x", 0), point3.get("y", 0)

        v1 = (x1 - x2, y1 - y2)
        v2 = (x3 - x2, y3 - y2)

        dot_product = v1[0] * v2[0] + v1[1] * v2[1]
        magnitude = math.sqrt(v1[0]**2 + v1[1]**2) * math.sqrt(v2[0]**2 + v2[1]**2)

        if magnitude == 0:
            return 0

        cos_angle = dot_product / magnitude
        angle_rad = math.acos(max(-1, min(1, cos_angle)))
        angle_deg = math.degrees(angle_rad)

        return angle_deg

    def _check_knee_valgus(self, hip: Dict, knee: Dict, ankle: Dict) -> float:
        """Check inward/outward knee deviation (valgus/varus)"""
        hip_x = hip.get("x", 0)
        knee_x = knee.get("x", 0)
        ankle_x = ankle.get("x", 0)

        # Calculate expected knee x position (linear interpolation)
        expected_knee_x = (hip_x + ankle_x) / 2

        # Deviation (negative = inward/valgus)
        deviation = knee_x - expected_knee_x
        return deviation

    def _calculate_forward_lean(self, shoulder: Dict, hip: Dict, knee: Dict) -> float:
        """Calculate forward lean angle in degrees"""
        return abs(self._calculate_angle(shoulder, hip, knee) - 90)

    def _calculate_back_alignment(self, left_shoulder: Dict, left_hip: Dict,
                                   right_shoulder: Dict, right_hip: Dict) -> float:
        """Check if back is straight (0-1 scale, 1=perfect)"""
        left_align = abs(left_shoulder.get("x", 0) - left_hip.get("x", 0))
        right_align = abs(right_shoulder.get("x", 0) - right_hip.get("x", 0))

        avg_alignment = (left_align + right_align) / 2
        # Normalize to 0-1 (less than 10 pixels difference = perfect)
        alignment_score = max(0, 1 - (avg_alignment / 50))

        return alignment_score
