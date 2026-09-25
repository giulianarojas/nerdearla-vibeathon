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
    ):
        self.file_path = Path(file_path)
        self.start_offset = max(0.0, float(start_offset))
        self.pause_event = pause_event
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
        compensación precisa de tiempo real y soporte de pausa.
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
            # Audio PCM sin comprimir
            "-f",
            "s16le",
            # Mono
            "-ac",
            "1",
            # 16 kHz
            "-ar",
            "16000",
            # Salida por stdout
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
                if self.pause_event is not None and not self.pause_event.is_set():
                    await self.pause_event.wait()
                    # Al reanudar, recalibramos el reloj para no correr de golpe
                    start_time = loop.time() - (self.bytes_sent / bytes_per_sec)

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