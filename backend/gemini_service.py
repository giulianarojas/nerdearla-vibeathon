from google import genai
from google.genai import types

from backend.config import GEMINI_API_KEY, GEMINI_MODEL


class GeminiService:
    """
    Servicio encargado de mantener una conexión
    de traducción en tiempo real con Gemini Live.
    """

    def __init__(self):
        self.client = genai.Client(
            api_key=GEMINI_API_KEY
        )

    async def connect(self):
        """
        Abre una sesión Live de Gemini preparada para
        recibir audio y devolver transcripción + traducción.
        """

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],

            # Transcripción del audio original.
            input_audio_transcription=(
                types.AudioTranscriptionConfig()
            ),

            # Transcripción del audio traducido.
            output_audio_transcription=(
                types.AudioTranscriptionConfig()
            ),

            # Traducción al español.
            translation_config=types.TranslationConfig(
                target_language_code="es",
                echo_target_language=False,
            ),
        )

        return self.client.aio.live.connect(
            model=GEMINI_MODEL,
            config=config,
        )

    async def send_audio(
        self,
        session,
        audio_chunk: bytes,
    ):
        """
        Envía un fragmento de audio PCM a Gemini.
        """

        await session.send_realtime_input(
            audio=types.Blob(
                data=audio_chunk,
                mime_type="audio/pcm;rate=16000",
            )
        )

    async def end_audio(self, session):
        """
        Indica a Gemini que terminó el stream de audio.
        """

        await session.send_realtime_input(
            audio_stream_end=True
        )

    async def receive_transcriptions(self, session):
        """
        Escucha las respuestas de Gemini y devuelve
        transcripción original y traducción.
        """

        async for response in session.receive():

            server_content = response.server_content

            if not server_content:
                continue

            # Inglés: audio original
            if (
                server_content.input_transcription
                and server_content.input_transcription.text
            ):
                yield {
                    "type": "original",
                    "text": server_content.input_transcription.text,
                }

            # Español: traducción
            if (
                server_content.output_transcription
                and server_content.output_transcription.text
            ):
                yield {
                    "type": "translation",
                    "text": server_content.output_transcription.text,
                }