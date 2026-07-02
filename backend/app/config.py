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

# Validation: Ensure critical keys are present
if not GROQ_API_KEY:
    print(
        "[CONFIG_WARNING] Missing GROQ_API_KEY. "
        "AI chat, diet, and plan generation routes will fail until it is configured."
    )

if not MONGODB_URL:
    raise ValueError(
        "Missing MONGODB_URL in environment configuration. "
        "Please set MONGODB_URL in your .env file or environment variables."
    )
