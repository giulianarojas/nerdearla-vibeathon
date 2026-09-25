import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.audio.youtube_source import YouTubeAudioSource
from backend.session_manager import SessionManager
from backend.websocket.handlers import handle_websocket_message

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / "audio"
YOUTUBE_CACHE_DIR = AUDIO_DIR / "youtube_cache"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
YOUTUBE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Nerdearla Live Captions",
    description="Open-source real-time conference transcription system",
    version="0.2.0",
)

session_manager = SessionManager(max_sessions=10)
websocket_connections = {}


class StartSessionRequest(BaseModel):
    audio: str
    start_offset: Optional[float] = 0.0


class YouTubePrepareRequest(BaseModel):
    url: str


# --- Archivos estáticos ---
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "frontend"),
    name="static",
)

app.mount(
    "/audio",
    StaticFiles(directory=AUDIO_DIR),
    name="audio",
)


# --- Endpoints ---

@app.get("/")
async def home():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "nerdearla-live-captions",
        "active_sessions": len(session_manager.list_session()),
    }


@app.get("/api/audios")
async def list_audio():
    """Devuelve los audios locales disponibles y los cacheados de YouTube."""
    audio_files = []
    if AUDIO_DIR.exists():
        for file in AUDIO_DIR.iterdir():
            if file.is_file() and file.suffix.lower() in [".mp3", ".wav"]:
                audio_files.append(file.name)

    if YOUTUBE_CACHE_DIR.exists():
        for file in YOUTUBE_CACHE_DIR.iterdir():
            if file.is_file() and file.suffix.lower() in [".mp3", ".wav", ".m4a"]:
                audio_files.append(f"youtube_cache/{file.name}")

    return {
        "audio": sorted(audio_files)
    }


@app.post("/api/sessions")
async def create_session():
    try:
        session_id = session_manager.create_session()
        return {"session_id": session_id}
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return {
        "session_id": session_id,
        "status": session.get("status"),
        "audio": session.get("audio"),
    }


@app.post("/api/youtube/prepare")
async def prepare_youtube(request: YouTubePrepareRequest):
    """
    Descarga o recupera de la caché el audio de un video de YouTube.
    Valida la duración y entrega el identificador listo para reproducir.
    """
    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(
            None,
            YouTubeAudioSource.prepare_audio,
            request.url,
            YOUTUBE_CACHE_DIR,
        )
        return {
            "status": "ok",
            "audio": f"youtube_cache/{info['filename']}",
            "title": info["title"],
            "duration": info["duration"],
            "filename": info["filename"],
        }
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Error procesando video de YouTube: {err}")


@app.post("/api/sessions/{session_id}/start")
async def start_session(
    session_id: str,
    request: StartSessionRequest,
):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sala no encontrada")

    audio_path = (AUDIO_DIR / request.audio).resolve()
    audio_directory = AUDIO_DIR.resolve()

    # Seguridad: el archivo debe permanecer dentro de la carpeta audio/
    if audio_directory != audio_path and audio_directory not in audio_path.parents:
        raise HTTPException(status_code=400, detail="Ruta de audio inválida")

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Archivo de audio no encontrado")

    ws = websocket_connections.get(session_id)
    if not ws:
        raise HTTPException(
            status_code=400,
            detail="La conexión WebSocket para esta sala aún no está activa. Conéctate antes de reproducir."
        )

    try:
        await session_manager.start_session(
            session_id,
            audio_path,
            ws,
            start_offset=request.start_offset or 0.0,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error))

    return {
        "session_id": session_id,
        "audio": request.audio,
        "status": "running",
    }


@app.post("/api/sessions/{session_id}/pause")
async def pause_session_endpoint(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    session_manager.pause_session(session_id)
    ws = websocket_connections.get(session_id)
    if ws:
        try:
            await ws.send_json({"type": "status", "status": "paused"})
        except Exception:
            pass
    return {"session_id": session_id, "status": "paused"}


@app.post("/api/sessions/{session_id}/resume")
async def resume_session_endpoint(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    session_manager.resume_session(session_id)
    ws = websocket_connections.get(session_id)
    if ws:
        try:
            await ws.send_json({"type": "status", "status": "running"})
        except Exception:
            pass
    return {"session_id": session_id, "status": "running"}


@app.post("/api/sessions/{session_id}/stop")
async def stop_session_endpoint(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    session_manager.stop_session(session_id)
    ws = websocket_connections.get(session_id)
    if ws:
        try:
            await ws.send_json({"type": "status", "status": "finished"})
        except Exception:
            pass
    return {"session_id": session_id, "status": "finished"}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
):
    await websocket.accept()

    session = session_manager.get_session(session_id)
    if not session:
        await websocket.send_json({
            "type": "error",
            "message": f"Sala {session_id} no encontrada"
        })
        await websocket.close()
        return

    websocket_connections[session_id] = websocket

    try:
        while True:
            message = await websocket.receive_json()
            await handle_websocket_message(
                websocket=websocket,
                session_id=session_id,
                message=message,
                session_manager=session_manager,
                audio_dir=AUDIO_DIR,
            )
    except Exception as error:
        print(f"[{session_id}] WebSocket cerrado / desconectado: {error}")
    finally:
        websocket_connections.pop(session_id, None)