import json, os, re, shutil, subprocess, tempfile, zipfile, tarfile, time, threading, uuid
from pathlib import Path
import signal
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from packaging.version import Version, InvalidVersion

BASE = Path(os.getenv("CONTROL_CENTER_BASE", "/mnt/nas/homelab/control-center"))
APP_DIR = BASE / "app"
DATA_DIR = BASE / "data"
LOG_DIR = BASE / "logs"
INSTALLERS_DIR = Path(os.getenv("INSTALLERS_DIR", "/mnt/nas/homelab/installers"))
APPS_DIR = Path(os.getenv("APPS_DIR", "/mnt/nas/homelab/apps"))
NAS_DIR = Path(os.getenv("NAS_MOUNT", "/mnt/nas"))
BACKUPS_DIR = Path(os.getenv("HOMELAB_BACKUPS_DIR", str(NAS_DIR / "homelab" / "backups")))
FQDN = os.getenv("TAILSCALE_FQDN", "pi-nas.taild4713b.ts.net")
for p in [DATA_DIR, LOG_DIR, INSTALLERS_DIR, APPS_DIR, BACKUPS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

KNOWN_APPS = {
    "pihole": {"name": "Pi-hole", "port": 8447, "open_path": "/admin/"},
    "navidrome": {"name": "Navidrome", "port": 8445, "open_path": "/"},
    "jellyfin": {"name": "Jellyfin", "port": 8446, "open_path": "/"},
    "nextcloud": {"name": "Nextcloud", "port": 8448, "open_path": "/"},
    "files": {"name": "Files", "port": 8449, "open_path": "/"},
    "home-assistant": {"name": "Home Assistant", "port": 8450, "open_path": "/"},
    "status": {"name": "Pi Status Board", "port": 8451, "open_path": "/"},
    "voice-ai": {"name": "Voice AI", "port": 8452, "open_path": "/"},
    "homarr": {"name": "Homarr", "port": 8453, "open_path": "/"},
    "personal-library": {"name": "Personal Library", "port": 8454, "open_path": "/"},
    "dictionary": {"name": "Dictionary", "port": 8455, "open_path": "/"},
    "api-gateway": {"name": "API Gateway", "port": 8456, "open_path": "/docs"},
    "control-center": {"name": "Control Center", "port": 8444, "open_path": "/"},
}
BUNDLE_RE = re.compile(r"^(?P<id>[a-zA-Z0-9._-]+)\.app\.v(?P<ver>\d+\.\d+\.\d+)\.(?:zip|tgz|tar\.gz)$")
CC_RE = re.compile(r"^control_center_bundle_v(?P<ver>\d+[._]\d+[._]\d+)(?:[_-]?[A-Za-z0-9.-]+)?\.(?:zip|tgz|tar\.gz)$")
JOB_STATE_PATH = DATA_DIR / "jobs.json"
INSTALLED_OVERRIDES_PATH = DATA_DIR / "installed_versions.json"
VERSION_FILE = BASE / "VERSION"
UPDATE_ALL_PLAN_PATH = DATA_DIR / "update_all_plan.json"

APP_ID_ALIASES = {
    "home_assistant": "home-assistant",
    "home-assistant": "home-assistant",
    "voice_ai": "voice-ai",
    "voice-ai": "voice-ai",
    "api_gateway": "api-gateway",
    "control_center": "control-center",
}

def normalize_app_id(app_id: str | None) -> str:
    if not app_id:
        return ""
    app_id = str(app_id).strip()
    return APP_ID_ALIASES.get(app_id, app_id.replace("_", "-") if app_id.replace("_", "-") in KNOWN_APPS else app_id)

def docker_root_dir() -> str:
    try:
        out = subprocess.check_output(["docker", "info", "--format", "{{.DockerRootDir}}"], text=True, timeout=5).strip()
        return out or "/var/lib/docker"
    except Exception:
        return "/var/lib/docker"

def sdcard_warning() -> str | None:
    root = docker_root_dir()
    return None if root.startswith(str(NAS_DIR)) else f"Docker data root is currently on {root}. Recommended: {NAS_DIR / 'homelab' / 'docker'}"

def get_cc_version():
    try:
        return VERSION_FILE.read_text().strip() or "1.6.4"
    except Exception:
        return "1.6.4"

app = FastAPI(title="Pi Control Center", version=get_cc_version())

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

JOBS_LOCK = threading.Lock()
JOBS = {}

def _disk(path: Path):
    try:
        u = shutil.disk_usage(path)
        return {
            "path": str(path),
            "total_gb": round(u.total / 1024**3, 2),
            "used_gb": round((u.total - u.free) / 1024**3, 2),
            "free_gb": round(u.free / 1024**3, 2),
            "used_pct": round(((u.total - u.free) / u.total) * 100, 2) if u.total else 0,
        }
    except Exception:
        return {"path": str(path), "total_gb": 0, "used_gb": 0, "free_gb": 0, "used_pct": 0}

def _json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

def notifications():
    items = _json(DATA_DIR / "notifications.json", [])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("app_id"):
                item["app_id"] = normalize_app_id(item.get("app_id"))
        return items
    return []

def save_notifications(items):
    _write_json(DATA_DIR / "notifications.json", items[:500])

def add_notification(message: str, app_id: str | None = None):
    items = notifications()
    items.insert(0, {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "message": message, "app_id": normalize_app_id(app_id) if app_id else None})
    save_notifications(items)

def notification_counts():
    counts = {}
    for item in notifications():
        app_id = normalize_app_id(item.get("app_id"))
        if app_id:
            counts[app_id] = counts.get(app_id, 0) + 1
    return counts

def installed_overrides():
    data = _json(INSTALLED_OVERRIDES_PATH, {})
    return data if isinstance(data, dict) else {}

def set_installed_override(app_id: str, version: str, bundle_filename: str | None = None):
    app_id = normalize_app_id(app_id)
    data = installed_overrides()
    payload = {"installed_version": str(version), "version": str(version), "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if bundle_filename:
        payload["bundle_filename"] = bundle_filename
    data[app_id] = payload
    _write_json(INSTALLED_OVERRIDES_PATH, data)

def clear_installed_override(app_id: str):
    app_id = normalize_app_id(app_id)
    data = installed_overrides()
    if app_id in data:
        del data[app_id]
        _write_json(INSTALLED_OVERRIDES_PATH, data)

def scan_backups():
    items = []
    for p in sorted(BACKUPS_DIR.glob("homelab_snapshot_*.tar.gz"), reverse=True):
        manifest = p.with_suffix("").with_suffix(".json")
        meta = _json(manifest, {}) if manifest.exists() else {}
        items.append({
            "filename": p.name,
            "size_mb": round(p.stat().st_size / 1024**2, 2),
            "created_at": meta.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime)),
            "label": meta.get("label") or p.stem.replace("homelab_snapshot_", "").replace("_", " "),
            "path": str(p),
            "includes": meta.get("includes") or ["/mnt/nas/homelab", "/etc/caddy/Caddyfile", "/etc/caddy/apps", "/etc/systemd/system/pi-control-center.service"],
        })
    return items

