#creo un componente que controle las salas de manera dinamica sin escribirlas manualmente 

import asyncio

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