import asyncio
import re
from pathlib import Path
from typing import Optional

import yt_dlp

from backend.audio.audio_source import AudioSource
from backend.audio.mp3_source import MP3AudioSource


class YouTubeAudioSource(AudioSource):
    """
    Fuente de audio para videos de YouTube.
    Descarga y almacena en caché el audio en MP3 mediante yt-dlp,
    y delega la entrega PCM continua en tiempo real a MP3AudioSource.
    """

    MAX_DURATION_SECONDS = 7200  # 2 horas máximo por seguridad

    def __init__(
        self,
        url: str,
        cache_dir: Path,
        start_offset: float = 0.0,
        pause_event: Optional[asyncio.Event] = None,
    ):
        self.url = url.strip()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.start_offset = max(0.0, float(start_offset))
        self.pause_event = pause_event

        self.video_info = None
        self.file_path: Optional[Path] = None
        self._mp3_source: Optional[MP3AudioSource] = None

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Verifica si la cadena tiene formato de URL de YouTube."""
        patterns = [
            r"^(https?://)?(www\.)?(youtube\.com/watch\?v=[\w-]{11})",
            r"^(https?://)?(www\.)?(youtu\.be/[\w-]{11})",
            r"^(https?://)?(www\.)?(youtube\.com/shorts/[\w-]{11})",
            r"^(https?://)?(www\.)?(youtube\.com/live/[\w-]{11})",
        ]
        return any(re.match(p, url.strip()) for p in patterns)

    @classmethod
    def prepare_audio(cls, url: str, cache_dir: Path) -> dict:
        """
        Descarga el audio del video de YouTube en el directorio de caché
        o reutiliza el archivo si ya fue descargado previamente.
        Devuelve un diccionario con metadatos y la ruta local del archivo.
        """
        url = url.strip()
        if not cls.is_valid_url(url):
            raise ValueError(f"URL de YouTube inválida: '{url}'")

        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        ydl_opts_info = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as err:
            raise ValueError(f"No se pudo obtener información del video: {err}")

        if not info:
            raise ValueError("No se encontraron datos para el video de YouTube especificado.")

        video_id = info.get("id")
        duration = info.get("duration") or 0
        title = info.get("title", "Video de YouTube")

        if duration > cls.MAX_DURATION_SECONDS:
            raise ValueError(
                f"El video dura {duration // 60} minutos. El límite máximo admitido es de 2 horas."
            )

        target_file = cache_dir / f"{video_id}.mp3"

        # Si ya existe en caché, evitamos re-descargar
        if not target_file.exists():
            ydl_opts_download = {
                "format": "bestaudio/best",
                "outtmpl": str(cache_dir / f"{video_id}.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "quiet": True,
                "no_warnings": True,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                    ydl.download([url])
            except Exception as err:
                raise RuntimeError(f"Error al descargar audio de YouTube: {err}")

        if not target_file.exists():
            # Buscar si se guardó con otra extensión de audio
            matching = list(cache_dir.glob(f"{video_id}.*"))
            if matching:
                target_file = matching[0]
            else:
                raise FileNotFoundError(f"No se pudo encontrar el archivo descargado para el video {video_id}")

        return {
            "video_id": video_id,
            "title": title,
            "duration": duration,
            "file_path": target_file,
            "filename": target_file.name,
        }

    async def prepare(self) -> dict:
        """Ejecuta la preparación/descarga en un hilo separado de forma asíncrona."""
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(
            None,
            self.prepare_audio,
            self.url,
            self.cache_dir,
        )
        self.video_info = info
        self.file_path = info["file_path"]
        self._mp3_source = MP3AudioSource(
            self.file_path,
            start_offset=self.start_offset,
            pause_event=self.pause_event,
        )
        return info

    @property
    def current_position(self) -> float:
        if self._mp3_source:
            return self._mp3_source.current_position
        return self.start_offset

    async def stream(self):
        """
        Entrega chunks PCM mono 16 kHz delegando en MP3AudioSource
        una vez preparado el audio.
        """
        if not self._mp3_source:
            await self.prepare()

        async for chunk in self._mp3_source.stream():
            yield chunk
