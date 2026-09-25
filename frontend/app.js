async function initializeSession() {
    const params = new URLSearchParams(window.location.search);

    let sessionId = params.get("sala");

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
}

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

initializeSession();

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

loadAudioFiles();

// reproducir los audios
const audioSelect =
    document.getElementById("audioSelect");

const audioPlayer =
    document.getElementById("audioPlayer");

const playButton =
    document.getElementById("playButton");

playButton.addEventListener("click", () => {

    const selectedAudio = audioSelect.value;

    if (!selectedAudio) {
        alert("Seleccioná un audio");
        return;
    }

    audioPlayer.src = `/audio/${selectedAudio}`;

    audioPlayer.play();
});