def parse_version(v: str):
    try:
        return Version(str(v))
    except InvalidVersion:
        return Version("0.0.0")

def scan_bundles():
    bundles = []
    bundles_by_id = {}
    latest_by_id = {}
    ota = []
    for p in sorted(INSTALLERS_DIR.iterdir() if INSTALLERS_DIR.exists() else []):
        if not p.is_file():
            continue
        m = BUNDLE_RE.match(p.name)
        if m:
            item = {"filename": p.name, "app_id": normalize_app_id(m.group("id")), "version": m.group("ver")}
            bundles.append(item)
            bundles_by_id.setdefault(item["app_id"], []).append(item)
            prev = latest_by_id.get(item["app_id"])
            if not prev or parse_version(item["version"]) > parse_version(prev["version"]):
                latest_by_id[item["app_id"]] = item
            continue
        m = CC_RE.match(p.name)
        if m:
            item = {"filename": p.name, "app_id": "control-center", "version": m.group("ver").replace("_", ".")}
            ota.append(item)
            bundles.append(item)
            bundles_by_id.setdefault("control-center", []).append(item)
            prev = latest_by_id.get("control-center")
            if not prev or parse_version(item["version"]) > parse_version(prev["version"]):
                latest_by_id["control-center"] = item
    for _, v in bundles_by_id.items():
        v.sort(key=lambda x: parse_version(x["version"]), reverse=True)
    latest_ota = latest_by_id.get("control-center")
    return bundles, bundles_by_id, latest_by_id, latest_ota

def load_installed_app(app_id: str):
    app_id = normalize_app_id(app_id)
    d = APPS_DIR / app_id
    for name in ["install_state.json", "app_info.json", "metadata.json"]:
        obj = _json(d / name, None)
        if isinstance(obj, dict):
            obj["id"] = normalize_app_id(obj.get("id") or app_id)
            return obj
    return None

def current_jobs():
    with JOBS_LOCK:
        return [dict(v) for v in JOBS.values()]

def persist_jobs():
    with JOBS_LOCK:
        _write_json(JOB_STATE_PATH, [dict(v) for v in JOBS.values()])

def load_jobs():
    arr = _json(JOB_STATE_PATH, [])
    if not isinstance(arr, list):
        return
    with JOBS_LOCK:
        for item in arr:
            if item.get("status") in ("queued", "running"):
                item["status"] = "failed"
                item["message"] = "Recovered after service restart"
                item["progress"] = 100
            JOBS[item["id"]] = item

def get_running_job_for_app(app_id: str):
    app_id = normalize_app_id(app_id)
    with JOBS_LOCK:
        for job in JOBS.values():
            if job["app_id"] == app_id and job["status"] in ("queued", "running"):
                return dict(job)
    return None

def tail_log(log_path, lines=40):
    p = Path(log_path)
    if not p.exists():
        return "No log available."
    try:
        txt = p.read_text(errors="ignore").splitlines()
        return "\n".join(txt[-lines:]) if txt else "(empty log)"
    except Exception as e:
        return f"Failed to read log: {e}"

