const el = (id) => document.getElementById(id);
const openLogs = new Set();
const RETAG_MEMORY_KEY = 'song-downloader-retag-memory-v1';
let librarySongs = [];
let lastHealth = null;

async function fetchHealth() {
  const res = await fetch('/api/health', { cache: 'no-store' });
  const data = await res.json();
  lastHealth = data;
  const extra = data.default_cookies_path ? ' • cookies default set' : ' • no default cookies';
  // el('healthStatus').textContent = `OK • v${data.version}${extra}`;
  el('healthStatus').textContent = `OK • v${data.version}`;
}

function buildPayload(prefix = '') {
  return {
    song_name: el(`${prefix}song_name`).value.trim(),
    artist_names: el(`${prefix}artist_names`).value.trim(),
    album_name: el(`${prefix}album_name`).value.trim(),
    release_year: (el(`${prefix}release_year`)?.value || '').trim(),
    youtube_url: el(`${prefix}youtube_url`).value.trim(),
    cookies_path: (el(`${prefix}cookies_path`)?.value || '').trim(),
    rename_to: prefix ? '' : el('rename_to').value.trim(),
    auto_move: prefix ? true : el('auto_move').checked,
    selected_file: prefix ? el('selected_file').value : '',
    album_art_url: prefix ? (el('retag_album_art_url')?.value.trim() || '') : (el('album_art_url')?.value.trim() || ''),
  };
}

function clearInputs(ids) {
  ids.forEach((id) => {
    const node = el(id);
    if (!node) return;
    if (node.type === 'checkbox') node.checked = true;
    else node.value = '';
  });
}

function parseSongFilename(filePath) {
  const rawName = (filePath || '').split('/').pop() || '';
  const base = rawName.replace(/\.mp3$/i, '').trim();
  if (!base) return { song_name: '', album_name: '', artist_names: '' };

  const normalized = base
    .replace(/[–—]/g, '-')
    .replace(/[，]/g, ',')
    .replace(/\s+-\s+/g, ' - ')
    .trim();

  const parts = normalized.split(' - ').map((part) => part.trim()).filter(Boolean);
  if (parts.length >= 3) {
    return {
      song_name: parts[0],
      album_name: parts.slice(1, -1).join(' - '),
      artist_names: parts[parts.length - 1],
    };
  }
  if (parts.length === 2) {
    return {
      song_name: parts[0],
      album_name: '',
      artist_names: parts[1],
    };
  }
  return { song_name: normalized, album_name: '', artist_names: '' };
}

function loadRetagMemory() {
  try {
    return JSON.parse(localStorage.getItem(RETAG_MEMORY_KEY) || '{}');
  } catch {
    return {};
  }
}

function saveRetagMemory(memory) {
  localStorage.setItem(RETAG_MEMORY_KEY, JSON.stringify(memory));
}

function storeCurrentRetagState() {
  const selected = el('selected_file')?.value;
  if (!selected) return;
  const memory = loadRetagMemory();
  memory[selected] = {
    song_name: el('retag_song_name')?.value || '',
    artist_names: el('retag_artist_names')?.value || '',
    album_name: el('retag_album_name')?.value || '',
    release_year: el('retag_release_year')?.value || '',
    youtube_url: el('retag_youtube_url')?.value || '',
    cookies_path: el('retag_cookies_path')?.value || '',
    album_art_url: el('retag_album_art_url')?.value || '',
  };
  saveRetagMemory(memory);
}

