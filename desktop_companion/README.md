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

For the installer release, no Python or MongoDB setup is required. For the portable developer package, edit:

```text
desktop_companion\.env
```

Set:

```env
BACKEND_API_URL=https://fitness-ai-core.onrender.com
FITNESS_AI_WEB_ORIGIN=https://fitness-ai-core.vercel.app
```

## Start

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop_companion\start.ps1
```

Keep this terminal open while using live exercise tracking.

## Model Assets

The trained tracker model files are bundled inside the desktop tracker release zip. No separate model download is required.

If a future release ships models separately, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop_companion\install_models.ps1
```

## Package For GitHub Releases

### Option A: Windows Installer

Install Inno Setup 6, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop_companion\build_installer.ps1
```

Upload:

```text
release\installer\FitnessAI-Desktop-Tracker-Setup.exe
```

to GitHub Releases. This is the recommended release for normal users.

### Option B: Portable Zip

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop_companion\package.ps1
```

Upload:

```text
release\FitnessAI-Desktop-Tracker.zip
```

to GitHub Releases as the only required release asset.
