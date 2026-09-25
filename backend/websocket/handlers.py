import logging
from typing import Any, Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)


async def handle_websocket_message(
    websocket: WebSocket,
    session_id: str,
    message: Dict[str, Any],
    session_manager,
    audio_dir,
):
    """
    Procesa las acciones enviadas desde el cliente por WebSocket:
    sync_clock, play, pause, resume, stop, seek.
    """
    action = message.get("action")
    if not action:
        return

    session = session_manager.get_session(session_id)
    if not session:
        await websocket.send_json({
            "type": "error",
            "message": f"Sala {session_id} no encontrada",
        })
        return

    if action == "sync_clock":
        curr_time = float(message.get("currentTime", 0.0))
        is_paused = message.get("paused")
        session_manager.update_clock(session_id, curr_time, is_paused)

    elif action == "pause":
        curr_time = float(message.get("currentTime", 0.0))
        session_manager.pause_session(session_id, curr_time)
        await websocket.send_json({
            "type": "status",
            "status": "paused",
            "timestamp": curr_time,
        })

    elif action == "resume":
        curr_time = float(message.get("currentTime", 0.0))
        session_manager.resume_session(session_id, curr_time)
        await websocket.send_json({
            "type": "status",
            "status": "running",
            "timestamp": curr_time,
        })

    elif action == "stop":
        session_manager.stop_session(session_id)
        await websocket.send_json({
            "type": "status",
            "status": "finished",
        })

    elif action == "seek":
        new_pos = float(message.get("currentTime", 0.0))
        audio_name = message.get("audio") or session.get("audio")
        was_paused = bool(message.get("paused", session.get("is_paused", False)))
        if audio_name:
            await session_manager.seek_session(
                session_id=session_id,
                audio_dir=audio_dir,
                audio_identifier=audio_name,
                new_position=new_pos,
                websocket=websocket,
                was_paused=was_paused,
            )
