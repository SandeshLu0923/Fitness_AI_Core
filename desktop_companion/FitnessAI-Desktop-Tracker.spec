# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

root = Path(SPECPATH).parent

datas = [
    (str(root / "desktop_companion" / ".env.example"), "desktop_companion"),
    (str(root / "backend" / "app" / "habit_model.joblib"), "app"),
    (str(root / "backend" / "app" / "pose_model.joblib"), "app"),
    (str(root / "backend" / "app" / "pose_state_model.joblib"), "app"),
    (str(root / "backend" / "app" / "exercise_phase_models.joblib"), "app"),
]

binaries = []
binaries += collect_dynamic_libs("numpy")
binaries += collect_dynamic_libs("scipy")
try:
    binaries += collect_dynamic_libs("cv2")
except Exception:
    pass


a = Analysis(
    [str(root / "desktop_companion" / "launcher.py")],
    pathex=[str(root), str(root / "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "desktop_companion.companion_app",
        "app.database",
        "app.routers.gym_trainer",
        "app.modules.trainer_engine",
        "sklearn.ensemble._forest",
        "sklearn.tree._classes",
        "sklearn.neighbors._classification",
        "sklearn.svm._classes",
        "sklearn.preprocessing._label",
        "numpy._core",
        "numpy._core._exceptions",
        "numpy._core._multiarray_umath",
        "numpy.core",
        "numpy.core._multiarray_umath",
        "cv2",
        "mediapipe.python.solutions.pose",
        "mediapipe.python.solutions.hands",
        "mediapipe.python.solutions.drawing_utils",
        "mediapipe.modules.pose_landmark",
        "mediapipe.modules.pose_detection",
        "mediapipe.modules.hand_landmark",
        "mediapipe.modules.palm_detection",
    ] + collect_submodules("scipy"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "IPython",
        "notebook",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FitnessAI-Desktop-Tracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FitnessAI-Desktop-Tracker",
)
