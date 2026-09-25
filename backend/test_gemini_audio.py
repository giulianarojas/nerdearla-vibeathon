import asyncio
from pathlib import Path

from backend.audio.mp3_source import MP3AudioSource
from backend.gemini_service import GeminiService


async def main():

    audio_path = (
        Path(__file__).resolve().parent.parent
        / "audio"
        / "charla-nerdearla-1.mp3"
    )

    audio_source = MP3AudioSource(audio_path)
    gemini = GeminiService()

    print("Conectando con Gemini...")

    async with await gemini.connect() as session:

        print("Gemini conectado.")

        async def send_audio():

            try:
                async for chunk in audio_source.stream():

                    await gemini.send_audio(
                        session,
                        chunk
                    )

                await gemini.end_audio(session)

                print("Audio enviado completamente.")

            except Exception as error:

                print(
                    "Error enviando audio:",
                    error
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
                        f"{result['text']}"
                    )

            except Exception as error:

                print(
                    "Error recibiendo Gemini:",
                    error
                )

        await asyncio.gather(
            send_audio(),
            receive_transcriptions(),
        )


if __name__ == "__main__":
    asyncio.run(main())