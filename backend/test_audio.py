import asyncio
from pathlib import Path

from backend.audio.mp3_source import MP3AudioSource


async def main():

    audio_path = (
        Path(__file__).resolve().parent.parent
        / "audio"
        / "charla-nerdearla-1.mp3"
    )

    source = MP3AudioSource(audio_path)

    total_bytes = 0
    chunks = 0

    async for chunk in source.stream():

        chunks += 1
        total_bytes += len(chunk)

        print(
            f"Chunk {chunks}: "
            f"{len(chunk)} bytes"
        )

        # Solo probamos algunos chunks.
        if chunks >= 5:
            break

    print()
    print("Prueba terminada")
    print(f"Chunks recibidos: {chunks}")
    print(f"Bytes recibidos: {total_bytes}")


if __name__ == "__main__":
    asyncio.run(main())