function applyRetagStateForSelected() {
  const selected = el('selected_file').value;
  if (!selected) {
    ['retag_song_name', 'retag_album_name', 'retag_artist_names', 'retag_release_year', 'retag_youtube_url', 'retag_cookies_path', 'retag_album_art_url'].forEach((id) => {
      if (el(id)) el(id).value = '';
    });
    return;
  }

  const memory = loadRetagMemory();
  const remembered = memory[selected];
  if (remembered) {
    if (el('retag_song_name')) el('retag_song_name').value = remembered.song_name || '';
    if (el('retag_album_name')) el('retag_album_name').value = remembered.album_name || '';
    if (el('retag_artist_names')) el('retag_artist_names').value = remembered.artist_names || '';
    if (el('retag_release_year')) el('retag_release_year').value = remembered.release_year || '';
    if (el('retag_youtube_url')) el('retag_youtube_url').value = remembered.youtube_url || '';
    if (el('retag_cookies_path')) el('retag_cookies_path').value = remembered.cookies_path || '';
    if (el('retag_album_art_url')) el('retag_album_art_url').value = remembered.album_art_url || '';
    return;
  }

  const parsed = parseSongFilename(selected);
  if (el('retag_song_name')) el('retag_song_name').value = parsed.song_name || '';
  if (el('retag_album_name')) el('retag_album_name').value = parsed.album_name || '';
  if (el('retag_artist_names')) el('retag_artist_names').value = parsed.artist_names || '';
  if (el('retag_release_year')) el('retag_release_year').value = '';
  if (el('retag_youtube_url')) el('retag_youtube_url').value = '';
  if (el('retag_cookies_path')) el('retag_cookies_path').value = lastHealth?.default_cookies_path || '';
  if (el('retag_album_art_url')) el('retag_album_art_url').value = '';
}

function renderLibrarySongOptions(songs, preferredValue = '') {
  const select = el('selected_file');
  const currentValue = preferredValue || select.value;
  const search = (el('library_song_search')?.value || '').trim().toLowerCase();
  const filtered = songs.filter((song) => !search || song.path.toLowerCase().includes(search) || (song.name || '').toLowerCase().includes(search));

  select.innerHTML = '<option value="">Select a song from /mnt/nas/media/music</option>';
  filtered.forEach((song) => {
    const option = document.createElement('option');
    option.value = song.path;
    option.textContent = song.name || song.path;
    select.appendChild(option);
  });

  if (currentValue && Array.from(select.options).some((option) => option.value === currentValue)) {
    select.value = currentValue;
  } else if (filtered.length === 1) {
    select.value = filtered[0].path;
  } else {
    select.value = '';
  }

  applyRetagStateForSelected();
}

function progressWidth(job) {
  const value = Number(job.progress || 0);
  return `${Math.max(0, Math.min(100, value))}%`;
}

function rememberOpenLogs() {
  document.querySelectorAll('.logs-box[data-job-id]').forEach((node) => {
    const id = node.dataset.jobId;
    if (node.open) openLogs.add(id);
    else openLogs.delete(id);
  });
}

