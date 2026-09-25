/**
 * Nerdearla Live Captions — Cliente Web Frontend
 * Implementación de Reloj Maestro (Master Clock), congelamiento estricto
 * de subtítulos en pausa y sincronización temporal precisa.
 */

let socket = null;
let sessionId = null;
let currentSourceMode = "local"; // "local" | "youtube"
let currentAudioIdentifier = null;
let isPreparingYoutube = false;
let clockSyncTimer = null;
let isAudioPaused = true;

// Cola de subtítulos para sincronización temporal con audioPlayer.currentTime
const captionQueue = {
    original: [],
    translation: []
};

// --- Inicialización de Sala ---
async function initializeSession() {
    const params = new URLSearchParams(window.location.search);
    sessionId = params.get("sala");

    if (!sessionId) {
        try {
            const response = await fetch("/api/sessions", { method: "POST" });
            const data = await response.json();
            if (!data.session_id) {
                throw new Error("Respuesta inválida al crear sala");
            }
            window.location.href = `/?sala=${data.session_id}`;
            return;
        } catch (error) {
            console.error("Error inicializando sala:", error);
            alert("No se pudo conectar con el servidor para crear la sala.");
            return;
        }
    }

    const roomNameEl = document.getElementById("roomName");
    if (roomNameEl) {
        roomNameEl.textContent = sessionId;
    }

    connectWebSocket(sessionId);
    loadAudioFiles();
    setupEventListeners();
}

// --- Conexión WebSocket ---
function connectWebSocket(sessionId) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log(`[WS] Conectado a la sala: ${sessionId}`);
        updateStatus("created");
    };

    socket.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            handleIncomingMessage(message);
        } catch (err) {
            console.error("[WS] Error parseando mensaje:", err, event.data);
        }
    };

    socket.onerror = (error) => {
        console.error("[WS] Error en socket:", error);
        updateStatus("error");
    };

    socket.onclose = () => {
        console.warn("[WS] Conexión cerrada. Reconectando en 3s...");
        setTimeout(() => {
            if (!socket || socket.readyState === WebSocket.CLOSED) {
                connectWebSocket(sessionId);
            }
        }, 3000);
    };
}

// --- Procesamiento de Mensajes Entrantes con Congelamiento Estricto ---
function handleIncomingMessage(message) {
    const audioPlayer = document.getElementById("audioPlayer");

    // REGLA FUNDAMENTAL DE PAUSA:
    // Si el reproductor está en pausa o detenido, NINGÚN subtítulo entrante
    // debe modificar el DOM. La pantalla se congela inmediatamente.
    const isPaused = isAudioPaused || (audioPlayer ? audioPlayer.paused : true);

    if (message.type === "original") {
        if (message.text && !isPaused) {
            queueOrDisplayCaption("original", message.text, message.timestamp);
        }
    } else if (message.type === "translation") {
        if (message.text && !isPaused) {
            queueOrDisplayCaption("translation", message.text, message.timestamp);
        }
    } else if (message.type === "status") {
        updateStatus(message.status);
    } else if (message.type === "error") {
        console.error("[Servidor]", message.message);
        updateStatus("error", message.message);
    }
}

// --- Sincronización Temporal de Subtítulos con Reloj Maestro ---
function queueOrDisplayCaption(type, text, timestamp) {
    const audioPlayer = document.getElementById("audioPlayer");
    const currentTime = audioPlayer ? audioPlayer.currentTime : 0;

    // Si no hay reproductor o no tiene timestamp, se muestra directo
    if (!audioPlayer || timestamp === undefined || timestamp === null) {
        renderCaption(type, text);
        return;
    }

    // Margen de tolerancia de 0.3s para fluidez
    if (timestamp <= currentTime + 0.35) {
        renderCaption(type, text);
    } else {
        // Si el modelo inferió con anticipación, lo encolamos para el segundo exacto
        captionQueue[type].push({ text, timestamp });
        captionQueue[type].sort((a, b) => a.timestamp - b.timestamp);
    }
}

function processCaptionQueue() {
    const audioPlayer = document.getElementById("audioPlayer");
    if (!audioPlayer || audioPlayer.paused || isAudioPaused) {
        return; // Congelado absoluto mientras esté en pausa
    }

    const currentTime = audioPlayer.currentTime;

    ["original", "translation"].forEach(type => {
        const queue = captionQueue[type];
        while (queue.length > 0 && queue[0].timestamp <= currentTime + 0.3) {
            const item = queue.shift();
            renderCaption(type, item.text);
        }
    });
}

function renderCaption(type, text) {
    const audioPlayer = document.getElementById("audioPlayer");
    if (audioPlayer && audioPlayer.paused) {
        return; // Guardrail adicional de seguridad
    }
    const element = document.getElementById(type);
    if (element) {
        element.textContent = text;
    }
}

