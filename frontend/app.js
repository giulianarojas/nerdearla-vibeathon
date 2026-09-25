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

    console.log("Sala actual:", sessionId);
}

initializeSession();



