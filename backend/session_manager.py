import asyncio
from pathlib import Path
from typing import Optional, Union

from backend.audio.audio_source import AudioSource
from backend.audio.mp3_source import MP3AudioSource
from backend.gemini_service import GeminiService


class SessionManager:
    """
    Gestiona dinámicamente las salas de transcripción y traducción en paralelo.
    Sincronizado con el Reloj Maestro del frontend (currentTime).
    """

    def __init__(self, max_sessions: int = 10, gemini_service_factory=None):
        self.sessions = {}
        self.counter = 0
        self.max_sessions = max_sessions
        self.gemini_service_factory = gemini_service_factory or GeminiService

    def create_session(self) -> str:
        if len(self.sessions) >= self.max_sessions:
            raise RuntimeError(f"Límite máximo de salas alcanzado ({self.max_sessions})")

        self.counter += 1
        session_id = f"sala-{self.counter}"

        self.sessions[session_id] = {
            "status": "created",
            "task": None,
            "audio": None,
            "audio_source": None,
            "client_current_time": 0.0,
            "is_paused": False,
        }

        return session_id

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str):
        session = self.sessions.pop(session_id, None)
        if session and session.get("task"):
            session["task"].cancel()

    def list_session(self):
        return list(self.sessions.keys())

    def update_clock(self, session_id: str, current_time: float, is_paused: Optional[bool] = None):
        """Actualiza el reloj de reproducción informado por el frontend."""
        session = self.sessions.get(session_id)
        if session:
            session["client_current_time"] = max(0.0, float(current_time))
            if is_paused is not None:
                session["is_paused"] = is_paused
                session["status"] = "paused" if is_paused else "running"

    def pause_session(self, session_id: str, current_time: Optional[float] = None):
        """Pausa el streaming de audio hacia Gemini de forma inmediata."""
        session = self.sessions.get(session_id)
        if session:
            session["is_paused"] = True
            session["status"] = "paused"
            if current_time is not None:
                session["client_current_time"] = max(0.0, float(current_time))

    def resume_session(self, session_id: str, current_time: Optional[float] = None):
        """Reanuda el streaming de audio hacia Gemini desde la posición informada."""
        session = self.sessions.get(session_id)
        if session:
            session["is_paused"] = False
            session["status"] = "running"
            if current_time is not None:
                session["client_current_time"] = max(0.0, float(current_time))

    def stop_session(self, session_id: str):
        """Detiene completamente la sesión y cancela subprocesos."""
        session = self.sessions.get(session_id)
        if session:
            session["status"] = "finished"
            session["is_paused"] = True
            if session.get("task") and not session["task"].done():
                session["task"].cancel()
            session["task"] = None

    async def seek_session(
        self,
        session_id: str,
        audio_dir: Path,
        audio_identifier: str,
        new_position: float,
        websocket,
        was_paused: bool = False,
    ):
        """
        Reposiciona FFmpeg con -ss al segundo exacto indicado por el frontend.
        """
        session = self.sessions.get(session_id)
        if not session:
            return

        if session.get("task") and not session["task"].done():
            session["task"].cancel()
            try:
                await session["task"]
            except (asyncio.CancelledError, Exception):
                pass
            session["task"] = None

        audio_path = Path(audio_identifier)
        if not audio_path.is_absolute():
            audio_path = (Path(audio_dir) / audio_identifier).resolve()

        session["client_current_time"] = max(0.0, float(new_position))
        session["is_paused"] = was_paused
        session["status"] = "paused" if was_paused else "running"

        source = MP3AudioSource(
            audio_path,
            start_offset=new_position,
            is_paused_check=lambda: session.get("is_paused", False),
            get_client_time=lambda: session.get("client_current_time", 0.0),
        )
        session["audio_source"] = source
        session["audio"] = str(audio_identifier)

        task = asyncio.create_task(
            self.run_session(session_id, source, websocket)
        )
        session["task"] = task

    async def start_session(
        self,
        session_id: str,
        audio_source_or_path: Union[Path, str, AudioSource],
        websocket,
        start_offset: float = 0.0,
    ):
        """Inicia la sesión vinculada a la sala."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Sala {session_id} no encontrada")

        if session.get("task") and not session["task"].done():
            session["task"].cancel()
            try:
                await session["task"]
            except (asyncio.CancelledError, Exception):
                pass
            session["task"] = None

        session["client_current_time"] = max(0.0, float(start_offset))
        session["is_paused"] = False

        if isinstance(audio_source_or_path, (str, Path)):
            audio_path = Path(audio_source_or_path)
            session["audio"] = str(audio_path.name)
            audio_source = MP3AudioSource(
                audio_path,
                start_offset=start_offset,
                is_paused_check=lambda: session.get("is_paused", False),
                get_client_time=lambda: session.get("client_current_time", 0.0),
            )
        else:
            audio_source = audio_source_or_path
            session["audio"] = str(getattr(audio_source, "file_path", "stream"))

        session["audio_source"] = audio_source
        session["status"] = "running"

        task = asyncio.create_task(
            self.run_session(
                session_id,
                audio_source,
                websocket,
            )
        )
        session["task"] = task

    async def run_session(
        self,
        session_id: str,
        audio_source: AudioSource,
        websocket,
    ):
        session = self.sessions.get(session_id)
        if not session:
            return

        try:
            await websocket.send_json({
                "type": "status",
                "status": "running",
            })

            gemini = self.gemini_service_factory()

            async with await gemini.connect() as gemini_session:

                async def send_audio():
                    try:
                        async for chunk in audio_source.stream():
                            # 1. Si la sesión se detuvo, salimos de inmediato
                            if session.get("status") in ("finished", "stopped"):
                                break

                            # 2. Si está en pausa, nos suspendemos sin consumir audio
                            while session.get("is_paused") and session.get("status") not in ("finished", "stopped"):
                                await asyncio.sleep(0.05)

                            if session.get("status") in ("finished", "stopped"):
                                break

                            # 3. Gobernanza del Reloj Maestro:
                            # Solo permitimos entregar audio hasta un margen muy estrecho (+0.3s)
                            # respecto al currentTime del frontend.
                            current_audio_pos = getattr(audio_source, "current_position", 0.0)
                            client_time = session.get("client_current_time", 0.0)

                            while (
                                current_audio_pos > client_time + 0.3
                                and not session.get("is_paused")
                                and session.get("status") == "running"
                            ):
                                await asyncio.sleep(0.04)
                                client_time = session.get("client_current_time", 0.0)

                            if session.get("is_paused") or session.get("status") in ("finished", "stopped"):
                                continue

                            await gemini.send_audio(gemini_session, chunk)

                        await gemini.end_audio(gemini_session)
                    except asyncio.CancelledError:
                        raise
                    except Exception as err:
                        print(f"[{session_id}] Error enviando audio a Gemini: {err}")

                async def receive_results():
                    try:
                        async for result in gemini.receive_transcriptions(gemini_session):
                            if session.get("status") in ("finished", "stopped"):
                                break
                            curr_ts = getattr(audio_source, "current_position", 0.0)
                            await websocket.send_json({
                                "type": result["type"],
                                "text": result["text"],
                                "timestamp": round(curr_ts, 2),
                            })
                    except asyncio.CancelledError:
                        raise
                    except Exception as err:
                        print(f"[{session_id}] Error recibiendo de Gemini: {err}")

                await asyncio.gather(
                    send_audio(),
                    receive_results(),
                )

            if session and session.get("status") not in ("stopped", "paused"):
                session["status"] = "finished"
                await websocket.send_json({
                    "type": "status",
                    "status": "finished",
                })

        except asyncio.CancelledError:
            if session and session.get("status") != "finished":
                session["status"] = "stopped"
            raise

        except Exception as error:
            import traceback
            print(f"[{session_id}] Session error: {error}")
            traceback.print_exc()
            if session:
                session["status"] = "error"
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error en la sesión: {error}",
                })
            except Exception:
                pass