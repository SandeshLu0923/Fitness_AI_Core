# Fitness AI Desktop Tracker Companion

This local companion runs the OpenCV/MediaPipe exercise tracker on a user's Windows laptop or desktop. It opens the webcam locally and exposes the tracker API at:

```text
http://127.0.0.1:8000
```

The deployed web app calls this local service for live tracking while normal dashboard data continues to use the deployed Render backend.

## Install

Install Python 3.11 first. Then run from the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop_companion\install.ps1
```

Edit:

```text
desktop_companion\.env
```

Set:

```env
MONGODB_URL=your_mongodb_atlas_connection_string
FITNESS_AI_WEB_ORIGIN=https://fitness-ai-core.vercel.app
```

## Start

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop_companion\start.ps1
```

Keep this terminal open while using live exercise tracking.

## Optional Model Assets

The tracker package is intentionally small. Large trained model files are released separately.

After uploading the model chunk files to GitHub Releases, install them with:

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop_companion\install_models.ps1
```

If model files are not installed, the tracker falls back to MediaPipe plus geometry-based rep detection.

## Package For GitHub Releases

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop_companion\package.ps1
```

Upload:

```text
release\FitnessAI-Desktop-Tracker.zip
```

to GitHub Releases.

To create model release chunks:

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop_companion\package_models.ps1
```

Upload every file from:

```text
release\models\
```

to the same GitHub Release.
