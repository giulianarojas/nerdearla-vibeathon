#creo un componente que controle las salas de manera dinamica sin escribirlas manualmente 

import asyncio
from pathlib import Path

from backend.audio.mp3_source import MP3AudioSource
from backend.gemini_service import GeminiService

class SessionManager:

    def __init__(self, max_sessions: int =10):
        self.sessions = {}
        self.counter = 0
        self.max_sessions = max_sessions

    def create_session(self) -> str:
        if len(self.sessions) >= self.max_sessions:
            raise RuntimeError("Maximum number of sessions reached")

        self.counter += 1

        session_id = f"sala-{self.counter}"

        self.sessions[session_id] = {
            "status": "created",
            "task": None,
            "audio": None,
        }

        return session_id

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str):
        session = self.sessions.pop(session_id, None)

        if session and session["task"]:
            session["task"].cancel()

    def list_session(self):
        return list(self.sessions.keys())

    #se llama cuando el usuario aprieta "Reproducir"
    async def start_session(
        self,
        session_id: str,
        audio_path: Path,
        websocket,
    ):

        session = self.sessions.get(
            session_id
        )

        if not session:

            raise ValueError(
                "Session not found"
            )

        if session["task"]:

            raise RuntimeError(
                "Session is already running"
            )

        session["audio"] = str(
            audio_path
        )

        session["status"] = "running"

        task = asyncio.create_task(
            self.run_session(
                session_id,
                audio_path,
                websocket,
            )
        )

        session["task"] = task

    async def run_session(
        self,
        session_id: str,
        audio_path: Path,
        websocket,
    ):

        session = self.sessions.get(
            session_id
        )

        try:

            await websocket.send_json({
                "type": "status",
                "status": "running",
            })

            audio_source = MP3AudioSource(
                audio_path
            )

            gemini = GeminiService()

            async with await gemini.connect() as gemini_session:

                async def send_audio():

                    async for chunk in (
                        audio_source.stream()
                    ):

                        await gemini.send_audio(
                            gemini_session,
                            chunk,
                        )

                    await gemini.end_audio(
                        gemini_session
                    )

                async def receive_results():

                    async for result in (
                        gemini.receive_transcriptions(
                            gemini_session
                        )
                    ):

                        await websocket.send_json({
                            "type": result["type"],
                            "text": result["text"],
                        })

                await asyncio.gather(
                    send_audio(),
                    receive_results(),
                )

            if session:

                session["status"] = "finished"

            await websocket.send_json({
                "type": "status",
                "status": "finished",
            })

        except asyncio.CancelledError:

            if session:

                session["status"] = "cancelled"

            raise

        except Exception as error:

            print(
                f"[{session_id}] "
                f"Session error:",
                error,
            )

            if session:

                session["status"] = "error"

            try:

                await websocket.send_json({
                    "type": "error",
                    "message": str(error),
                })

            except Exception:
                pass