from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="Nerdearla Live Captions",
    description="Open-source real-time conference transcription system",
    version="0.1.0",
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "frontend"),
    name="static"),

@app.get("/")
async def home():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "nerdearla-live-captions",
    }