function escapeHtml(text) {
  return String(text || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderJobSummary(jobs) {
  const summaryNode = el('jobsSummary');
  if (!summaryNode) return;
  const counts = {
    total: jobs.length,
    queued: 0,
    running: 0,
    retrying: 0,
    completed: 0,
    failed: 0,
    aborted: 0,
    blocked: 0,
    rate_limited: 0,
  };

  jobs.forEach((job) => {
    counts[job.status] = (counts[job.status] || 0) + 1;
    if (job.failure_category === 'bot_check') counts.blocked += 1;
    if (job.failure_category === 'rate_limited') counts.rate_limited += 1;
  });

  summaryNode.innerHTML = `
    <strong>Total:</strong> ${counts.total}
    &nbsp;•&nbsp; <strong>Queued:</strong> ${counts.queued}
    &nbsp;•&nbsp; <strong>Running:</strong> ${counts.running}
    &nbsp;•&nbsp; <strong>Retrying:</strong> ${counts.retrying}
    &nbsp;•&nbsp; <strong>Completed:</strong> ${counts.completed}
    &nbsp;•&nbsp; <strong>Failed:</strong> ${counts.failed}
    &nbsp;•&nbsp; <strong>Aborted:</strong> ${counts.aborted}
    &nbsp;•&nbsp; <strong>Bot check:</strong> ${counts.blocked}
    &nbsp;•&nbsp; <strong>429:</strong> ${counts.rate_limited}
  `;
}

function renderJobs(jobs) {
  rememberOpenLogs();
  renderJobSummary(jobs);
  const container = el('jobsContainer');
  container.innerHTML = '';
  if (!jobs.length) {
    container.innerHTML = '<div class="empty-state">No jobs yet.</div>';
    return;
  }

  jobs.forEach((job) => {
    const song = job.payload?.song_name || job.payload?.selected_file || '—';
    const artists = job.payload?.artist_names || '—';
    const album = job.payload?.album_name || 'Unknown';
    const youtube = job.payload?.youtube_url || 'Search mode';
    const jobType = job.payload?.job_type || 'download';
    const attempts = Number(job.attempts || 0);
    const friendlyError = job.failure_hint || job.error || '—';
    const extraMeta = [
      job.payload?.release_year ? `<div><strong>Year:</strong> ${escapeHtml(job.payload.release_year)}</div>` : '',
      job.failure_category ? `<div><strong>Failure type:</strong> ${escapeHtml(job.failure_category)}</div>` : '',
      attempts ? `<div><strong>Attempts:</strong> ${attempts}</div>` : '',
      job.payload?.cookies_path ? `<div><strong>Cookies:</strong> ${escapeHtml(job.payload.cookies_path)}</div>` : '',
      job.retriable ? `<div><strong>Retryable:</strong> yes</div>` : '',
    ].filter(Boolean).join('');

    const card = document.createElement('article');
    card.className = 'job-card';
    card.innerHTML = `
      <div class="job-top">
        <div>
          <div class="job-status ${escapeHtml(job.status)}">${escapeHtml(job.status)}</div>
          <div class="job-time">${escapeHtml(job.updated_at || job.created_at || '')}</div>
        </div>
        <div class="job-actions-top">
          <div class="job-id">${escapeHtml(job.id.slice(0, 8))}</div>
          ${(job.status === 'running' || job.status === 'queued' || job.status === 'retrying') ? `<button type="button" class="ghost-btn danger abort-job-btn" data-job-id="${escapeHtml(job.id)}">Abort job</button>` : ''}
        </div>
      </div>
      <div class="job-main">
        <div><strong>Type:</strong> ${escapeHtml(jobType)}</div>
        <div><strong>Song:</strong> ${escapeHtml(song)}</div>
        <div><strong>Artists:</strong> ${escapeHtml(artists)}</div>
        <div><strong>Album:</strong> ${escapeHtml(album)}</div>
        <div><strong>YouTube:</strong> ${escapeHtml(youtube)}</div>
        ${extraMeta}
        <div><strong>Final file:</strong> ${escapeHtml(job.final_file || '—')}</div>
        <div><strong>Error:</strong> ${escapeHtml(friendlyError)}</div>
      </div>
      <div class="progress-wrap">
        <div class="progress-bar"><span style="width:${progressWidth(job)}"></span></div>
        <div class="progress-label">${Number(job.progress || 0)}%</div>
      </div>
      <details class="logs-box" data-job-id="${escapeHtml(job.id)}">
        <summary>Logs</summary>
        <pre>${escapeHtml((job.logs || []).join('\n'))}</pre>
      </details>
    `;
    container.appendChild(card);
    const details = card.querySelector('.logs-box');
    if (openLogs.has(job.id)) details.open = true;
    details.addEventListener('toggle', (event) => {
      if (event.currentTarget.open) openLogs.add(job.id);
      else openLogs.delete(job.id);
    });

    const abortBtn = card.querySelector('.abort-job-btn');
    if (abortBtn) {
      abortBtn.addEventListener('click', async () => {
        abortBtn.disabled = true;
        const res = await fetch(`/api/jobs/${job.id}/abort`, { method: 'POST' });
        const data = await res.json().catch(() => ({}));
        if (!data.ok) alert(data.error || 'Failed to abort job');
        fetchJobs();
      });
    }
  });
}

async function fetchJobs() {
  const res = await fetch('/api/jobs', { cache: 'no-store' });
  const data = await res.json();
  renderJobs(data.jobs || []);
}

async function fetchLibrarySongs() {
  const res = await fetch('/api/library-songs', { cache: 'no-store' });
  const data = await res.json();
  librarySongs = data.songs || [];
  renderLibrarySongOptions(librarySongs, el('selected_file')?.value || '');
}

async function submitDownload(event) {
  event.preventDefault();
  const payload = buildPayload('');

  if (!payload.youtube_url && (!payload.song_name || !payload.artist_names)) {
    alert('Provide either a YouTube link or at least song name + artist names.');
    return;
  }

  const res = await fetch('/api/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!data.ok) {
    alert(data.error || 'Failed to queue download');
    return;
  }
  clearInputs(['song_name', 'artist_names', 'album_name', 'release_year', 'youtube_url', 'cookies_path', 'album_art_url', 'rename_to']);
  fetchJobs();
}

async function submitRetag(event) {
  event.preventDefault();
  const payload = buildPayload('retag_');
  if (!payload.selected_file) {
    alert('Select a downloaded song to retag.');
    return;
  }
  if (!payload.youtube_url && (!payload.song_name || !payload.artist_names)) {
    alert('Provide either a YouTube link or at least song name + artist names for metadata lookup.');
    return;
  }

  const res = await fetch('/api/retag', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!data.ok) {
    alert(data.error || 'Failed to queue retag job');
    return;
  }
  storeCurrentRetagState();
  fetchLibrarySongs();
  fetchJobs();
}

async function clearJobs() {
  openLogs.clear();
  await fetch('/api/jobs/clear', { method: 'POST' });
  fetchJobs();
}

async function abortAllJobs() {
  const res = await fetch('/api/jobs/abort-all', { method: 'POST' });
  const data = await res.json().catch(() => ({}));
  if (!data.ok) return alert(data.error || 'Failed to abort all jobs');
  fetchJobs();
}

async function refreshJobsAndClearInputs() {
  clearInputs([
    'song_name', 'artist_names', 'album_name', 'release_year', 'youtube_url', 'cookies_path', 'album_art_url', 'rename_to', 'batch_json',
    'retag_song_name', 'retag_artist_names', 'retag_album_name', 'retag_release_year', 'retag_youtube_url', 'retag_cookies_path', 'retag_album_art_url', 'selected_file', 'library_song_search',
  ]);
  await clearJobs();
  await fetchJobs();
}

async function submitBatchDownload() {
  const raw = el('batch_json').value.trim();
  if (!raw) return alert('Paste JSON payload first.');
  let payload;
  try { payload = JSON.parse(raw); } catch { return alert('Invalid JSON payload'); }
  const res = await fetch('/api/download-batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!data.ok) return alert(data.error || 'Failed to queue multi song download');
  clearInputs(['batch_json']);
  fetchJobs();
}

async function submitRetagAll() {
  const res = await fetch('/api/retag-all', { method: 'POST' });
  const data = await res.json();
  if (!data.ok) return alert(data.error || 'Failed to queue retag all');
  fetchJobs();
}

window.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.clear-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = el(btn.dataset.target);
      if (!target) return;
      target.value = '';
      if (target.id === 'library_song_search') renderLibrarySongOptions(librarySongs, '');
      if (target.id === 'selected_file') applyRetagStateForSelected();
      if (target.id.startsWith('retag_')) storeCurrentRetagState();
    });
  });

  ['retag_song_name', 'retag_artist_names', 'retag_album_name', 'retag_release_year', 'retag_youtube_url', 'retag_cookies_path', 'retag_album_art_url'].forEach((id) => {
    const node = el(id);
    if (node) node.addEventListener('input', storeCurrentRetagState);
  });

  el('downloadForm').addEventListener('submit', submitDownload);
  el('retagForm').addEventListener('submit', submitRetag);
  if (el('batchDownloadForm')) el('batchDownloadForm').addEventListener('submit', (e) => { e.preventDefault(); submitBatchDownload(); });
  el('refreshJobsBtn').addEventListener('click', refreshJobsAndClearInputs);
  el('clearJobsBtn').addEventListener('click', clearJobs);
  if (el('abortAllJobsBtn')) el('abortAllJobsBtn').addEventListener('click', abortAllJobs);
  el('refreshLibraryBtn').addEventListener('click', fetchLibrarySongs);
  el('selected_file').addEventListener('change', applyRetagStateForSelected);
  el('library_song_search').addEventListener('input', () => { renderLibrarySongOptions(librarySongs, el('selected_file')?.value || ''); });
  if (el('retagAllBtn')) el('retagAllBtn').addEventListener('click', submitRetagAll);

  fetchHealth();
  fetchJobs();
  fetchLibrarySongs();
  setInterval(fetchJobs, 1500);
});
