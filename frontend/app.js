const params = new URLSearchParams(window.location.search);

let sessionId = params.get("sala");

console.log("Sala actual:", sessionId);