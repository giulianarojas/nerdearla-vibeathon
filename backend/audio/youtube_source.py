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
            r"^(https?://)?(youtube\.com/shorts/[\w-]{11})",
            r"^(https?://)?(www\.)?(youtube\.com/shorts/[\w-]{11})",
            r"^(https?://)?(youtube\.com/live/[\w-]{11})",
            r"^(https?://)?(www\.)?(youtube\.com/live/[\w-]{11})",
        ]
        return any(re.match(p, url.strip()) for p in patterns)

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extrae el ID de 11 caracteres del video de YouTube mediante regex."""
        match = re.search(r"(?:v=|\/|be\/|shorts\/|live\/)([0-9A-Za-z_-]{11})", url.strip())
        return match.group(1) if match else None

    @staticmethod
    def _clean_error(err: Exception) -> str:
        """Limpia secuencias de escape ANSI y formatea mensajes de error de forma legible."""
        msg = str(err)
        # Eliminar secuencias ANSI tipo [0;31m
        msg = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", msg)
        msg = re.sub(r"\[0;[0-9]+m", "", msg)
        msg = re.sub(r"\[0m", "", msg)

        if "getaddrinfo failed" in msg or "11001" in msg:
            return "No se pudo conectar a YouTube (error de resolución DNS / conexión a internet). Verificá tu conexión a la red."
        if "Sign in to confirm you" in msg or "bot" in msg.lower():
            return "YouTube ha solicitado verificación para este video. Probá con otra charla o utilizá los audios locales de prueba."
        if "429" in msg or "Too Many Requests" in msg:
            return "Límite de solicitudes de YouTube alcanzado temporalmente. Probá en unos instantes o utilizá un audio local."

        # Limpiar prefijos redundantes
        msg = msg.replace("ERROR: [youtube]", "").strip()
        return msg

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

        video_id = cls.extract_video_id(url)

        # 1. Si el archivo ya existe en caché, retornarlo inmediatamente sin llamadas de red
        if video_id:
            cached_file = cache_dir / f"{video_id}.mp3"
            if cached_file.exists():
                return {
                    "video_id": video_id,
                    "title": f"Video ({video_id})",
                    "duration": 0,
                    "file_path": cached_file,
                    "filename": cached_file.name,
                }

        # 2. Configuración optimizada de yt-dlp con clientes móviles para evitar errores 429 y bot checks
        ydl_common_opts = {
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "mweb"]
                }
            }
        }

        ydl_opts_info = dict(ydl_common_opts)
        ydl_opts_info["skip_download"] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as err:
            clean_msg = cls._clean_error(err)
            raise ValueError(f"No se pudo obtener información del video: {clean_msg}")

        if not info:
            raise ValueError("No se encontraron datos para el video de YouTube especificado.")

        video_id = info.get("id") or video_id
        duration = info.get("duration") or 0
        title = info.get("title", f"Video {video_id}")

        if duration > cls.MAX_DURATION_SECONDS:
            raise ValueError(
                f"El video dura {duration // 60} minutos. El límite máximo admitido es de 2 horas."
            )

        target_file = cache_dir / f"{video_id}.mp3"

        # 3. Descarga si no existe
        if not target_file.exists():
            ydl_opts_download = dict(ydl_common_opts)
            ydl_opts_download.update({
                "format": "bestaudio/best",
                "outtmpl": str(cache_dir / f"{video_id}.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            })

            try:
                with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                    ydl.download([url])
            except Exception as err:
                clean_msg = cls._clean_error(err)
                raise RuntimeError(f"Error al descargar audio de YouTube: {clean_msg}")

        if not target_file.exists():
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