// --- Emisión del Reloj Maestro hacia el Backend ---
function sendClockSync() {
    const audioPlayer = document.getElementById("audioPlayer");
    if (!audioPlayer || !socket || socket.readyState !== WebSocket.OPEN) {
        return;
    }

    socket.send(JSON.stringify({
        action: "sync_clock",
        currentTime: audioPlayer.currentTime,
        paused: audioPlayer.paused || isAudioPaused
    }));
}

function startClockSyncLoop() {
    if (clockSyncTimer) clearInterval(clockSyncTimer);
    clockSyncTimer = setInterval(() => {
        const audioPlayer = document.getElementById("audioPlayer");
        if (audioPlayer && !audioPlayer.paused) {
            sendClockSync();
            processCaptionQueue();
        }
    }, 150);
}

function stopClockSyncLoop() {
    if (clockSyncTimer) {
        clearInterval(clockSyncTimer);
        clockSyncTimer = null;
    }
}

// --- Estado Visual y Badges ---
function updateStatus(status, customMsg = null) {
    const textElement = document.getElementById("status-text");
    const indicator = document.getElementById("status-indicator");

    const labels = {
        created: "Listo para reproducir",
        running: "En vivo (Transcribiendo)",
        paused: "En pausa",
        finished: "Finalizado",
        stopped: "Detenido",
        error: customMsg || "Error en la sesión"
    };

    if (textElement) {
        textElement.textContent = labels[status] || status;
    }

    if (indicator) {
        indicator.className = "status-dot";
        if (status === "running") {
            indicator.classList.add("live");
        } else if (status === "paused") {
            indicator.classList.add("paused");
        } else if (status === "error") {
            indicator.classList.add("error");
        }
    }
}

