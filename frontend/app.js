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


