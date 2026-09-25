let socket;
let sessionId;

async function initializeSession() {
    const params = new URLSearchParams(window.location.search);

    sessionId = params.get("sala");

    if (!sessionId) {
        const response = await fetch("/api/sessions", {
            method: "POST"
        });

        const data = await response.json();

        if (!data.session_id) {
            throw new Error("No se pudo crear la sala");
        }

        sessionId = data.session_id;

        window.location.href = `/?sala=${sessionId}`;

        return;
    }

    document.getElementById("roomName").textContent = sessionId;

    connectWebSocket(sessionId);
}
//websocket

function connectWebSocket(sessionId) {

    socket = new WebSocket(
        `ws://${window.location.host}/ws/${sessionId}`
    );

    socket.onopen = () => {
        console.log(
            "WebSocket conectado:",
            sessionId
        );
    };

   socket.onmessage = (event) => {

        const message =
            JSON.parse(event.data);

        if (message.type === "original") {

            document.getElementById(
                "original"
            ).textContent = message.text;
        }

        if (message.type === "translation") {

            document.getElementById(
                "translation"
            ).textContent = message.text;
        }

        if (message.type === "status") {

            updateStatus(
                message.status
            );
        }

        if (message.type === "error") {

            console.error(
                message.message
            );

            updateStatus("error");
        }
    };

    socket.onerror = (error) => {
        console.error(
            "WebSocket error:",
            error
        );
    };

    socket.onclose = () => {
        console.log(
            "WebSocket cerrado"
        );
    };
}

function updateStatus(status) {
    const textElement = document.getElementById("status-text");
    const indicator = document.getElementById("status-indicator");

    const labels = {
        created: "Preparando",
        running: "En vivo",
        finished: "Finalizado",
        cancelled: "Cancelado",
        error: "Error"
    };

    textElement.textContent = labels[status] || status;

    // cambia el color del indicador según estado
    const colors = {
        created: "#94a3b8",   // gris
        running: "#22c55e",   // verde
        finished: "#94a3b8",  // gris
        cancelled: "#94a3b8", // gris
        error: "#ef4444"      // rojo
    };

    if (indicator) {
        indicator.style.color = colors[status] || "#94a3b8";
    }
}
//boton de nueva sala
const newSessionButton =
    document.getElementById("newSessionButton");

newSessionButton.addEventListener("click", async () => {

    const response = await fetch("/api/sessions", {
        method: "POST"
    });

    const data = await response.json();

    if (!data.session_id) {
        alert("No se pudo crear una nueva sala");
        return;
    }

    window.open(
        `/?sala=${data.session_id}`,
        "_blank"
    );
});

//cargar los audios
async function loadAudioFiles() {
    const response = await fetch("/api/audios");

    const data = await response.json();

    const audioSelect = document.getElementById("audioSelect");

    data.audio.forEach(fileName => {
        const option = document.createElement("option");

        option.value = fileName;
        option.textContent = fileName;

        audioSelect.appendChild(option);
    });
}

// reproducir los audios
const audioSelect =
    document.getElementById("audioSelect");

const audioPlayer =
    document.getElementById("audioPlayer");

const playButton =
    document.getElementById("playButton");

playButton.addEventListener("click", async() => {

    const selectedAudio = audioSelect.value;

    if (!selectedAudio) {
        alert("Seleccioná un audio");
        return;
    }

    try {

        const response = await fetch(
            `/api/sessions/${sessionId}/start`,
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    audio: selectedAudio
                })
            }
        );

        const data =
            await response.json();

        if (!response.ok) {

            alert(
                data.detail ||
                "No se pudo iniciar la sesión"
            );

            return;
        }

        audioPlayer.src =
            `/audio/${selectedAudio}`;

        await audioPlayer.play();

        updateStatus("running");

    } catch (error) {

        console.error(
            "Error iniciando sesión:",
            error
        );

        alert(
            "No se pudo iniciar la sesión."
        );
    }
});

loadAudioFiles();
initializeSession();