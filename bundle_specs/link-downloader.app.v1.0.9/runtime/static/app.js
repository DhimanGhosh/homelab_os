const state = {
  jobs: [],
  files: [],
  defaultExternalSaveDir: "/mnt/nas/media/music",
  allowedSaveRoots: [],
  lastRefresh: null,
  fileDrafts: {},
  manualRefreshing: false,
};
const $ = (s) => document.querySelector(s);
const jobsEl = $("#jobs");
const filesEl = $("#files");
document.querySelectorAll(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    document
      .querySelectorAll(".tab")
      .forEach((b) => b.classList.toggle("active", b === btn));
    document
      .querySelectorAll(".panel")
      .forEach((p) => (p.hidden = p.id !== btn.dataset.panel));
  }),
);
function fmtBytes(bytes) {
  if (!bytes) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0,
    n = bytes;
  while (n >= 1024 && i < u.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
}
function escapeHtml(s) {
  return String(s || "").replace(
    /[&<>"']/g,
    (m) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
      m
      ],
  );
}
async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let txt = "";
  try {
    txt = await r.text();
  } catch { }
  let data = {};
  try {
    data = txt ? JSON.parse(txt) : {};
  } catch {
    data = { error: txt };
  }
  if (!r.ok) throw new Error(data.error || txt || "Request failed");
  return data;
}
function relToDownloadUrl(file, preferredName) {
  const base =
    file.download_url ||
    "/downloaded/" +
    file.relative_path.split("/").map(encodeURIComponent).join("/");
  if (preferredName) {
    return base + "?filename=" + encodeURIComponent(preferredName);
  }
  return base;
}
function relToOpenUrl(file) {
  return (
    file.browser_open_url ||
    "/open/" + file.relative_path.split("/").map(encodeURIComponent).join("/")
  );
}
function fmtTime(ts) {
  if (!ts) return "never";
  const d = new Date(ts * 1000 || ts);
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
function setRefreshStamp() {
  $("#lastRefresh").textContent = "Last refreshed: " + fmtTime(Date.now());
}
function getDraft(rel, file) {
  if (!state.fileDrafts[rel]) {
    state.fileDrafts[rel] = {
      newName: file.name,
      destination: state.defaultExternalSaveDir,
      operation: "copy",
    };
  }
  return state.fileDrafts[rel];
}
function syncDraftInputs(root) {
  root
    .querySelectorAll("[data-new-name],[data-dest],[data-op]")
    .forEach((el) => {
      const rel = el.dataset.newName || el.dataset.dest || el.dataset.op;
      const draft = state.fileDrafts[rel] || {};
      if (el.dataset.newName !== undefined) draft.newName = el.value;
      if (el.dataset.dest !== undefined) draft.destination = el.value;
      if (el.dataset.op !== undefined) draft.operation = el.value;
      state.fileDrafts[rel] = draft;
      updateDownloadLink(rel);
    });
}
function updateDownloadLink(rel) {
  const card = [...document.querySelectorAll(".file")].find(
    (el) => el.dataset.relativePath === rel,
  );
  if (!card) return;
  const file = state.files.find((f) => f.relative_path === rel);
  if (!file) return;
  const draft = getDraft(rel, file);
  const link = card.querySelector("[data-device-download]");
  if (link) {
    link.href = relToDownloadUrl(file, draft.newName);
    link.setAttribute("download", draft.newName || file.name);
  }
}
function renderJobs() {
  jobsEl.innerHTML = state.jobs.length
    ? ""
    : '<div class="hint">No jobs yet.</div>';
  state.jobs.forEach((job) => {
    const el = document.createElement("div");
    el.className = "job";
    const log = (job.log || []).slice(-6).join("\n");
    const resultBtn = job.output_relative
      ? `<button class="btn small ghost" data-focus-file="${escapeHtml(job.output_relative)}">Show saved file card</button>`
      : "";
    el.innerHTML = `<div class="section-title"><strong>${job.kind === "convert" ? "Conversion" : job.kind === "save-as" ? "Save elsewhere" : job.kind === "upload-convert" ? "Upload + convert" : "Download"} · ${escapeHtml(job.status)}</strong><span class="muted">${Math.round(job.progress || 0)}%</span></div><div class="progress"><div style="width:${job.progress || 0}%"></div></div><div class="hint" style="margin-top:8px">${escapeHtml(job.message || "")}</div>${resultBtn ? `<div class="action-row">${resultBtn}</div>` : ""}${job.output_path ? `<div class="hint mono" style="margin-top:8px">${escapeHtml(job.output_path)}</div>` : ""}${log ? `<div class="log">${escapeHtml(log)}</div>` : ""}`;
    jobsEl.appendChild(el);
  });
  document
    .querySelectorAll("[data-focus-file]")
    .forEach((btn) =>
      btn.addEventListener("click", () =>
        focusSavedFile(btn.dataset.focusFile),
      ),
    );
}
function renderFiles() {
  filesEl.innerHTML = "";
  if (!state.files.length) {
    filesEl.innerHTML = '<div class="hint">Nothing downloaded yet.</div>';
    return;
  }
  state.files.forEach((file) => {
    const rel = file.relative_path;
    const relEsc = escapeHtml(rel);
    const name = escapeHtml(file.name);
    const externalDefault = escapeHtml(
      state.defaultExternalSaveDir || "/mnt/nas/media/music",
    );
    const fileId = "file-" + btoa(rel).replace(/=/g, "");
    const draft = getDraft(rel, file);
    const el = document.createElement("div");
    el.className = "file";
    el.id = fileId;
    el.dataset.relativePath = rel;
    el.innerHTML = `<div class="section-title"><strong>${name}</strong><span class="pill">${escapeHtml(file.kind)}</span></div><div class="hint mono">${escapeHtml(file.full_path)}</div><div class="hint">${fmtBytes(file.size_bytes)}</div><div class="file-actions"><a class="btn small" href="${relToOpenUrl(file)}" target="_blank">Open in browser</a><a class="btn small primary" data-device-download href="${relToDownloadUrl(file, draft.newName)}" download="${escapeHtml(draft.newName)}">Download to this device</a>${file.kind !== "audio" ? `<button class="btn small ghost" data-convert="${relEsc}">Convert to MP3</button>` : ""}</div><div class="save-elsewhere"><div class="save-note">Rename this file, choose a destination, then copy or move it into another Raspberry Pi/NAS path like <span class="mono">${externalDefault}</span>.</div><div class="inline-grid"><input list="destinations" data-new-name="${relEsc}" value="${escapeHtml(draft.newName)}" placeholder="Rename file" /><input list="destinations" data-dest="${relEsc}" value="${escapeHtml(draft.destination)}" placeholder="Destination path e.g. /mnt/nas/media/music" /><select data-op="${relEsc}"><option value="copy" ${draft.operation === "copy" ? "selected" : ""}>Copy there</option><option value="move" ${draft.operation === "move" ? "selected" : ""}>Move there</option></select><button class="btn small ghost" data-save-as="${relEsc}">Save elsewhere</button></div></div>`;
    filesEl.appendChild(el);
  });
  document.querySelectorAll("[data-convert]").forEach((btn) =>
    btn.addEventListener("click", () => {
      $("#convertSelect").value = btn.dataset.convert;
      document.querySelector('[data-panel="convertPanel"]').click();
    }),
  );
  document.querySelectorAll("[data-save-as]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const rel = btn.dataset.saveAs;
      const draft = state.fileDrafts[rel] || {};
      const new_name = (draft.newName || "").trim();
      const destination_path = (draft.destination || "").trim();
      const operation = draft.operation || "copy";
      btn.disabled = true;
      const old = btn.textContent;
      btn.textContent = "Saving…";
      try {
        await api("/api/save-as", {
          method: "POST",
          body: JSON.stringify({
            relative_path: rel,
            new_name,
            destination_path,
            operation,
          }),
        });
        await refresh(true);
        alert(
          `${operation === "move" ? "Move" : "Copy"} queued for ${destination_path}`,
        );
      } catch (e) {
        alert(e.message || String(e));
      } finally {
        btn.disabled = false;
        btn.textContent = old;
      }
    }),
  );
  filesEl.querySelectorAll("input,select").forEach((el) => {
    el.addEventListener("input", () => syncDraftInputs(filesEl));
    el.addEventListener("change", () => syncDraftInputs(filesEl));
  });
  syncDraftInputs(filesEl);
}
function focusSavedFile(rel) {
  const target = [...document.querySelectorAll(".file")].find(
    (el) => el.dataset.relativePath === rel,
  );
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.classList.add("highlight");
  setTimeout(() => target.classList.remove("highlight"), 1800);
}
function updateSummary(data) {
  state.defaultExternalSaveDir =
    data.default_external_save_dir || "/mnt/nas/media/music";
  state.allowedSaveRoots = data.allowed_save_roots || [];
  $("#toolStatus").textContent = data.tools.message || "Ready";
  $("#serverRoot").textContent = data.server_save_root;
  $("#hostRoot").textContent =
    data.server_save_root_host || data.server_save_root;
  $("#externalRoot").textContent = state.defaultExternalSaveDir;
  $("#allowedRoots").textContent =
    "Allowed Pi/NAS roots: " +
    (state.allowedSaveRoots.join(", ") || "/mnt/nas, /data");
  $("#deviceHint").textContent = data.device_hint;
  $("#savedCount").textContent = data.saved_files.length;
  $("#audioCount").textContent = data.saved_files.filter(
    (f) => f.kind === "audio",
  ).length;
  $("#dlCount").textContent = data.jobs.filter(
    (j) => j.status === "completed",
  ).length;
  $("#actionLegend").textContent =
    "Open in browser • Download to this device • Copy/Move to Pi/NAS";
  const convertOptions = data.saved_files.filter((f) => f.kind !== "audio");
  $("#convertSelect").innerHTML =
    convertOptions
      .map(
        (f) =>
          `<option value="${escapeHtml(f.relative_path)}">${escapeHtml(f.name)}</option>`,
      )
      .join("") || '<option value="">No saved video files yet</option>';
  const dataList = $("#destinations");
  dataList.innerHTML = (data.common_destinations || [])
    .map((v) => `<option value="${escapeHtml(v)}"></option>`)
    .join("");
}
function editingInFiles() {
  const el = document.activeElement;
  return !!(el && filesEl.contains(el));
}
async function refresh(forceFiles = false) {
  const data = await api("/api/status");
  state.jobs = data.jobs;
  state.files = data.saved_files;
  updateSummary(data);
  renderJobs();
  if (forceFiles || !editingInFiles()) {
    renderFiles();
  }
  setRefreshStamp();
}
function setBusy(on, text) {
  const btn = $("#startBtn");
  btn.disabled = !!on;
  btn.textContent = text || "Start download";
}
$("#refreshBtn").addEventListener("click", () => refresh(true));
function bindClear(inputId, buttonId) {
  const input = $(inputId),
    btn = $(buttonId);
  if (!input || !btn) return;
  const sync = () => (btn.style.display = input.value ? "block" : "none");
  btn.addEventListener("click", () => {
    input.value = "";
    sync();
    input.focus();
  });
  input.addEventListener("input", sync);
  sync();
}
bindClear("#urlInput", "#clearUrlBtn");
bindClear("#convertNewName", "#clearConvertNameBtn");
fetch("/api/health")
  .then((r) => r.json())
  .then((data) => {
    if (!data) return;
    document.title = data.service || document.title;
    const name = data.service || "Downloader";
    const version = data.version ? "v" + data.version : "";
    const appName = $("#appName");
    const appVersion = $("#appVersion");
    const pageVersion = $("#pageVersion");
    if (appName) appName.textContent = name;
    if (appVersion)
      appVersion.textContent = `${version} • 8460 • social + file links + MP3 conversion`;
    if (pageVersion) pageVersion.textContent = version;
  })
  .catch(() => { });
