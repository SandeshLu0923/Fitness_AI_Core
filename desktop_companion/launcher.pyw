import os
import sys
from pathlib import Path
import io

import uvicorn
from dotenv import load_dotenv


APP_NAME = "Fitness AI Desktop Tracker"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "8000"


def app_data_dir() -> Path:
    base = os.getenv("APPDATA")
    if base:
        return Path(base) / "FitnessAI" / "DesktopTracker"
    return Path.home() / ".fitness_ai" / "desktop_tracker"


def ensure_user_env() -> Path:
    config_dir = app_data_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    env_path = config_dir / ".env"
    if not env_path.exists():
        env_path.write_text(
            "\n".join(
                [
                    "BACKEND_API_URL=https://fitness-ai-core.onrender.com",
                    "FITNESS_AI_WEB_ORIGIN=https://fitness-ai-core.vercel.app",
                    "HOST=127.0.0.1",
                    "PORT=8000",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        current = env_path.read_text(encoding="utf-8")
        if "BACKEND_API_URL=" not in current:
            env_path.write_text(
                "BACKEND_API_URL=https://fitness-ai-core.onrender.com\n" + current,
                encoding="utf-8",
            )
    return env_path


def bundled_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def main() -> None:
    # Allow starting via custom URL scheme or --from-backend flag
    # Check if started via URL scheme (fitnessai://start)
    url_scheme_started = False
    
    # Debug: Log all arguments
    print(f"Arguments received: {sys.argv}")
    
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            print(f"Checking argument: {arg}")
            if arg.startswith('fitnessai://') or 'fitnessai' in arg.lower():
                url_scheme_started = True
                print(f"Started via URL scheme: {arg}")
                break
    
    if not url_scheme_started and "--from-backend" not in sys.argv:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Fitness AI Desktop Tracker",
            "This app can only be started from the web interface.\n\nPlease use the 'Start Training' button on the Fitness AI website to begin a workout session."
        )
        sys.exit(1)
    
    # Fix for PyInstaller no-console mode: redirect stdout/stderr if they are None
    if sys.stdout is None:
        sys.stdout = io.TextIOWrapper(sys.__stdout__.buffer, encoding='utf-8') if hasattr(sys, '__stdout__') and sys.__stdout__ else io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.TextIOWrapper(sys.__stderr__.buffer, encoding='utf-8') if hasattr(sys, '__stderr__') and sys.__stderr__ else io.StringIO()

    env_path = ensure_user_env()
    load_dotenv(env_path)
    os.environ.setdefault("FITNESS_AI_COMPANION", "1")

    root = bundled_root()
    backend_path = root / "backend"
    if backend_path.exists():
        sys.path.insert(0, str(backend_path))
    else:
        sys.path.insert(0, str(root))

    host = os.getenv("HOST", DEFAULT_HOST)
    port = int(os.getenv("PORT", DEFAULT_PORT))

    print(f"{APP_NAME} starting on http://{host}:{port}")
    print(f"Config file: {env_path}")
    print("Keep this window open while using live exercise tracking.")

    uvicorn.run(
        "desktop_companion.companion_app:app",
        host=host,
        port=port,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
