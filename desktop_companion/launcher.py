import os
import sys
from pathlib import Path

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
    env_path = ensure_user_env()
    load_dotenv(env_path)

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
