# 🎙️ Nerdearla Live Captions — Transcripción y Traducción Simultánea a Escala

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-teal.svg)](https://fastapi.tiangolo.com/)
[![Gemini Live API](https://img.shields.io/badge/AI-Google%20Gemini%20Live-orange.svg)](https://ai.google.dev/)
[![Event](https://img.shields.io/badge/Nerdearla-Vibeathon%202026-F23D4C.svg)](https://nerdearla.org/)

**Nerdearla Live Captions** es una plataforma *open source* diseñada para brindar **transcripción de audio en vivo y traducción simultánea (inglés &rarr; español)** para conferencias técnicas de gran escala. Construida específicamente para el desafío de la **Vibeathon — Nerdearla Argentina 2026**, permite operar múltiples salas o escenarios de forma simultánea, independiente y accesible desde cualquier navegador web.

---

## 📌 1. El Problema que Resuelve

Las conferencias técnicas multiescenario como **Nerdearla** tradicionalmente dependen de servicios comerciales cerrados para subtitulación y traducción en vivo (un proveedor para transcripción español&rarr;español y otro para traducción inglés&rarr;español). Este esquema presenta importantes limitaciones:
- **Costos elevados** que limitan la accesibilidad en eventos comunitarios.
- **Operación manual compleja** con operadores por cada track.
- **Falta de escalabilidad**: en ediciones con más de 30 charlas en inglés concurrentes, coordinar servicios cerrados se vuelve inviable o prohibitivo.
- **Dificultad de replicabilidad**: las comunidades de software libre de la región no pueden reutilizar la infraestructura fácilmente.

**Nerdearla Live Captions** proporciona una alternativa 100% de código abierto que democratiza el acceso simultáneo a conferencias técnicas mediante inteligencia artificial generativa en tiempo real.

---

## ⚡ 2. Características Principales

- **Salas Dinámicas Concurrentes:** Creación instantánea de salas (`sala-1`, `sala-2`, `sala-N`) sin reiniciar el servidor ni tocar código. Cada sala cuenta con su propio flujo de audio, sesión de IA y traducción independiente.
- **Transcripción y Traducción en Tiempo Real:** Genera la transcripción original (inglés) y la traducción al español en paralelo con latencia mínima, potenciada por **Gemini Live API**.
- **Soporte de Múltiples Fuentes de Audio:**
  - **Audios locales de prueba (MP3/WAV):** Carga inmediata de grabaciones de conferencias.
  - **Videos de YouTube:** Extracción y procesamiento de audio de cualquier charla o livestream de YouTube mediante `yt-dlp` con almacenamiento en caché inteligente.
- **Sincronización Temporal Precisa:**
  - Control de derivas (drift) y alineación milimétrica con el reproductor de audio web.
  - Soporte completo del ciclo de vida de reproducción: **Play &rarr; Pausa &rarr; Reanudar &rarr; Adelantar/Retroceder (Seek) &rarr; Stop**. Al pausar el audio, los subtítulos se congelan de inmediato y se reanudan exactamente donde quedaron.
- **UI Moderna y Accesible con Identidad Nerdearla:** Diseñada bajo la paleta oficial de Nerdearla (`#F23D4C`, `#14A697`, `#F2A81D`, `#400101`, `#F2F2F2`), con badges de estado en vivo, indicadores visuales de tiempo y modo oscuro de alto contraste.
- **Arquitectura Escalable:** Comunicación bidireccional vía **WebSockets** y API REST con FastAPI.

---

## 🏗️ 3. Arquitectura del Proyecto

```
nerdearla-vibeathon/
│
├── backend/
│   ├── main.py                 # Aplicación FastAPI, endpoints REST y WebSockets
│   ├── config.py               # Carga de entorno y configuración de Gemini
│   ├── gemini_service.py       # Cliente Gemini Live (bidireccional, transcripción + traducción)
│   ├── session_manager.py      # Gestor de salas dinámicas, ciclo de vida (play/pause/seek)
│   ├── test_audio.py           # Script de prueba rápida para streaming de audio
│   ├── test_gemini_audio.py    # Script de prueba de conexión directa con Gemini Live
│   │
│   ├── audio/
│   │   ├── audio_source.py     # Interfaz abstracta base (AudioSource)
│   │   ├── mp3_source.py       # Decodificación PCM 16kHz en tiempo real con FFmpeg
│   │   └── youtube_source.py   # Extracción y caché de audio de YouTube vía yt-dlp
│   │
│   └── websocket/
│       └── handlers.py         # Manejadores de acciones WebSocket (play, pause, resume, seek, stop)
│
├── frontend/
│   ├── index.html              # Vista web: salas, selector de audio/YouTube, subtítulos en vivo
│   ├── style.css               # Estilos oficiales Nerdearla (responsive, tema oscuro accesible)
│   └── app.js                  # Lógica de cliente, sincronización temporal y WebSockets
│
├── audio/                      # Directorio de audios de muestra y caché de YouTube
│   ├── charla-nerdearla-1.mp3
│   ├── charla-nerdearla-2.mp3
│   └── youtube_cache/          # Archivos de YouTube descargados automáticamente
│
├── tests/
│   └── test_backend.py         # Suite de pruebas automatizadas (unitarias e integración)
│
├── .env.example                # Plantilla de variables de entorno
├── requirements.txt            # Dependencias de Python
├── LICENSE                     # Licencia Apache 2.0 (OSI Approved)
└── README.md                   # Documentación completa del proyecto
```

### Componentes Clave:
1. **`SessionManager`**: Controla el estado de cada sala concurrente, sus fuentes de audio y eventos de pausa asíncronos (`asyncio.Event`), asegurando aislamiento total entre escenarios.
2. **`AudioSource` & Implementaciones (`MP3AudioSource`, `YouTubeAudioSource`)**: Convierten cualquier fuente a PCM mono 16 kHz y entregan chunks controlados para emular un stream de escenario en tiempo real.
3. **`GeminiService`**: Gestiona la sesión Live con Gemini (`gemini-3.5-live-translate-preview`), configurando modalidades de audio bidireccional y traducción simultánea.
4. **`app.js`**: Controla la visualización de los subtítulos, vinculando la cola de mensajes con la propiedad `currentTime` del reproductor nativo para garantizar sincronización perfecta.

---

## 📋 4. Requisitos Previos

- **Python**: Versión **3.10 o superior** (probado y verificado en Python 3.13).
- **FFmpeg**: Necesario para la decodificación y remuestreo de audio a PCM 16 kHz.
  - *Windows*: Instalar vía `winget install Gyan.FFmpeg` o `choco install ffmpeg`.
  - *Linux (Debian/Ubuntu)*: `sudo apt update && sudo apt install -y ffmpeg`.
  - *macOS*: `brew install ffmpeg`.
- **API Key de Gemini**: Obtener una clave gratuita en [Google AI Studio](https://aistudio.google.com/).

---

## 🚀 5. Instalación y Configuración

### Paso 1: Clonar el repositorio
```bash
git clone https://github.com/giulianarojas/nerdearla-vibeathon.git
cd nerdearla-vibeathon
```

### Paso 2: Crear y activar entorno virtual
- En **Linux / macOS**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- En **Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

### Paso 3: Instalar dependencias
```bash
pip install -r requirements.txt
```

### Paso 4: Configurar variables de entorno
Crea un archivo `.env` en la raíz del proyecto basándote en `.env.example`:
```ini
# .env
GEMINI_API_KEY=tu_api_key_de_gemini_aqui
GEMINI_MODEL=gemini-3.5-live-translate-preview
```

---

## 🏃 6. Ejecución del Proyecto

Levanta el servidor con `uvicorn`:
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Una vez levantado, abrí tu navegador en:
👉 **`http://localhost:8000`**

---

## 💡 7. Guía de Uso

1. **Ingreso a la Sala:** Al abrir la aplicación, entrarás automáticamente a una sala (ej: `sala-1`).
2. **Seleccionar Fuente de Audio:**
   - **Opción A (Audio Local):** En la pestaña *📁 Audio Local*, seleccioná una de las charlas provistas (ej. `charla-nerdearla-1.mp3`).
   - **Opción B (Video de YouTube):** En la pestaña *📹 Video de YouTube*, pegá el link de una charla o panel (ej. `https://www.youtube.com/watch?v=...`) y hacé clic en **Extraer audio**. El sistema procesará los metadatos y preparará el track de audio.
3. **Reproducir y Ver Subtítulos:**
   - Hacé clic en **▶ Reproducir**.
   - El audio comenzará a reproducirse y el estado cambiará a **● En vivo (Transcribiendo)**.
   - En el recuadro superior verás la **transcripción original en inglés**, y en el inferior la **traducción en español**, en tiempo real y sincronizadas con lo que escuchás.
4. **Controles de Reproducción:**
   - Podés pausar en cualquier momento: los subtítulos se congelarán de inmediato. Al reanudar, continuarán desde ese segundo exacto.
   - Podés adelantar o retroceder (seek) usando los controles del reproductor.
5. **Crear Múltiples Salas en Simultáneo:**
   - Hacé clic en el botón **➕ Nueva sala**.
   - Se abrirá una nueva pestaña (ej. `http://localhost:8000/?sala=sala-2`).
   - En esa pestaña podés seleccionar otro audio o video de YouTube y reproducirlo en paralelo con total independencia.

---

## 📈 8. Escalabilidad y Despliegue en Producción

El diseño desacoplado de **Nerdearla Live Captions** permite escalar desde un escenario individual hasta eventos masivos con decenas de tracks concurrentes:

1. **Concurrencia Asíncrona (I/O Bound):**
   - FastAPI y `asyncio` manejan miles de conexiones WebSocket simultáneas con mínima sobrecarga de memoria.
   - La decodificación con FFmpeg se ejecuta en subprocesos asíncronos sin bloquear el event loop principal.
2. **Escalado Horizontal:**
   - Para despliegues con 10 o más escenarios en vivo, se recomienda desplegar el backend en contenedores Docker detrás de un reverse proxy (ej. NGINX o Cloud Run / Kubernetes).
   - Utilizar un broker de mensajes (ej. Redis Pub/Sub) para distribuir los eventos WebSocket si se requiere balanceo de carga entre múltiples réplicas del backend.
3. **Caché y CDN:**
   - Los audios estáticos y transcripciones procesadas pueden almacenarse en Cloud Storage (GCS) o distribuirse mediante CDN para reducir latencia hacia la audiencia global.

---

## 🧪 9. Pruebas Automatizadas

El proyecto incluye una suite de pruebas unitarias y de integración que validan el ciclo de vida de las salas, las fuentes de audio y las rutas de la API:
```bash
python -m unittest tests/test_backend.py
```

---

## 🗺️ 10. Roadmap y Próximas Mejoras

- [ ] **Integración OBS / vMix:** Endpoint de salida NDI o browser source transparente para incrustar subtítulos directamente en el streaming de video.
- [ ] **Soporte Multilingüe Adicional:** Expansión a portugués, francés y alemán.
- [ ] **Glosario Técnico Personalizado:** Inyección de diccionarios de términos técnicos de tecnología (ej. Kubernetes, Linux, GraphQL) en el prompt de Gemini para evitar errores fonéticos.
- [ ] **Exportación Automática:** Descarga de la transcripción y traducción completa al finalizar la sesión en formato SRT, VTT y texto plano.
- [ ] **Dashboard de Monitoreo para Operadores:** Panel técnico para monitorear latencia por sala, estado de conexión a la API y consumo de tokens.

---

## 📄 11. Licencia

Este proyecto está liberado bajo la licencia de código abierto **Apache License 2.0** (aprobada por la Open Source Initiative - OSI). Para más detalles, consultar el archivo [LICENSE](LICENSE).

---

## 👥 12. Créditos y Agradecimientos

- **Nerdearla Argentina**: Inspiración y marco de la hackatón **Vibeathon 2026**.
- **Google DeepMind / Google AI**: Capacidades de audio y traducción en vivo provistas por **Gemini Live API**.
- Desarrollado con pasión para hacer los eventos tecnológicos más accesibles e inclusivos para toda la comunidad.
