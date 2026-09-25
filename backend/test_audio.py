import asyncio
import sys
from pathlib import Path

# Permitir ejecutar directamente como script o como módulo
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.audio.mp3_source import MP3AudioSource


async def main():

    audio_path = (
        BASE_DIR
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
            f"{len(chunk)} bytes",
            flush=True,
        )

        # Solo probamos algunos chunks.
        if chunks >= 5:
            break

    print(flush=True)
    print("Prueba terminada", flush=True)
    print(f"Chunks recibidos: {chunks}", flush=True)
    print(f"Bytes recibidos: {total_bytes}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())