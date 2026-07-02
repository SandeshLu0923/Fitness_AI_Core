"""
Form Analysis Router
Endpoints for real-time form quality analysis and injury prevention
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, List
from ..services.advanced_form_analyzer import AdvancedFormAnalyzer, FormAnalysis
from pydantic import BaseModel

router = APIRouter(prefix="/api/form-analysis", tags=["form-analysis"])

# Initialize analyzer
analyzer = AdvancedFormAnalyzer()


class LandmarkData(BaseModel):
    """Pose landmark data"""
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


class FormAnalysisRequest(BaseModel):
    """Request body for form analysis"""
    exercise_type: str
    landmarks: Dict[int, LandmarkData]


@router.post("/analyze")
async def analyze_form(request: FormAnalysisRequest):
    """Analyze exercise form in real-time"""
    try:
        # Convert to dictionary format expected by analyzer
        landmarks_dict = {}
        for key, landmark in request.landmarks.items():
            landmarks_dict[int(key)] = {
                "x": landmark.x,
                "y": landmark.y,
                "z": landmark.z,
                "visibility": landmark.visibility,
            }

        # Analyze form
        analysis = analyzer.analyze_form(request.exercise_type, landmarks_dict)

        return {
            "success": True,
            "exercise": analysis.exercise,
            "overall_quality": analysis.overall_quality,
            "form_score": analysis.score,
            "injury_risk": analysis.injury_risk_level,
            "issues": [
                {
                    "name": issue.name,
                    "severity": issue.severity,
                    "description": issue.description,
                    "recommendation": issue.recommendation,
                    "confidence": issue.confidence,
                }
                for issue in analysis.issues
            ],
            "strengths": analysis.strengths,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Form analysis failed: {str(e)}")


@router.get("/guidelines/{exercise_type}")
async def get_exercise_guidelines(exercise_type: str):
    """Get form guidelines for specific exercise"""
    guidelines = {
        "squat": {
            "key_points": [
                "Keep knees aligned with toes (no inward collapse)",
                "Maintain upright torso, slight forward lean OK",
                "Lower until knees reach 90 degrees",
                "Keep weight in heels",
                "Even weight distribution left/right",
            ],
            "common_mistakes": [
                "Knees caving inward (valgus)",
                "Excessive forward lean",
                "Insufficient depth",
                "Asymmetry (one leg working harder)",
                "Heel lift off ground",
            ],
            "injury_prevention": [
                "Stop if you feel sharp knee pain",
                "Warm up ankles before squatting",
                "Work on ankle mobility if heels lift",
                "Use resistance band for knee alignment practice",
            ],
        },
        "pushup": {
            "key_points": [
                "Keep elbows at 45-degree angle to body",
                "Maintain straight back (plank position)",
                "Lower until chest near ground",
                "Even shoulder height throughout",
                "Core engaged throughout",
            ],
            "common_mistakes": [
                "Elbows flaring out too wide",
                "Sagging hips (poor spine alignment)",
                "Insufficient depth",
                "Uneven shoulder height",
                "Head jutting forward",
            ],
            "injury_prevention": [
                "Stop if shoulder feels unstable",
                "Strengthen rotator cuff",
                "Proper warmup before heavy sets",
                "Modify with knees if needed",
            ],
        },
        "jumping-jacks": {
            "key_points": [
                "Land with both feet at same level",
                "Maintain upright posture",
                "Controlled arm movements",
                "Even leg coordination",
                "Stable core throughout",
            ],
            "common_mistakes": [
                "Uneven landing",
                "Poor balance side-to-side",
                "Jerky movements",
                "Uncontrolled arm swing",
            ],
            "injury_prevention": [
                "Good footwear with cushioning",
                "Warm up properly before intense sets",
                "Stop if knee or ankle pain occurs",
                "Modify with step-touch instead of jumps if needed",
            ],
        },
        "pullup": {
            "key_points": [
                "Full range of motion (dead hang to chin over bar)",
                "Chest to bar or chin over bar",
                "Controlled descent",
                "Engage back muscles (not just arms)",
                "Stability throughout",
            ],
            "common_mistakes": [
                "Partial range of motion",
                "Momentum instead of strength",
                "Uneven grip width",
                "Shrugging shoulders",
            ],
            "injury_prevention": [
                "Proper grip technique",
                "Strengthen shoulder stability first",
                "Progress gradually (use bands if needed)",
                "Stop if shoulder pain occurs",
            ],
        },
        "situp": {
            "key_points": [
                "Straight up and down movement",
                "Neutral neck position",
                "Core engagement",
                "Controlled descent",
                "Even weight distribution",
            ],
            "common_mistakes": [
                "Twisting to one side",
                "Neck strain (pulling head forward)",
                "Momentum instead of control",
                "Incomplete range of motion",
            ],
            "injury_prevention": [
                "Avoid jerky movements",
                "Keep neck neutral (no pulling)",
                "Use crunches for better form initially",
                "Stop if lower back pain occurs",
            ],
        },
    }

    exercise_lower = exercise_type.lower()
    if exercise_lower not in guidelines:
        return {
            "success": True,
            "message": "Guidelines not available for this exercise yet",
        }

    return {
        "success": True,
        "exercise": exercise_lower,
        "guidelines": guidelines[exercise_lower],
    }


@router.post("/batch-analyze")
async def batch_analyze_forms(
    exercise_type: str,
    landmarks_list: List[Dict[int, LandmarkData]],
):
    """Analyze multiple frames for form consistency"""
    try:
        analyses = []
        for landmarks in landmarks_list:
            landmarks_dict = {}
            for key, landmark in landmarks.items():
                landmarks_dict[int(key)] = {
                    "x": landmark.x,
                    "y": landmark.y,
                    "z": landmark.z,
                    "visibility": landmark.visibility,
                }

            analysis = analyzer.analyze_form(exercise_type, landmarks_dict)
            analyses.append(analysis)

        # Calculate average form quality
        avg_score = sum(a.score for a in analyses) / len(analyses) if analyses else 0
        most_common_issues = {}

        for analysis in analyses:
            for issue in analysis.issues:
                most_common_issues[issue.name] = most_common_issues.get(issue.name, 0) + 1

        # Sort by frequency
        sorted_issues = sorted(most_common_issues.items(), key=lambda x: x[1], reverse=True)

        return {
            "success": True,
            "total_frames": len(analyses),
            "avg_form_score": round(avg_score, 2),
            "consistency": "High" if avg_score > 80 else "Medium" if avg_score > 60 else "Low",
            "recurring_issues": [
                {
                    "issue": issue[0],
                    "frequency": f"{(issue[1] / len(analyses) * 100):.0f}%",
                }
                for issue in sorted_issues[:5]
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Batch analysis failed: {str(e)}")