$("#clearJobsBtn").addEventListener("click", async () => {
  try {
    await api("/api/clear-jobs", { method: "POST", body: "{}" });
    await refresh(true);
  } catch (e) {
    alert(e.message || String(e));
  }
});
$("#startBtn").addEventListener("click", async () => {
  const url = $("#urlInput").value.trim();
  if (!url) {
    alert("Paste a URL first");
    return;
  }
  setBusy(true, "Submitting…");
  try {
    await api("/api/download", {
      method: "POST",
      body: JSON.stringify({
        url,
        mode: $("#modeSelect").value,
        audio_format: "mp3",
      }),
    });
    $("#urlInput").value = "";
    await refresh(true);
  } catch (e) {
    alert(e.message || String(e));
  } finally {
    setBusy(false, "Start download");
  }
});
$("#convertBtn").addEventListener("click", async () => {
  const relative_path = $("#convertSelect").value;
  if (!relative_path) {
    alert("Select a saved video file first");
    return;
  }
  try {
    await api("/api/convert", {
      method: "POST",
      body: JSON.stringify({
        relative_path,
        new_name: $("#convertNewName").value.trim(),
      }),
    });
    $("#convertNewName").value = "";
    await refresh(true);
  } catch (e) {
    alert(e.message || String(e));
  }
});
$("#uploadConvertBtn").addEventListener("click", async () => {
  const file = $("#uploadFile").files[0];
  if (!file) {
    alert("Choose a file first");
    return;
  }
  const fd = new FormData();
  fd.append("file", file);
  fd.append("convert_to", $("#uploadConvertTo").value);
  fd.append("new_name", $("#uploadNewName").value.trim());
  const btn = $("#uploadConvertBtn");
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = "Uploading…";
  try {
    const r = await fetch("/api/upload-convert", { method: "POST", body: fd });
    const txt = await r.text();
    let data = {};
    try {
      data = txt ? JSON.parse(txt) : {};
    } catch {
      data = { error: txt };
    }
    if (!r.ok) throw new Error(data.error || txt || "Upload failed");
    $("#uploadFile").value = "";
    $("#uploadNewName").value = "";
    await refresh(true);
    document.querySelector('[data-panel="convertPanel"]').click();
  } catch (e) {
    alert(e.message || String(e));
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
});
refresh(true);
setInterval(() => refresh(false), 4000);
