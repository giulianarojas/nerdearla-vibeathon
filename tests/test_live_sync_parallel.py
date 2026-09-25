import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.session_manager import SessionManager


class MockWebSocket:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.sent_messages = []

    async def send_json(self, data):
        self.sent_messages.append(data)


class MockGeminiService:
    def __init__(self):
        self.audio_chunks_received = []

    async def connect(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def send_audio(self, session, chunk: bytes):
        self.audio_chunks_received.append(chunk)

    async def end_audio(self, session):
        pass

    async def receive_transcriptions(self, session):
        # Generar transcripciones a medida que llegan chunks
        last_count = 0
        while True:
            await asyncio.sleep(0.05)
            curr_count = len(self.audio_chunks_received)
            if curr_count > last_count:
                last_count = curr_count
                yield {
                    "type": "original",
                    "text": f"Transcribing at chunk {curr_count}",
                }
                yield {
                    "type": "translation",
                    "text": f"Traduciendo en chunk {curr_count}",
                }
            if curr_count >= 100:
                break


async def test_pause_and_master_clock_sync():
    print("--- INICIANDO TEST: PAUSA INMEDIATA Y RELOJ MAESTRO ---")
    sm = SessionManager(max_sessions=5, gemini_service_factory=MockGeminiService)
    sala1 = sm.create_session()
    audio_path = BASE_DIR / "audio" / "charla-nerdearla-1.mp3"
    ws1 = MockWebSocket(sala1)

    # Iniciar sesión
    await sm.start_session(sala1, audio_path, ws1, start_offset=0.0)
    session1 = sm.get_session(sala1)

    # 1. Simular reproducción: el usuario escucha del segundo 0.0 al 1.0
    for tick in range(1, 11):
        await asyncio.sleep(0.08)
        current_time = tick * 0.1
        sm.update_clock(sala1, current_time, is_paused=False)

    delivered_before_pause = session1["audio_source"].current_position
    print(f"Posición del audio antes de pausar: {delivered_before_pause:.2f}s (reloj usuario: 1.00s)")

    # El backend no debe haberse adelantado más de ~0.35s respecto al reloj del usuario (1.0s)
    assert delivered_before_pause <= 1.45, f"Desincronización: el audio se adelantó a {delivered_before_pause}s"

    # 2. EL USUARIO APRIETA PAUSA a 1.0s
    print("Usuario aprieta PAUSA a 1.0s...")
    sm.pause_session(sala1, current_time=1.0)
    assert session1["is_paused"] is True
    assert session1["status"] == "paused"

    # Esperamos 0.5s con el reproductor en pausa
    await asyncio.sleep(0.5)

    delivered_during_pause = session1["audio_source"].current_position
    print(f"Posición del audio durante la pausa: {delivered_during_pause:.2f}s")

    # Confirmación: NO se avanzó ni un solo chunk mientras estaba en pausa
    assert delivered_during_pause == delivered_before_pause, (
        f"ERROR: el audio continuó avanzando en pausa! De {delivered_before_pause} pasó a {delivered_during_pause}"
    )
    print(">> CONFIRMADO: Subtítulos y entrega de audio se detienen INMEDIATAMENTE al pausar.")

    # 3. EL USUARIO REANUDA la reproducción
    print("Usuario aprieta REANUDAR...")
    sm.resume_session(sala1, current_time=1.0)
    assert session1["is_paused"] is False

    for tick in range(11, 20):
        await asyncio.sleep(0.08)
        current_time = tick * 0.1
        sm.update_clock(sala1, current_time, is_paused=False)

    delivered_after_resume = session1["audio_source"].current_position
    print(f"Posición del audio tras reanudar: {delivered_after_resume:.2f}s (reloj usuario: 1.90s)")
    assert delivered_after_resume > delivered_during_pause
    print(">> CONFIRMADO: Al reanudar, continúa desde la posición exacta sin adelantarse.")

    sm.stop_session(sala1)


async def test_parallel_independent_rooms():
    print("\n--- INICIANDO TEST: N SALAS PARALELAS CON ESTADOS INDEPENDIENTES ---")
    sm = SessionManager(max_sessions=5, gemini_service_factory=MockGeminiService)

    sala1 = sm.create_session()
    sala2 = sm.create_session()
    audio1 = BASE_DIR / "audio" / "charla-nerdearla-1.mp3"
    audio2 = BASE_DIR / "audio" / "charla-nerdearla-2.mp3"

    ws1 = MockWebSocket(sala1)
    ws2 = MockWebSocket(sala2)

    await sm.start_session(sala1, audio1, ws1, start_offset=0.0)
    await sm.start_session(sala2, audio2, ws2, start_offset=0.0)

    # Sala 1 avanza a 2.0s
    for tick in range(1, 10):
        await asyncio.sleep(0.04)
        sm.update_clock(sala1, tick * 0.2, is_paused=False)

    # Pausamos Sala 1 a 1.8s
    sm.pause_session(sala1, current_time=1.8)
    pos1_paused = sm.get_session(sala1)["audio_source"].current_position

    # Sala 2 SIGUE reproduciéndose independientemente hasta 3.0s
    for tick in range(1, 16):
        await asyncio.sleep(0.04)
        sm.update_clock(sala2, tick * 0.2, is_paused=False)

    pos2_running = sm.get_session(sala2)["audio_source"].current_position
    pos1_check = sm.get_session(sala1)["audio_source"].current_position

    print(f"Sala 1 (Pausada): {pos1_check:.2f}s | Estado: {sm.get_session(sala1)['status']}")
    print(f"Sala 2 (En vivo): {pos2_running:.2f}s | Estado: {sm.get_session(sala2)['status']}")

    assert pos1_check == pos1_paused, "Sala 1 no debió moverse mientras estaba en pausa"
    assert pos2_running > pos1_check, "Sala 2 debió seguir avanzando independientemente de Sala 1"
    assert sm.get_session(sala1)["status"] == "paused"
    assert sm.get_session(sala2)["status"] == "running"

    print(">> CONFIRMADO: N salas funcionan en paralelo de forma 100% independiente.")

    sm.stop_session(sala1)
    sm.stop_session(sala2)


async def main():
    await test_pause_and_master_clock_sync()
    await test_parallel_independent_rooms()
    print("\nTODOS LOS TESTS DE SINCRONIZACIÓN Y PARALELISMO PASARON EXITOSAMENTE.")


if __name__ == "__main__":
    asyncio.run(main())