def scan_apps():
    installed = {}
    if APPS_DIR.exists():
        for d in sorted(APPS_DIR.iterdir()):
            if d.is_dir():
                info = load_installed_app(d.name)
                if info:
                    installed[normalize_app_id(d.name)] = info
    _, bundles_by_id, latest_by_id, _ = scan_bundles()
    overrides = installed_overrides()
    ids = set(KNOWN_APPS) | set(installed) | set(latest_by_id) | set(overrides)
    running_by_app = {}
    for j in current_jobs():
        if j["status"] in ("queued", "running"):
            running_by_app[j["app_id"]] = j
    note_counts = notification_counts()
    cards = []
    for app_id in ids:
        m = {"id": app_id}
        m.update(KNOWN_APPS.get(app_id, {}))
        m.update(installed.get(app_id, {}))
        latest = latest_by_id.get(app_id)
        override = overrides.get(app_id) if isinstance(overrides, dict) else None
        if isinstance(override, dict):
            if override.get("installed_version"):
                m["installed_version"] = override.get("installed_version")
            if override.get("version"):
                m["version"] = override.get("version")
            if override.get("bundle_filename"):
                m["current_bundle_filename"] = override.get("bundle_filename")
        installed_ver = m.get("installed_version") or m.get("version")
        m["installed_version"] = installed_ver
        m["latest_version"] = latest["version"] if latest else installed_ver
        m["bundle_filename"] = latest["filename"] if latest else None
        m["bundles"] = bundles_by_id.get(app_id, [])
        m["installed"] = app_id in installed or app_id in overrides or app_id == "control-center"
        port = m.get("port")
        path = m.get("open_path", "/")
        if path and not path.startswith("/"):
            path = "/" + path
        m["open_url"] = f"https://{FQDN}:{port}{path}" if port and m["installed"] else None
        running = running_by_app.get(app_id)
        m["job"] = running
        m["notification_count"] = note_counts.get(app_id, 0)
        m["has_notifications"] = m["notification_count"] > 0
        if app_id == "control-center":
            m["installed"] = True
            cc_version = get_cc_version()
            m["installed_version"] = cc_version
            m["latest_version"] = latest["version"] if latest else cc_version
            m["bundle_filename"] = latest["filename"] if latest else None
            m["action"] = "update" if latest and parse_version(latest["version"]) > parse_version(app.version) else "installed"
        elif running:
            m["action"] = "running"
        elif not m["installed"] and latest:
            m["action"] = "install"
        elif m["installed"] and latest and parse_version(m["latest_version"]) > parse_version(installed_ver or "0.0.0"):
            m["action"] = "update"
        elif m["installed"]:
            m["action"] = "reinstall"
        else:
            m["action"] = "none"
        cards.append(m)
    cards.sort(key=lambda x: (x["id"] != "control-center", x.get("name", x["id"]).lower()))
    return cards

def extract_bundle(bundle_path: Path) -> Path:
    temp = Path(tempfile.mkdtemp(prefix="ccbundle-"))
    name = bundle_path.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(bundle_path, "r") as zf:
            zf.extractall(temp)
    elif name.endswith(".tgz") or name.endswith(".tar.gz"):
        with tarfile.open(bundle_path, "r:gz") as tf:
            tf.extractall(temp)
    else:
        raise RuntimeError(f"Unsupported bundle type: {bundle_path.name}")
    children = [p for p in temp.iterdir() if not p.name.startswith("__MACOSX")]
    return children[0] if len(children) == 1 and children[0].is_dir() else temp

def estimate_progress(line: str, current: int):
    s = line.strip().lower()
    if not s:
        return current
    mapping = [
        ("queued", 5), ("preparing bundle", 10), ("bundle extracted", 15),
        ("pulling", 25), ("downloading", 30), ("extracting", 35), ("verifying checksum", 38),
        ("building", 45), ("creating", 55), ("snapshot", 35), ("restoring", 55), ("rollback", 75), ("starting", 65), ("started", 72),
        ("health", 82), ("local service health check failed", 100),
        ("caddy", 90), ("installed", 100), ("uninstalled", 100), ("done", 100), ("complete", 100),
    ]
    for key, val in mapping:
        if key in s:
            return max(current, val)
    return current

