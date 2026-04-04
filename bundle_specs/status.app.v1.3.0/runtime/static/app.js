function esc(v) {
  return String(v ?? "").replace(
    /[&<>"']/g,
    (m) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
      m
      ],
  );
}
function storageCard(label, s) {
  return `<div class="card"><div class="muted">${esc(label)}</div><div style="font-size:26px;font-weight:700">${esc(s.used_gb)} / ${esc(s.total_gb)} GB</div><div class="tiny muted">Free ${esc(s.free_gb)} GB • Used ${esc(s.used_pct)}%</div></div>`;
}
async function load() {
  const j = await fetch("/api/system").then((r) => r.json());
  document.title = j.app_name || document.title;
  document.getElementById("appName").textContent =
    j.app_name || "Pi Status Board";
  document.getElementById("appVersion").textContent =
    "v" + (j.app_version || "");
  document.getElementById("meta").textContent =
    `${j.hostname} • ${j.summary.ok}/${j.summary.total} healthy • ${j.generated_at}`;
  document.getElementById("summary").innerHTML = `
    <div class="card"><div class="muted">Uptime</div><div style="font-size:26px;font-weight:700">${esc(j.uptime || "-")}</div><div class="tiny muted">Tailscale IP: ${esc(j.tailscale_ip || "-")}</div></div>
    ${storageCard("NAS Storage", j.nas_storage)}
    ${storageCard("Root Storage", j.root_storage)}
  `;
  document.getElementById("services").innerHTML = (j.services || [])
    .map(
      (s) => `
    <div class="svc">
      <div class="row"><div class="name">${esc(s.name)}</div><div class="pill ${s.ok ? "ok" : "bad"}">${s.ok ? "Online" : "Offline"}</div></div>
      <div class="muted tiny">Version ${esc(s.version)} • Port ${esc(s.port)}</div>
      <div style="margin-top:10px"><a target="_blank" href="${esc(s.url)}">${esc(s.url)}</a></div>
      <div class="tiny muted" style="margin-top:8px">${s.ok ? "HTTP " + esc(s.status) : esc(s.error || "Unavailable")}</div>
    </div>
  `,
    )
    .join("");
  const peers = j.tailscale_devices || [];
  document.getElementById("tailscale").innerHTML = peers.length
    ? peers
      .map(
        (p) =>
          `<div class="svc"><div class="row"><strong>${esc(p.name)}</strong><span class="${p.online ? "good" : "warn"}">${p.online ? "Online" : "Offline"}</span></div><div class="tiny muted">${esc(p.os || "-")} • ${esc(p.ip || "-")}</div></div>`,
      )
      .join("")
    : '<div class="muted">No peers found.</div>';
}
load();
setInterval(load, 15000);
