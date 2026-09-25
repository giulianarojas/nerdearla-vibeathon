import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = "gemini-3.5-live-translate-preview"

if not GEMINI_API_KEY:
    raise RuntimeError(
        "La Api key de gemini no está configurada")