// --- Carga de Audios Locales ---
async function loadAudioFiles() {
    try {
        const response = await fetch("/api/audios");
        const data = await response.json();
        const audioSelect = document.getElementById("audioSelect");
        if (!audioSelect) return;

        audioSelect.innerHTML = "";
        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Seleccionar charla de prueba...";
        audioSelect.appendChild(defaultOption);

        if (Array.isArray(data.audio)) {
            data.audio.forEach(fileName => {
                if (fileName.startsWith(".")) return;
                const option = document.createElement("option");
                option.value = fileName;
                option.textContent = fileName.replace("youtube_cache/", "📹 [YouTube] ");
                audioSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error("Error cargando audios:", error);
    }
}

function formatSeconds(secs) {
    if (isNaN(secs) || secs < 0) return "00:00";
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

// --- Configuración de Eventos del Reproductor y la UI ---
function setupEventListeners() {
    const newSessionButton = document.getElementById("newSessionButton");
    const playButton = document.getElementById("playButton");
    const audioSelect = document.getElementById("audioSelect");
    const audioPlayer = document.getElementById("audioPlayer");
    const tabLocal = document.getElementById("tabLocal");
    const tabYoutube = document.getElementById("tabYoutube");
    const localSourcePanel = document.getElementById("localSourcePanel");
    const youtubeSourcePanel = document.getElementById("youtubeSourcePanel");
    const loadYoutubeButton = document.getElementById("loadYoutubeButton");
    const youtubeUrlInput = document.getElementById("youtubeUrlInput");
    const currentTimeDisplay = document.getElementById("currentTimeDisplay");

    // Botón Nueva Sala (abre pestaña nueva independiente)
    newSessionButton?.addEventListener("click", async () => {
        try {
            const response = await fetch("/api/sessions", { method: "POST" });
            const data = await response.json();
            if (data.session_id) {
                window.open(`/?sala=${data.session_id}`, "_blank");
            }
        } catch (err) {
            alert("No se pudo crear la nueva sala.");
        }
    });

    // Pestañas de origen
    tabLocal?.addEventListener("click", () => {
        currentSourceMode = "local";
        tabLocal.classList.add("active");
        tabYoutube.classList.remove("active");
        localSourcePanel.classList.add("active");
        youtubeSourcePanel.classList.remove("active");
    });

    tabYoutube?.addEventListener("click", () => {
        currentSourceMode = "youtube";
        tabYoutube.classList.add("active");
        tabLocal.classList.remove("active");
        youtubeSourcePanel.classList.add("active");
        localSourcePanel.classList.remove("active");
    });

    // Cargar video de YouTube
    loadYoutubeButton?.addEventListener("click", async () => {
        const url = youtubeUrlInput.value.trim();
        if (!url) {
            alert("Por favor ingresá un enlace de YouTube.");
            return;
        }

        loadYoutubeButton.disabled = true;
        loadYoutubeButton.textContent = "⏳ Extrayendo audio...";
        isPreparingYoutube = true;

        try {
            const response = await fetch("/api/youtube/prepare", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (!response.ok) {
                alert(data.detail || "Error al procesar el enlace de YouTube.");
                return;
            }

            currentAudioIdentifier = data.audio;
            audioPlayer.src = `/audio/${data.audio}`;

            const infoBox = document.getElementById("youtubeInfo");
            const titleEl = document.getElementById("youtubeTitle");
            const durationEl = document.getElementById("youtubeDuration");

            if (infoBox && titleEl && durationEl) {
                infoBox.classList.remove("hidden");
                titleEl.textContent = data.title;
                durationEl.textContent = `(${formatSeconds(data.duration)})`;
            }

            updateStatus("created");
        } catch (error) {
            console.error("Error al preparar YouTube:", error);
            alert("Error de conexión al procesar el video de YouTube.");
        } finally {
            loadYoutubeButton.disabled = false;
            loadYoutubeButton.textContent = "Extraer audio";
            isPreparingYoutube = false;
        }
    });

    // Selección de archivo local
    audioSelect?.addEventListener("change", () => {
        if (audioSelect.value) {
            currentAudioIdentifier = audioSelect.value;
            audioPlayer.src = `/audio/${audioSelect.value}`;
        }
    });

    // Botón Reproducir Principal
    playButton?.addEventListener("click", async () => {
        let audioToPlay = currentAudioIdentifier;

        if (currentSourceMode === "local") {
            audioToPlay = audioSelect.value;
            if (!audioToPlay) {
                alert("Por favor seleccioná un archivo de audio local de la lista.");
                return;
            }
            currentAudioIdentifier = audioToPlay;
        } else if (currentSourceMode === "youtube") {
            if (!currentAudioIdentifier) {
                if (youtubeUrlInput.value.trim()) {
                    await loadYoutubeButton.click();
                    audioToPlay = currentAudioIdentifier;
                } else {
                    alert("Por favor ingresá y extraé un enlace de YouTube primero.");
                    return;
                }
            }
        }

        if (!audioToPlay) return;

        // Limpiamos cola anterior
        captionQueue.original = [];
        captionQueue.translation = [];

        try {
            if (audioPlayer.src !== `${window.location.origin}/audio/${audioToPlay}`) {
                audioPlayer.src = `/audio/${audioToPlay}`;
            }

            const response = await fetch(`/api/sessions/${sessionId}/start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    audio: audioToPlay,
                    start_offset: audioPlayer.currentTime || 0.0
                })
            });

            const data = await response.json();

            if (!response.ok) {
                alert(data.detail || "No se pudo iniciar la sesión de transcripción.");
                return;
            }

            isAudioPaused = false;
            await audioPlayer.play();
            updateStatus("running");
            startClockSyncLoop();

        } catch (error) {
            console.error("Error iniciando reproducción:", error);
            alert("No se pudo iniciar la reproducción.");
        }
    });

    // Eventos Nativos del Elemento HTML5 <audio>
    audioPlayer?.addEventListener("play", () => {
        isAudioPaused = false;
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                action: "resume",
                currentTime: audioPlayer.currentTime
            }));
        }
        updateStatus("running");
        startClockSyncLoop();
    });

    audioPlayer?.addEventListener("pause", () => {
        // CONGELAMIENTO INMEDIATO:
        isAudioPaused = true;
        stopClockSyncLoop();

        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                action: "pause",
                currentTime: audioPlayer.currentTime
            }));
        }
        updateStatus("paused");
    });

    audioPlayer?.addEventListener("seeked", () => {
        captionQueue.original = [];
        captionQueue.translation = [];

        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                action: "seek",
                currentTime: audioPlayer.currentTime,
                audio: currentAudioIdentifier,
                paused: audioPlayer.paused
            }));
        }
        if (currentTimeDisplay) {
            currentTimeDisplay.textContent = formatSeconds(audioPlayer.currentTime);
        }
    });

    audioPlayer?.addEventListener("timeupdate", () => {
        if (currentTimeDisplay) {
            currentTimeDisplay.textContent = formatSeconds(audioPlayer.currentTime);
        }
        if (!audioPlayer.paused && !isAudioPaused) {
            sendClockSync();
            processCaptionQueue();
        }
    });

    audioPlayer?.addEventListener("ended", () => {
        isAudioPaused = true;
        stopClockSyncLoop();
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ action: "stop" }));
        }
        updateStatus("finished");
    });
}

// Iniciar app al cargar el DOM
document.addEventListener("DOMContentLoaded", () => {
    initializeSession();
});