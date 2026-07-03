import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration - Using Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Database Configuration
MONGODB_URL = os.getenv("MONGODB_URL")

# Server Configuration
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))
IS_DESKTOP_COMPANION = os.getenv("FITNESS_AI_COMPANION") == "1"

# Validation: Ensure critical keys are present
if not IS_DESKTOP_COMPANION and not GROQ_API_KEY:
    print(
        "[CONFIG_WARNING] Missing GROQ_API_KEY. "
        "AI chat, diet, and plan generation routes will fail until it is configured."
    )

if not IS_DESKTOP_COMPANION and not MONGODB_URL:
    print(
        "[CONFIG_WARNING] Missing MONGODB_URL. "
        "Database-backed routes will fail until it is configured."
    )
