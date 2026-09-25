import asyncio
from pathlib import Path

from backend.audio.audio_source import AudioSource


class MP3AudioSource(AudioSource):
    """
    Convierte un archivo MP3 a PCM mono 16 kHz
    utilizando FFmpeg y lo entrega progresivamente
    en pequeños fragmentos.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16 bits = 2 bytes

    # 100 ms de audio
    CHUNK_DURATION = 0.1

    @property
    def chunk_size(self):
        return int(
            self.SAMPLE_RATE
            * self.CHANNELS
            * self.SAMPLE_WIDTH
            * self.CHUNK_DURATION
        )

    def __init__(
        self,
        file_path: Path,
        start_offset: float = 0.0,
        pause_event: asyncio.Event = None,
        is_paused_check=None,
        get_client_time=None,
    ):
        self.file_path = Path(file_path)
        self.start_offset = max(0.0, float(start_offset))
        self.pause_event = pause_event
        self.is_paused_check = is_paused_check
        self.get_client_time = get_client_time
        self.bytes_sent = 0
        self.current_position = self.start_offset

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"Archivo de audio no encontrado: "
                f"{self.file_path}"
            )

    async def stream(self):
        """
        Ejecuta FFmpeg y entrega audio PCM
        en chunks de aproximadamente 100 ms con
        gobernanza estricta de tiempo y pausa.
        """
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
        ]

        if self.start_offset > 0.05:
            ffmpeg_cmd.extend(["-ss", f"{self.start_offset:.2f}"])

        ffmpeg_cmd.extend([
            "-i",
            str(self.file_path),
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "pipe:1",
        ])

        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self.bytes_sent = 0
        bytes_per_sec = self.SAMPLE_RATE * self.CHANNELS * self.SAMPLE_WIDTH
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            while True:
                # 1. Chequeo de pausa inmediato: no leer ni avanzar si está pausado
                if self.is_paused_check:
                    while self.is_paused_check():
                        await asyncio.sleep(0.02)
                elif self.pause_event is not None and not self.pause_event.is_set():
                    await self.pause_event.wait()
                    start_time = loop.time() - (self.bytes_sent / bytes_per_sec)

                # 2. Puerta de Reloj Maestro: no leer por delante del cliente (+0.25s)
                if self.get_client_time:
                    client_t = self.get_client_time()
                    while self.current_position > client_t + 0.25:
                        if self.is_paused_check and self.is_paused_check():
                            break
                        await asyncio.sleep(0.02)
                        client_t = self.get_client_time()

                if self.is_paused_check and self.is_paused_check():
                    continue

                try:
                    chunk = await asyncio.wait_for(
                        process.stdout.read(self.chunk_size),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    break

                if not chunk:
                    break

                self.bytes_sent += len(chunk)
                self.current_position = self.start_offset + (self.bytes_sent / bytes_per_sec)

                yield chunk

                # Compensación precisa de drift en tiempo real
                expected_elapsed = self.bytes_sent / bytes_per_sec
                actual_elapsed = loop.time() - start_time
                ahead = expected_elapsed - actual_elapsed
                if ahead > 0:
                    await asyncio.sleep(ahead)

        finally:
            if process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=1.5)
                except (asyncio.TimeoutError, ProcessLookupError):
                    try:
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=1.5)
                    except Exception:
                        pass
                except Exception:
                    pass
            # Permitir que el loop de Windows procese el cierre de pipes sin warnings
            await asyncio.sleep(0.05)