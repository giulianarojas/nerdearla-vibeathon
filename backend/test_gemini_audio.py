import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.audio.mp3_source import MP3AudioSource
from backend.gemini_service import GeminiService


async def main():

    audio_path = (
        BASE_DIR
        / "audio"
        / "charla-nerdearla-1.mp3"
    )

    audio_source = MP3AudioSource(audio_path)
    gemini = GeminiService()

    print("Conectando con Gemini...", flush=True)

    async with await gemini.connect() as session:

        print("Gemini conectado.", flush=True)

        async def send_audio():

            try:
                async for chunk in audio_source.stream():

                    await gemini.send_audio(
                        session,
                        chunk
                    )

                await gemini.end_audio(session)

                print("Audio enviado completamente.", flush=True)

            except Exception as error:

                print(
                    "Error enviando audio:",
                    error,
                    flush=True
                )

        async def receive_transcriptions():

            try:

                async for result in (
                    gemini.receive_transcriptions(
                        session
                    )
                ):

                    print(
                        f"[{result['type']}] "
                        f"{result['text']}",
                        flush=True
                    )

            except Exception as error:

                print(
                    "Error recibiendo Gemini:",
                    error,
                    flush=True
                )

        await asyncio.gather(
            send_audio(),
            receive_transcriptions(),
        )


if __name__ == "__main__":
    asyncio.run(main())