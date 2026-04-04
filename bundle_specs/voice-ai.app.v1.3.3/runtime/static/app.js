const statusEl = document.getElementById("status");
const btnStart = document.getElementById("btnStart");
const btnStop = document.getElementById("btnStop");
const btnRaw = document.getElementById("btnRaw");
const transcriptEl = document.getElementById("transcript");
const assistantEl = document.getElementById("assistant");
const toolCardsEl = document.getElementById("toolCards");
const toolRawEl = document.getElementById("toolRaw");

function setStatus(text, cls = "") {
  statusEl.textContent = text;
  statusEl.className = "pill " + cls;
}

function setTranscript(t) {
  transcriptEl.textContent = t || "";
}

function setAssistantMarkdown(md) {
  const text = md || "";
  assistantEl.innerHTML = marked.parse(text);
}

function renderTool(result) {
  // Raw JSON view
  toolRawEl.textContent = result ? JSON.stringify(result, null, 2) : "";

  // Cards/table view (best effort)
  toolCardsEl.innerHTML = "";

  if (!result || typeof result !== "object") return;

  const name = result.name || result.tool || result.type || "tool";
  const res = result.result || result;

  // If result has key/value pairs, show as table
  if (res && typeof res === "object" && !Array.isArray(res)) {
    const card = document.createElement("div");
    card.className = "card";
    card.style.margin = "0";

    const title = document.createElement("div");
    title.style.fontWeight = "750";
    title.style.marginBottom = "10px";
    title.textContent = String(res.title || name);
    card.appendChild(title);

    const table = document.createElement("table");
    for (const [k, v] of Object.entries(res)) {
      if (k === "title") continue;
      const tr = document.createElement("tr");
      const tdK = document.createElement("td");
      tdK.className = "k";
      tdK.textContent = k;
      const tdV = document.createElement("td");
      tdV.className = "v mono";
      tdV.textContent = typeof v === "string" ? v : JSON.stringify(v);
      tr.appendChild(tdK);
      tr.appendChild(tdV);
      table.appendChild(tr);
    }
    card.appendChild(table);
    toolCardsEl.appendChild(card);
  } else {
    const card = document.createElement("div");
    card.className = "card";
    card.style.margin = "0";
    const title = document.createElement("div");
    title.style.fontWeight = "750";
    title.textContent = String(name);
    const pre = document.createElement("pre");
    pre.className = "mono";
    pre.textContent = JSON.stringify(res, null, 2);
    card.appendChild(title);
    card.appendChild(pre);
    toolCardsEl.appendChild(card);
  }
}

let showRaw = false;
btnRaw.addEventListener("click", () => {
  showRaw = !showRaw;
  toolRawEl.style.display = showRaw ? "block" : "none";
  toolCardsEl.style.display = showRaw ? "none" : "grid";
  btnRaw.textContent = showRaw ? "Cards View" : "Raw JSON";
});

const cfg = await fetch("/config/client").then((r) => r.json());

let ws = null;
let audioCtx = null;
let workletNode = null;
let mediaStream = null;

function cleanup() {
  try {
    if (workletNode) workletNode.port.onmessage = null;
  } catch { }
  try {
    if (workletNode) workletNode.disconnect();
  } catch { }
  try {
    if (audioCtx) audioCtx.close();
  } catch { }
  try {
    if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());
  } catch { }
  try {
    if (ws) ws.close();
  } catch { }

  ws = null;
  audioCtx = null;
  workletNode = null;
  mediaStream = null;

  btnStart.disabled = false;
  btnStop.disabled = true;
}

async function start() {
  setTranscript("");
  setAssistantMarkdown("");
  renderTool(null);

  // 1) Start microphone + audio pipeline first.
  setStatus("Mic starting…", "warn");
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioCtx = new (window.AudioContext || window.webkitAudioContext)({
    // Browsers may ignore requested sampleRate; we will use the actual value.
    sampleRate: cfg.sample_rate,
  });

  await audioCtx.audioWorklet.addModule("/static/pcm16-worklet.js");
  workletNode = new AudioWorkletNode(audioCtx, "pcm16-worklet");
  // Tell the worklet the *actual* sample rate and desired frame duration.
  workletNode.port.postMessage({
    type: "config",
    sampleRate: audioCtx.sampleRate,
    frameMs: cfg.frame_ms,
  });

  const source = audioCtx.createMediaStreamSource(mediaStream);
  source.connect(workletNode);

  // 2) Connect websocket *after* we know the real sample rate.
  setStatus("Connecting…", "warn");
  const wsUrl = `${location.origin.replace("http", "ws")}${cfg.ws_path}?token=${encodeURIComponent(cfg.token)}&sr=${encodeURIComponent(audioCtx.sampleRate)}&frame_ms=${encodeURIComponent(cfg.frame_ms)}`;
  ws = new WebSocket(wsUrl);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    btnStart.disabled = true;
    btnStop.disabled = false;
    setStatus("Listening…", "ok");
  };

  workletNode.port.onmessage = (ev) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(ev.data);
  };

  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "ready") {
      setStatus("Listening…", "ok");
    } else if (msg.type === "event") {
      setStatus(msg.message || "…", "warn");
    } else if (msg.type === "stt") {
      setTranscript(msg.text);
    } else if (msg.type === "assistant") {
      setAssistantMarkdown(msg.text);
    } else if (msg.type === "tool") {
      renderTool(msg);
    } else if (msg.type === "done") {
      // Server finished one-shot request
      cleanup();
      setStatus("Stopped", "warn");
    } else if (msg.type === "error") {
      setStatus("Error", "err");
      setAssistantMarkdown(msg.message || "Error");
    }
  };

  ws.onclose = () => {
    cleanup();
    setStatus("Disconnected", "warn");
  };

  ws.onerror = () => {
    setStatus("WS error", "err");
  };
}

function stop() {
  cleanup();
  setStatus("Stopped", "warn");
}

btnStart.addEventListener("click", start);
btnStop.addEventListener("click", stop);

setStatus("Ready", "ok");
