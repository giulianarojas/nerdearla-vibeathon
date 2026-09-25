import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.audio.mp3_source import MP3AudioSource
from backend.audio.youtube_source import YouTubeAudioSource
from backend.session_manager import SessionManager
from fastapi.testclient import TestClient
from backend.main import app


class TestNerdearlaCaptions(unittest.TestCase):

    def setUp(self):
        self.session_manager = SessionManager(max_sessions=3)
        self.client = TestClient(app)

    def test_session_manager_lifecycle(self):
        # 1. Crear salas dinámicamente
        sala1 = self.session_manager.create_session()
        self.assertEqual(sala1, "sala-1")
        sala2 = self.session_manager.create_session()
        self.assertEqual(sala2, "sala-2")

        # 2. Listar salas
        salas = self.session_manager.list_session()
        self.assertIn("sala-1", salas)
        self.assertIn("sala-2", salas)

        # 3. Pausar y reanudar
        self.session_manager.pause_session(sala1)
        # cuando pause_event es None al inicio, el estado solo cambia si hay pause_event o se valida
        self.session_manager.stop_session(sala1)
        session = self.session_manager.get_session(sala1)
        self.assertEqual(session["status"], "finished")

        # 4. Máximo de sesiones
        sala3 = self.session_manager.create_session()
        with self.assertRaises(RuntimeError):
            self.session_manager.create_session()

        # 5. Borrado
        self.session_manager.delete_session(sala1)
        self.assertNotIn(sala1, self.session_manager.list_session())

    def test_youtube_url_validation(self):
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/live/dQw4w9WgXcQ",
        ]
        invalid_urls = [
            "https://vimeo.com/123456",
            "https://google.com",
            "not a url",
            "",
        ]

        for url in valid_urls:
            self.assertTrue(YouTubeAudioSource.is_valid_url(url), f"Debería ser válida: {url}")

        for url in invalid_urls:
            self.assertFalse(YouTubeAudioSource.is_valid_url(url), f"Debería ser inválida: {url}")

    def test_mp3_audio_source_init(self):
        existing_file = BASE_DIR / "audio" / "charla-nerdearla-1.mp3"
        source = MP3AudioSource(existing_file, start_offset=5.5)
        self.assertEqual(source.start_offset, 5.5)
        self.assertEqual(source.chunk_size, 3200)

        with self.assertRaises(FileNotFoundError):
            MP3AudioSource(BASE_DIR / "audio" / "non_existing.mp3")

    def test_api_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_api_list_audios(self):
        response = self.client.get("/api/audios")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("audio", data)
        self.assertTrue(any("charla-nerdearla" in a for a in data["audio"]))

    def test_api_create_and_get_session(self):
        response = self.client.post("/api/sessions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        session_id = data["session_id"]
        self.assertTrue(session_id.startswith("sala-"))

        get_res = self.client.get(f"/api/sessions/{session_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["session_id"], session_id)

    def test_api_youtube_invalid_url(self):
        response = self.client.post(
            "/api/youtube/prepare",
            json={"url": "https://example.com/invalid"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