def update_job(job_id: str, **changes):
    with JOBS_LOCK:
        if job_id not in JOBS:
            return
        JOBS[job_id].update(changes)
        JOBS[job_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    persist_jobs()

def _run_and_stream(job_id: str, cmd, cwd: Path, env: dict, log_path: Path):
    progress = 15
    with log_path.open("a", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid,
        )
        update_job(job_id, pid=proc.pid)
        try:
            for raw in proc.stdout:
                fh.write(raw)
                fh.flush()
                progress = estimate_progress(raw, progress)
                update_job(job_id, progress=progress, message=raw.strip()[:240] or "Running…")
                with JOBS_LOCK:
                    job = JOBS.get(job_id)
                    cancel_requested = bool(job and job.get("cancel_requested"))
                if cancel_requested and proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except Exception:
                        pass
            return proc.wait()
        finally:
            update_job(job_id, pid=None)

def _write_installed_state_from_bundle(app_id: str, item: dict):
    app_id = normalize_app_id(app_id)
    app_dir = APPS_DIR / app_id
    app_dir.mkdir(parents=True, exist_ok=True)
    existing = load_installed_app(app_id) or {}
    base = dict(KNOWN_APPS.get(app_id, {}))
    state = {
        "id": app_id,
        "name": existing.get("name") or base.get("name") or app_id,
        "installed_version": item["version"],
        "version": item["version"],
        "bundle_filename": item["filename"],
        "port": existing.get("port") or base.get("port"),
        "open_path": existing.get("open_path") or base.get("open_path", "/"),
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    for key in ("health_url", "local_upstream"):
        if existing.get(key):
            state[key] = existing[key]
    _write_json(app_dir / "install_state.json", state)

def remove_installed_state(app_id: str):
    app_id = normalize_app_id(app_id)
    app_dir = APPS_DIR / app_id
    for name in ("install_state.json", "app_info.json", "metadata.json"):
        try:
            (app_dir / name).unlink(missing_ok=True)
        except Exception:
            pass

def read_bundle_metadata(bundle_path: Path) -> dict:
    try:
        name = bundle_path.name.lower()
        if name.endswith(".zip"):
            with zipfile.ZipFile(bundle_path, "r") as zf:
                for member in zf.namelist():
                    if member.endswith("metadata.json") and not member.startswith("__MACOSX/"):
                        return json.loads(zf.read(member).decode("utf-8"))
        elif name.endswith(".tgz") or name.endswith(".tar.gz"):
            with tarfile.open(bundle_path, "r:gz") as tf:
                for member in tf.getmembers():
                    if member.name.endswith("metadata.json") and not member.name.startswith("__MACOSX/"):
                        fh = tf.extractfile(member)
                        if fh:
                            return json.loads(fh.read().decode("utf-8"))
    except Exception:
        return {}
    return {}

def validate_bundle_dependencies(app_id: str, item: dict | None):
    app_id = normalize_app_id(app_id)
    if not item:
        return
    meta = read_bundle_metadata(INSTALLERS_DIR / item["filename"])
    requires_api = bool(meta.get("requires_api_gateway_bundle") or meta.get("requires_api_change") or meta.get("requires_api_endpoint_update"))
    if not requires_api:
        return
    _, _, latest_by_id, _ = scan_bundles()
    if not latest_by_id.get("api-gateway"):
        raise RuntimeError(f"{app_id} requires an API Gateway endpoint update bundle, but no api-gateway bundle is uploaded.")

def _latest_bundle_for_app(app_id: str):
    app_id = normalize_app_id(app_id)
    _, _, latest_by_id, _ = scan_bundles()
    return latest_by_id.get(app_id)

def _bundle_requires_api_gateway(item: dict | None) -> bool:
    if not item:
        return False
    meta = read_bundle_metadata(INSTALLERS_DIR / item["filename"])
    return bool(meta.get("requires_api_gateway_bundle") or meta.get("requires_api_change") or meta.get("requires_api_endpoint_update"))

def maybe_queue_api_gateway_dependency(app_id: str, item: dict | None):
    app_id = normalize_app_id(app_id)
    if app_id == "api-gateway" or not _bundle_requires_api_gateway(item):
        return
    gateway_bundle = _latest_bundle_for_app("api-gateway")
    if not gateway_bundle:
        raise RuntimeError(f"{app_id} requires an API Gateway endpoint update bundle, but no api-gateway bundle is uploaded.")
    create_job("api-gateway", "install", bundle_filename=gateway_bundle["filename"])

def collect_update_candidates():
    apps = scan_apps()
    return [a for a in apps if a.get("id") != "control-center" and a.get("action") == "update"]

def collect_install_candidates():
    apps = scan_apps()
    return [a for a in apps if a.get("id") != "control-center" and a.get("bundles") and a.get("action") in ("install", "update", "reinstall")]

def process_pending_update_all_plan():
    plan = _json(UPDATE_ALL_PLAN_PATH, None)
    if not isinstance(plan, dict):
        return
    if any(j.get("status") in ("queued", "running") for j in current_jobs()):
        return
    min_cc_version = plan.get("min_cc_version")
    if min_cc_version and parse_version(get_cc_version()) < parse_version(min_cc_version):
        return
    queued = []
    for app_id in plan.get("apps", []):
        job, created = create_job(app_id, "install")
        queued.append({"app_id": app_id, "created": created, "job_id": job.get("id")})
    UPDATE_ALL_PLAN_PATH.unlink(missing_ok=True)
    if queued:
        add_notification(f"Update all resumed and queued {len(queued)} app update(s)", "control-center")


def get_running_maintenance_job():
    with JOBS_LOCK:
        for job in JOBS.values():
            if job["app_id"] == "homelab-maintenance" and job["status"] in ("queued", "running"):
                return dict(job)
    return None


def run_maintenance_job_thread(job_id: str, mode: str, snapshot_name: str | None = None):
    archive = None
    try:
        update_job(job_id, status="running", progress=5, message=("Preparing snapshot" if mode == "backup" else "Preparing rollback"))
        if mode == "backup":
            ts = time.strftime("%Y%m%d_%H%M%S")
            archive = BACKUPS_DIR / f"homelab_snapshot_{ts}.tar.gz"
            script = "\n".join([
                "set -Eeuo pipefail",
                f'mkdir -p "{BACKUPS_DIR}"',
                'echo "[INFO] Creating homelab snapshot"',
                f'sudo tar -czf "{archive}" --exclude="mnt/nas/homelab/backups" -C / mnt/nas/homelab etc/caddy/Caddyfile etc/caddy/apps etc/systemd/system/pi-control-center.service',
                f'echo "[INFO] Snapshot archive created: {archive.name}"',
            ])
        else:
            if not snapshot_name:
                raise RuntimeError("Snapshot name missing")
            archive = BACKUPS_DIR / Path(snapshot_name).name
            if not archive.exists():
                raise RuntimeError(f"Snapshot not found: {archive.name}")
            script = "\n".join([
                "set -Eeuo pipefail",
                'WORKDIR="$(mktemp -d)"',
                'trap \'rm -rf "$WORKDIR"\' EXIT',
                f'echo "[INFO] Extracting snapshot {archive.name}"',
                f'sudo tar -xzf "{archive}" -C "$WORKDIR"',
                'echo "[INFO] Restoring /mnt/nas/homelab"',
                'sudo mkdir -p /mnt/nas/homelab',
                'sudo rsync -a --delete --exclude "backups/" "$WORKDIR/mnt/nas/homelab/" /mnt/nas/homelab/',
                'if [ -f "$WORKDIR/etc/caddy/Caddyfile" ]; then echo "[INFO] Restoring /etc/caddy/Caddyfile"; sudo cp "$WORKDIR/etc/caddy/Caddyfile" /etc/caddy/Caddyfile; fi',
                'if [ -d "$WORKDIR/etc/caddy/apps" ]; then echo "[INFO] Restoring /etc/caddy/apps"; sudo mkdir -p /etc/caddy/apps; sudo rsync -a --delete "$WORKDIR/etc/caddy/apps/" /etc/caddy/apps/; fi',
                'if [ -f "$WORKDIR/etc/systemd/system/pi-control-center.service" ]; then echo "[INFO] Restoring pi-control-center.service"; sudo cp "$WORKDIR/etc/systemd/system/pi-control-center.service" /etc/systemd/system/pi-control-center.service; fi',
                'echo "[INFO] Reloading services"',
                'sudo systemctl daemon-reload || true',
                'sudo systemctl reload caddy || sudo systemctl restart caddy || true',
                'sudo bash -lc \'nohup bash -lc "sleep 3; systemctl restart pi-control-center" >/dev/null 2>&1 &\' || true',
                'echo "[INFO] Rollback restore completed"',
            ])
        log_path = LOG_DIR / f"homelab-{mode}-{int(time.time())}-{job_id[:8]}.log"
        update_job(job_id, log_name=log_path.name, message="Starting task", progress=10)
        code = _run_and_stream(job_id, ["bash", "-lc", script], BACKUPS_DIR, os.environ.copy(), log_path)
        with JOBS_LOCK:
            cancel_requested = bool(JOBS.get(job_id, {}).get("cancel_requested"))
        if cancel_requested:
            update_job(job_id, status="canceled", progress=100, message=f"{mode.capitalize()} canceled")
            add_notification(f"{mode.capitalize()} canceled for homelab maintenance")
            return
        if code != 0:
            update_job(job_id, status="failed", progress=100, message=f"{mode.capitalize()} failed")
            add_notification(f"{mode.capitalize()} failed for homelab maintenance. Log: {log_path.name}")
            return
        if mode == "backup" and archive is not None:
            _write_json(archive.with_suffix("").with_suffix(".json"), {
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "label": archive.stem.replace("homelab_snapshot_", "").replace("_", " "),
                "includes": ["/mnt/nas/homelab", "/etc/caddy/Caddyfile", "/etc/caddy/apps", "/etc/systemd/system/pi-control-center.service"],
            })
        update_job(job_id, status="success", progress=100, message=("Backup completed" if mode == "backup" else "Rollback completed"))
        add_notification("Homelab backup completed" if mode == "backup" else f"Homelab rollback completed from {archive.name}")
    except Exception as e:
        update_job(job_id, status="failed", progress=100, message=str(e))
        add_notification(f"{mode.capitalize()} failed for homelab maintenance: {e}")
    finally:
        persist_jobs()


def create_maintenance_job(mode: str, snapshot_name: str | None = None):
    existing = get_running_maintenance_job()
    if existing:
        return existing, False
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "app_id": "homelab-maintenance",
        "app_name": "Homelab Backup & Rollback",
        "action": mode,
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "log_name": None,
        "bundle_filename": snapshot_name,
        "pid": None,
        "cancel_requested": False,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    persist_jobs()
    threading.Thread(target=run_maintenance_job_thread, args=(job_id, mode, snapshot_name), daemon=True).start()
    return job, True


def run_job_thread(job_id: str, app_id: str, action: str):
    app_id = normalize_app_id(app_id)
    root = None
    root_parent = None
    item = None
    try:
        update_job(job_id, status="running", progress=5, message="Preparing job")
        if action == "install":
            requested_filename = None
            with JOBS_LOCK:
                requested_filename = (JOBS.get(job_id) or {}).get("bundle_filename")
            if requested_filename:
                bundles, _, _, _ = scan_bundles()
                item = next((b for b in bundles if b["app_id"] == app_id and b["filename"] == requested_filename), None)
            else:
                _, _, latest_by_id, _ = scan_bundles()
                item = latest_by_id.get(app_id)
            if not item:
                raise RuntimeError(f"No bundle uploaded for {app_id}")
            validate_bundle_dependencies(app_id, item)
            maybe_queue_api_gateway_dependency(app_id, item)
            bundle = INSTALLERS_DIR / item["filename"]
            update_job(job_id, bundle_filename=item["filename"], message=f"Preparing bundle {item['filename']}", progress=8)
            root = extract_bundle(bundle)
            root_parent = root.parent if root.parent.name.startswith("ccbundle-") else root
            update_job(job_id, message="Bundle extracted", progress=15)
            script = root / "install.sh"
            if not script.exists():
                script = root / "scripts" / "install.sh"
            if not script.exists():
                raise RuntimeError("Install script not found in bundle")
        else:
            root = APPS_DIR / app_id
            script = root / "uninstall.sh"
            if not script.exists():
                script = root / "scripts" / "uninstall.sh"
            if not script.exists():
                raise RuntimeError("Uninstall script not found for installed app")
        env = os.environ.copy()
        env["APP_ROOT"] = str(root)
        env.setdefault("TAILSCALE_FQDN", FQDN)
        env.setdefault("CC_HTTPS_MODE", "tailscale-https")
        log_path = LOG_DIR / f"{app_id}-{action}-{int(time.time())}-{job_id[:8]}.log"
        update_job(job_id, log_name=log_path.name, message="Starting installer", progress=18)
        code = _run_and_stream(job_id, ["bash", str(script)], root, env, log_path)
        with JOBS_LOCK:
            cancel_requested = bool(JOBS.get(job_id, {}).get("cancel_requested"))
        if cancel_requested:
            update_job(job_id, status="canceled", progress=100, message=f"{action.capitalize()} canceled")
            add_notification(f"{action.capitalize()} canceled for {app_id}")
            return
        if code != 0:
            update_job(job_id, status="failed", progress=100, message=f"{action.capitalize()} failed")
            add_notification(f"{action.capitalize()} failed for {app_id}. Log: {log_path.name}")
            return
        if action == "install" and item:
            if app_id != "control-center":
                _write_installed_state_from_bundle(app_id, item)
            set_installed_override(app_id, item["version"], item.get("filename"))
        elif action == "uninstall":
            clear_installed_override(app_id)
            remove_installed_state(app_id)
            update_job(job_id, app_name=KNOWN_APPS.get(app_id, {}).get("name", app_id), bundle_filename=None)
        update_job(job_id, status="success", progress=100, message=f"{action.capitalize()} completed")
        add_notification(f"{action.capitalize()} completed for {app_id}")
    except Exception as e:
        update_job(job_id, status="failed", progress=100, message=str(e))
        add_notification(f"{action.capitalize()} failed for {app_id}: {e}")
    finally:
        if action == "install" and root_parent:
            shutil.rmtree(root_parent, ignore_errors=True)
        persist_jobs()

def create_job(app_id: str, action: str, bundle_filename: str | None = None):
    app_id = normalize_app_id(app_id)
    existing = get_running_job_for_app(app_id)
    if existing:
        return existing, False
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "app_id": app_id,
        "app_name": KNOWN_APPS.get(app_id, {}).get("name", app_id),
        "action": action,
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "log_name": None,
        "bundle_filename": bundle_filename,
        "pid": None,
        "cancel_requested": False,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    persist_jobs()
    threading.Thread(target=run_job_thread, args=(job_id, app_id, action), daemon=True).start()
    return job, True

@app.on_event("startup")
def on_startup():
    load_jobs()
    process_pending_update_all_plan()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    bundles, _, _, latest_ota = scan_bundles()
    current_cc_version = get_cc_version()
    if latest_ota and parse_version(latest_ota["version"]) <= parse_version(current_cc_version):
        latest_ota = None
    return templates.TemplateResponse("index.html", {
        "request": request,
        "nas_usage": _disk(NAS_DIR),
        "homelab_usage": _disk(NAS_DIR / "homelab"),
        "root_usage": _disk(Path("/")),
        "docker_root": docker_root_dir(),
        "sdcard_warning": sdcard_warning(),
        "apps": scan_apps(),
        "notifications": notifications(),
        "ota": latest_ota,
        "current_version": app.version,
        "total_bundles": len(bundles),
        "jobs": current_jobs(),
        "backups": scan_backups(),
        "backup_root": str(BACKUPS_DIR),
        "notification_total": len(notifications()),
        "docker_root": docker_root_dir(),
        "sdcard_warning": sdcard_warning(),
    })

@app.get("/api/state")
async def state():
    bundles, _, _, latest_ota = scan_bundles()
    current_cc_version = get_cc_version()
    if latest_ota and parse_version(latest_ota["version"]) <= parse_version(current_cc_version):
        latest_ota = None
    jobs = current_jobs()
    for j in jobs:
        j["log_tail"] = tail_log(LOG_DIR / j["log_name"], 12) if j.get("log_name") else ""
    jobs.sort(key=lambda j: (j["status"] not in ("queued", "running"), j["created_at"]))
    return {
        "apps": scan_apps(),
        "notifications": notifications()[:40],
        "notification_total": len(notifications()),
        "jobs": jobs,
        "ota": latest_ota,
        "current_version": app.version,
        "total_bundles": len(bundles),
        "backups": scan_backups(),
        "backup_root": str(BACKUPS_DIR),
        "docker_root": docker_root_dir(),
        "sdcard_warning": sdcard_warning(),
    }

@app.post("/api/marketplace/rescan")
async def rescan():
    add_notification("Marketplace rescanned")
    return {"ok": True, "message": "Marketplace rescanned."}

@app.post("/api/notifications/clear")
async def clear_notifications():
    save_notifications([])
    return {"ok": True, "message": "Notifications cleared."}

@app.post("/api/bundles/upload")
async def upload_bundle(files: list[UploadFile] = File(...)):
    saved = []
    for file in files:
        name = Path(file.filename or "").name
        if not name:
            continue
        target = INSTALLERS_DIR / name
        with target.open("wb") as f:
            f.write(await file.read())
        saved.append(name)
        add_notification(f"Uploaded bundle: {name}")
    if not saved:
        return JSONResponse(status_code=400, content={"ok": False, "message": "No files uploaded."})
    return {"ok": True, "message": f"Uploaded {len(saved)} bundle(s)."}

@app.delete("/api/bundles/{filename}")
async def delete_bundle(filename: str):
    p = INSTALLERS_DIR / filename
    if p.exists():
        p.unlink()
        add_notification(f"Deleted bundle: {filename}")
    return {"ok": True, "message": f"Deleted {filename}"}

@app.get("/api/backups")
async def list_backups():
    return {"ok": True, "items": scan_backups()}

@app.post("/api/backups/create")
async def create_backup():
    _, created = create_maintenance_job("backup")
    return {"ok": True, "message": "Backup queued." if created else "Backup or rollback already running.", "created": created}

@app.post("/api/backups/{filename}/restore")
async def restore_backup(filename: str):
    snapshot = BACKUPS_DIR / Path(filename).name
    if not snapshot.exists():
        raise HTTPException(404, "Snapshot not found")
    _, created = create_maintenance_job("rollback", snapshot.name)
    return {"ok": True, "message": f"Rollback queued for {snapshot.name}." if created else "Backup or rollback already running.", "created": created}

@app.delete("/api/backups/{filename}")
async def delete_backup(filename: str):
    snapshot = BACKUPS_DIR / Path(filename).name
    if not snapshot.exists():
        raise HTTPException(404, "Snapshot not found")
    meta = snapshot.with_suffix("").with_suffix(".json")
    snapshot.unlink(missing_ok=True)
    meta.unlink(missing_ok=True)
    add_notification(f"Deleted homelab snapshot: {snapshot.name}")
    return {"ok": True, "message": f"Deleted {snapshot.name}"}

@app.get("/api/logs/{log_name}", response_class=PlainTextResponse)
async def get_log(log_name: str):
    path = LOG_DIR / Path(log_name).name
    if not path.exists():
        raise HTTPException(404, "Log not found")
    return path.read_text(errors="ignore")

@app.post("/api/apps/{app_id}/install")
async def install_app(app_id: str):
    app_id = normalize_app_id(app_id)
    _, created = create_job(app_id, "install")
    return {"ok": True, "message": "Install queued." if created else "Install already running.", "created": created}

@app.post("/api/apps/{app_id}/install-bundle/{filename}")
async def install_app_bundle(app_id: str, filename: str):
    app_id = normalize_app_id(app_id)
    candidate = INSTALLERS_DIR / Path(filename).name
    if not candidate.exists():
        raise HTTPException(404, "Bundle not found")
    bundles, _, _, _ = scan_bundles()
    item = next((b for b in bundles if b["app_id"] == app_id and b["filename"] == Path(filename).name), None)
    if not item:
        raise HTTPException(400, "Bundle does not match app")
    _, created = create_job(app_id, "install", bundle_filename=item["filename"])
    return {"ok": True, "message": f"Install queued for {item['filename']}." if created else "Install already running.", "created": created}

@app.post("/api/apps/{app_id}/uninstall")
async def uninstall_app(app_id: str):
    app_id = normalize_app_id(app_id)
    _, created = create_job(app_id, "uninstall")
    return {"ok": True, "message": "Uninstall queued." if created else "Job already running for this app.", "created": created}

@app.post("/api/install-all")
async def install_all():
    current_cc_version = get_cc_version()
    _, _, _, latest_ota = scan_bundles()
    pending = collect_install_candidates()
    if latest_ota and parse_version(latest_ota["version"]) > parse_version(current_cc_version):
        _write_json(UPDATE_ALL_PLAN_PATH, {
            "apps": [app["id"] for app in pending],
            "min_cc_version": latest_ota["version"],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        add_notification(f"Install all started. Control Center update to v{latest_ota['version']} will run first.", "control-center")
        return await ota_apply()
    queued = []
    for app in pending:
        item = next((b for b in app.get("bundles", []) if b.get("version") == app.get("latest_version")), None) or (app.get("bundles") or [None])[0]
        validate_bundle_dependencies(app["id"], item)
        maybe_queue_api_gateway_dependency(app["id"], item)
        job, created = create_job(app["id"], "install", bundle_filename=item["filename"] if item else None)
        queued.append({"app_id": app["id"], "created": created, "job_id": job.get("id")})
    if not queued:
        return {"ok": True, "message": "No installable bundles available."}
    add_notification(f"Install all queued {len(queued)} app install/update job(s)", "control-center")
    return {"ok": True, "message": f"Queued {len(queued)} install/update job(s)."}

@app.post("/api/update-all")
async def update_all():
    current_cc_version = get_cc_version()
    _, _, _, latest_ota = scan_bundles()
    pending = collect_update_candidates()
    if latest_ota and parse_version(latest_ota["version"]) > parse_version(current_cc_version):
        _write_json(UPDATE_ALL_PLAN_PATH, {
            "apps": [app["id"] for app in pending],
            "min_cc_version": latest_ota["version"],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        add_notification(f"Update all started. Control Center update to v{latest_ota['version']} will run first.", "control-center")
        return await ota_apply()
    queued = []
    for app in pending:
        item = next((b for b in app.get("bundles", []) if b.get("version") == app.get("latest_version")), None) or (app.get("bundles") or [None])[0]
        validate_bundle_dependencies(app["id"], item)
        maybe_queue_api_gateway_dependency(app["id"], item)
        job, created = create_job(app["id"], "install", bundle_filename=item["filename"] if item else None)
        queued.append({"app_id": app["id"], "created": created, "job_id": job.get("id")})
    if not queued:
        return {"ok": True, "message": "No app updates available."}
    add_notification(f"Update all queued {len(queued)} app update(s)", "control-center")
    return {"ok": True, "message": f"Queued {len(queued)} update(s)."}

@app.post("/api/ota/apply")
async def ota_apply():
    _, _, _, latest_ota = scan_bundles()
    if not latest_ota or parse_version(latest_ota["version"]) <= parse_version(app.version):
        return JSONResponse(status_code=404, content={"ok": False, "message": "No newer Control Center bundle uploaded."})
    bundle = INSTALLERS_DIR / latest_ota["filename"]
    root = extract_bundle(bundle)
    script = root / "scripts" / f"rebuild_control_center_v{latest_ota['version'].replace('.', '_')}.sh"
    if not script.exists():
        return JSONResponse(status_code=500, content={"ok": False, "message": "OTA script not found in uploaded Control Center bundle."})
    log_file = LOG_DIR / f"control-center-ota-{int(time.time())}.log"
    launcher = f"sleep 1; bash {script} > {log_file} 2>&1"
    subprocess.Popen(["bash", "-lc", launcher], cwd=str(root), env=os.environ.copy())
    add_notification(f"Control Center OTA started using {latest_ota['filename']}")
    return {"ok": True, "message": f"Control Center OTA started for v{latest_ota['version']}. Refresh in about 30 seconds."}


def _kill_job_process(job: dict):
    pid = job.get("pid")
    if not pid:
        return
    try:
        os.killpg(int(pid), signal.SIGTERM)
    except Exception:
        return

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("status") not in ("queued", "running"):
            raise HTTPException(400, "Only queued/running jobs can be canceled")
        job["cancel_requested"] = True
        job["message"] = "Cancel requested"
        job["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        snapshot = dict(job)
    _kill_job_process(snapshot)
    persist_jobs()
    return {"ok": True, "message": "Cancel requested."}

@app.post("/api/jobs/{job_id}/dismiss")
async def dismiss_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("status") in ("queued", "running"):
            raise HTTPException(400, "Running jobs cannot be dismissed. Cancel them first.")
        del JOBS[job_id]
    persist_jobs()
    return {"ok": True, "message": "Job dismissed."}

@app.post("/api/jobs/clear-all")
async def clear_all_jobs():
    with JOBS_LOCK:
        snapshots = [dict(v) for v in JOBS.values()]
        JOBS.clear()
        removed = len(snapshots)
    for job in snapshots:
        _kill_job_process(job)
    persist_jobs()
    return {"ok": True, "message": f"Cleared {removed} job(s)."}

@app.post("/api/jobs/clear-completed")
async def clear_completed_jobs():
    removed = 0
    with JOBS_LOCK:
        for jid in list(JOBS.keys()):
            if JOBS[jid].get("status") in ("success", "failed", "canceled"):
                del JOBS[jid]
                removed += 1
    persist_jobs()
    return {"ok": True, "message": f"Cleared {removed} completed job(s)."}

@app.get('/api/health')
async def control_center_health():
    return {'ok': True, 'service': 'Pi Control Center', 'version': app.version}
