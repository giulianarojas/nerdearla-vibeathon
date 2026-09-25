from abc import ABC, abstractmethod


class AudioSource(ABC):
    """
    Interfaz base para las fuentes de audio.
    """

    @abstractmethod
    async def stream(self):
        """
        Devuelve fragmentos de audio progresivamente.
        """
        pass