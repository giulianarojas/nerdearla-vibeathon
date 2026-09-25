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

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"Archivo de audio no encontrado: "
                f"{self.file_path}"
            )

    async def stream(self):
        """
        Ejecuta FFmpeg y entrega audio PCM
        en chunks de aproximadamente 100 ms.
        """

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
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

            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            while True:
                chunk = await process.stdout.read(
                    self.chunk_size
                )

                if not chunk:
                    break

                yield chunk

                # Damos tiempo real al stream.
                await asyncio.sleep(
                    self.CHUNK_DURATION
                )

        finally:
            if process.returncode is None:
                process.terminate()

            await process.wait()