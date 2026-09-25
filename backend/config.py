from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-live-translate-preview")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "La Api key de gemini no está configurada en el archivo .env"
    )