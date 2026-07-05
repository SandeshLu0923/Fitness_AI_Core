import os
import sys
from pathlib import Path
import io
import threading
import signal

import uvicorn
from dotenv import load_dotenv
import pystray
from PIL import Image


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


def get_icon_path():
    """Get the path to the app icon file."""
    root = bundled_root()
    icon_path = root / "fitness_121040.ico"
    if icon_path.exists():
        return icon_path
    # Fallback to creating a simple icon if file not found
    return None


def create_icon_image():
    """Create icon for the system tray from the app icon file."""
    icon_path = get_icon_path()
    if icon_path:
        try:
            return Image.open(icon_path)
        except Exception as e:
            print(f"Failed to load icon file: {e}")
    # Fallback to simple colored square
    return Image.new('RGB', (64, 64), color=(0, 200, 255))


# Global reference to the system tray icon for shutdown
tray_icon = None


def on_exit(icon, item):
    """Handle exit from system tray."""
    global tray_icon
    icon.stop()
    # Send SIGTERM to gracefully shutdown the application
    os.kill(os.getpid(), signal.SIGTERM)


def run_system_tray():
    """Run the system tray icon."""
    global tray_icon
    icon_image = create_icon_image()
    menu = pystray.Menu(
        pystray.MenuItem("Exit", on_exit)
    )
    tray_icon = pystray.Icon(
        "fitness_ai",
        icon_image,
        title="Fitness AI Desktop Tracker",  # Tooltip on hover
        menu=menu
    )
    tray_icon.run()


def main() -> None:
    # Allow starting from desktop shortcut or command line
    # Remove URL scheme restriction for manual launch approach
    
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

    # Start system tray icon in a separate thread
    tray_thread = threading.Thread(target=run_system_tray, daemon=True)
    tray_thread.start()

    uvicorn.run(
        "desktop_companion.companion_app:app",
        host=host,
        port=port,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
