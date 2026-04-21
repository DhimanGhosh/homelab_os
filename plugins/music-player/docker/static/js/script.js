const S = {
    lib: null,
    trackMap: new Map(),
    view: 'home',
    entity: null,
    queue: [],
    index: -1,
    shuffle: false,
    repeat: 'off',
    search: '',
    dragging: false,
};

const $ = (id) => document.getElementById(id);
const audio = new Audio();
audio.preload = 'metadata';

function el(tag, cls, txt) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (txt !== undefined) node.textContent = txt;
    return node;
}

function fmt(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
}

async function api(url, opt = {}) {
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...opt,
    });
    if (!res.ok) {
        throw new Error(await res.text());
    }
    return res.json();
}

function trackById(id) {
    return S.trackMap.get(id);
}

function collect(ids) {
    return (ids || []).map(trackById).filter(Boolean);
}

function filterTracks(list) {
    const q = S.search.trim().toLowerCase();
    if (!q) return list;
    return list.filter((t) =>
        [t.title, t.artist, t.album, t.folder, t.year].join(' ').toLowerCase().includes(q)
    );
}

function setActiveNav() {
    document.querySelectorAll('.yt-nav-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.view === S.view);
    });
}

function artNode(track, cls = 'media-art') {
    const node = el('div', cls);
    if (track?.album_art) {
        const img = el('img');
        img.src = track.album_art;
        node.appendChild(img);
    } else {
        node.appendChild(el('div', 'fallback', '♪'));
    }
    return node;
}

function normalizePlaylists(playlists) {
    if (Array.isArray(playlists)) return playlists;
    return Object.entries(playlists || {}).map(([name, tracks]) => ({
        name,
        tracks,
        count: (tracks || []).length,
    }));
}

function renderSidebarPlaylists() {
    const box = $('sidebarPlaylists');
    box.innerHTML = '';
    normalizePlaylists(S.lib.playlists).forEach((p) => {
        const item = el('div', 'sidebar-playlist-item', p.name);
        item.onclick = () => {
            S.view = 'playlists';
            S.entity = p;
            render();
        };
        box.appendChild(item);
    });
}

function updatePlayer() {
    const t = trackById(S.queue[S.index]);
    $('playerTitle').textContent = t?.title || 'Nothing playing';
    $('playerSub').textContent = t
        ? `${t.artist} · ${t.album || 'Unknown'}${t.year ? ` · ${t.year}` : ''}`
        : 'Select a track to start playback';

    const art = $('playerArt');
    art.innerHTML = '';
    if (t?.album_art) {
        const img = el('img');
        img.src = t.album_art;
        art.appendChild(img);
    } else {
        art.appendChild(el('span', '', '♪'));
    }

    $('playPauseBtn').textContent = audio.paused ? '▶' : '⏸';
    $('repeatBtn').textContent = S.repeat === 'off' ? 'Off' : S.repeat === 'all' ? 'All' : 'One';
    $('shuffleBtn').style.outline = S.shuffle ? '1px solid #6f95ff' : 'none';
}

function renderQueue() {
    const q = $('queueList');
    q.innerHTML = '';
    const ids = S.queue || [];
    $('queueSubtitle').textContent = `${ids.length} song(s)`;

    ids.forEach((id, idx) => {
        const t = trackById(id);
        if (!t) return;

        const row = el('div', `queue-item ${idx === S.index ? 'active' : ''}`);
        row.append(
            el('div', 'queue-item-title', t.title),
            el('div', 'queue-item-sub', `${t.artist} · ${fmt(t.duration)}`)
        );
        row.onclick = () => {
            S.index = idx;
            loadCurrent();
        };
        q.appendChild(row);
    });
}

function loadCurrent() {
    const t = trackById(S.queue[S.index]);
    if (!t) return;
    audio.src = t.stream_url || t.url;
    audio.play().catch(() => { });
    updatePlayer();
    renderQueue();
}

function shuffleIds(ids) {
    const copy = [...ids];
    for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
}

function playTracks(tracks, start = 0) {
    if (!tracks.length) return;

    let ids = tracks.map((t) => t.id);

    if (S.shuffle) {
        const current = ids[start];
        ids.splice(start, 1);
        ids = [current, ...shuffleIds(ids)];
        S.index = 0;
    } else {
        S.index = start;
    }

    S.queue = ids;
    loadCurrent();
}

function queueNext(track) {
    if (!track) return;

    if (!S.queue.length) {
        playTracks([track], 0);
        return;
    }

    S.queue.splice(S.index + 1, 0, track.id);
    renderQueue();
}

function section(title, subtitle, content) {
    const sec = el('section', 'home-section');
    const head = el('div', 'section-head');
    const left = el('div');

    left.append(
        el('h2', 'section-title', title),
        el('div', 'section-sub', subtitle)
    );

    head.appendChild(left);
    sec.append(head, content);
    return sec;
}

function mediaCard(item, track, suffix, onClick) {
    const card = el('div', 'media-card');
    const art = artNode(track, 'media-art');
    const overlay = el('div', 'play-overlay', '▶');

    art.appendChild(overlay);
    card.append(
        art,
        el('div', 'media-title', item.name || track.title),
        el('div', 'media-meta', suffix)
    );
    card.onclick = onClick;
    return card;
}

function rowCard(track, list, idx) {
    const row = el('div', 'row-card');
    row.append(artNode(track, 'row-art'));

    const main = el('div', 'row-main');
    main.append(
        el('div', 'row-title', track.title),
        el(
            'div',
            'row-meta',
            `${track.artist} · ${track.album || 'Unknown'}${track.year ? ` · ${track.year}` : ''} · ${fmt(track.duration)}`
        )
    );

    const btn = el('button', 'ghost-btn', 'Play next');
    btn.onclick = (e) => {
        e.stopPropagation();
        queueNext(track);
    };

    row.append(main, btn);
    row.onclick = () => playTracks(list, idx);
    return row;
}

function entityCard(entity) {
    const sample = trackById(entity.tracks?.[0]);
    const card = el('div', 'entity-card');
    card.append(
        artNode(sample, 'media-art'),
        el('div', 'entity-title', entity.name),
        el('div', 'entity-count', `${entity.count} track(s)`)
    );
    card.onclick = () => {
        S.entity = entity;
        render();
    };
    return card;
}

function renderHome() {
    const area = $('contentArea');
    area.innerHTML = '';
    $('chipsBar').innerHTML = '';
    $('contextHeader').classList.add('hidden');

    ['All', 'Artists', 'Albums', 'Playlists', 'Folders'].forEach((name, i) => {
        const b = el('button', `chip ${i === 0 ? 'active' : ''}`, name);
        b.onclick = () => {
            if (name === 'All') {
                S.view = 'home';
                S.entity = null;
            } else {
                S.view = name.toLowerCase();
            }
            render();
        };
        $('chipsBar').appendChild(b);
    });

    const tracks = filterTracks(S.lib.tracks);

    const quick = el('div', 'media-row');
    tracks.slice(0, 6).forEach((t, i) => {
        quick.append(
            mediaCard(
                t,
                t,
                `${t.artist}${t.album && t.album !== 'Unknown' ? ` · ${t.album}` : ''}`,
                () => playTracks(tracks, i)
            )
        );
    });
    area.append(section('Listen again', 'Local library picks', quick));

    const artistRow = el('div', 'media-row');
    S.lib.artists.slice(0, 6).forEach((a) => {
        artistRow.append(
            mediaCard(
                a,
                trackById(a.tracks[0]),
                `${a.count} track(s)`,
                () => {
                    S.view = 'artists';
                    S.entity = a;
                    render();
                }
            )
        );
    });
    area.append(section('Artists', 'Open an artist to browse songs', artistRow));

    const albumRow = el('div', 'media-row');
    S.lib.albums.slice(0, 6).forEach((a) => {
        albumRow.append(
            mediaCard(
                a,
                trackById(a.tracks[0]),
                `${a.count} track(s)`,
                () => {
                    S.view = 'albums';
                    S.entity = a;
                    render();
                }
            )
        );
    });
    area.append(section('Albums', 'Browse by album', albumRow));

    const list = el('div', 'list-section');
    tracks.slice(0, 12).forEach((t, i) => list.append(rowCard(t, tracks, i)));
    area.append(section('Quick picks', 'Start anywhere', list));
}

function renderCollection() {
    const area = $('contentArea');
    area.innerHTML = '';
    $('chipsBar').innerHTML = '';

    const hdr = $('contextHeader');

    if (S.entity) {
        hdr.classList.remove('hidden');
        hdr.textContent = `Viewing ${S.view.replace(/s$/, '')}: ${S.entity.name}`;

        const tracks = filterTracks(collect(S.entity.tracks));
        const sec = el('section', 'home-section');
        const head = el('div', 'section-head');
        const left = el('div');

        left.append(
            el('h2', 'section-title', S.entity.name),
            el('div', 'section-sub', `${tracks.length} track(s)`)
        );

        const actions = el('div');
        const playBtn = el('button', 'ghost-btn', 'Play all');
        playBtn.onclick = () => playTracks(tracks, 0);

        const shuf = el('button', 'ghost-btn', 'Shuffle');
        shuf.onclick = () => {
            S.shuffle = true;
            playTracks(tracks, Math.floor(Math.random() * tracks.length));
        };

        actions.append(playBtn, shuf);
        head.append(left, actions);
        sec.append(head);

        const list = el('div', 'list-section');
        tracks.forEach((t, i) => list.append(rowCard(t, tracks, i)));
        sec.append(list);
        area.append(sec);
        return;
    }

    hdr.classList.add('hidden');

    const mapping = {
        all: S.lib.tracks,
        artists: S.lib.artists,
        albums: S.lib.albums,
        playlists: normalizePlaylists(S.lib.playlists),
        folders: S.lib.folders || [],
    };

    const items = mapping[S.view] || [];
    const sec = el('section', 'home-section');
    const head = el('div', 'section-head');
    const left = el('div');

    left.append(
        el('h2', 'section-title', S.view === 'all' ? 'All Songs' : S.view[0].toUpperCase() + S.view.slice(1)),
        el('div', 'section-sub', `${items.length} shown`)
    );
    head.append(left);
    sec.append(head);

    if (S.view === 'all') {
        const list = el('div', 'list-section');
        const filtered = filterTracks(items);
        filtered.forEach((t, i) => list.append(rowCard(t, filtered, i)));
        sec.append(list);
    } else {
        const grid = el('div', 'entity-grid');
        items.forEach((it) => grid.append(entityCard(it)));
        sec.append(grid);
    }

    area.append(sec);
}

function render() {
    setActiveNav();
    renderSidebarPlaylists();
    if (S.view === 'home') {
        renderHome();
    } else {
        renderCollection();
    }
}

async function load() {
    S.lib = await api('/api/library');
    S.lib.tracks = S.lib.tracks || S.lib.songs || [];
    S.trackMap = new Map(S.lib.tracks.map((t) => [t.id, t]));
    S.lib.artists = S.lib.artists || [];
    S.lib.albums = S.lib.albums || [];
    S.lib.folders = S.lib.folders || [];
    render();
    updatePlayer();
    renderQueue();
}

document.querySelectorAll('.yt-nav-btn').forEach((btn) => {
    btn.onclick = () => {
        S.view = btn.dataset.view;
        S.entity = null;
        render();
    };
});

$('searchInput').addEventListener('input', (e) => {
    S.search = e.target.value;
    render();
});

$('refreshBtn').onclick = load;

$('shuffleAllBtn').onclick = () => {
    S.shuffle = true;
    const tracks = filterTracks(S.lib.tracks);
    if (tracks.length) {
        playTracks(tracks, Math.floor(Math.random() * tracks.length));
    }
};

$('playPauseBtn').onclick = () => {
    if (!audio.src) {
        const tracks = filterTracks(S.lib.tracks);
        if (tracks.length) playTracks(tracks, 0);
        return;
    }
    if (audio.paused) audio.play();
    else audio.pause();
};

$('prevBtn').onclick = () => {
    if (audio.currentTime > 5) {
        audio.currentTime = 0;
    } else if (S.index > 0) {
        S.index -= 1;
        loadCurrent();
    }
};

$('nextBtn').onclick = () => {
    if (S.index < S.queue.length - 1) {
        S.index += 1;
        loadCurrent();
    } else if (S.repeat === 'all') {
        S.index = 0;
        loadCurrent();
    }
};

$('shuffleBtn').onclick = () => {
    S.shuffle = !S.shuffle;
    updatePlayer();
};

$('repeatBtn').onclick = () => {
    S.repeat = S.repeat === 'off' ? 'all' : S.repeat === 'all' ? 'one' : 'off';
    updatePlayer();
};

$('queueBtn').onclick = () => $('queueDrawer').classList.remove('hidden');
$('closeQueueBtn').onclick = () => $('queueDrawer').classList.add('hidden');
$('queueDrawer').onclick = (e) => {
    if (e.target.id === 'queueDrawer') $('queueDrawer').classList.add('hidden');
};

$('newPlaylistBtn').onclick = () => $('playlistModal').classList.remove('hidden');
$('closePlaylistModalBtn').onclick = () => $('playlistModal').classList.add('hidden');
$('playlistModal').onclick = (e) => {
    if (e.target.classList.contains('modal-backdrop')) {
        $('playlistModal').classList.add('hidden');
    }
};

$('createPlaylistConfirmBtn').onclick = async () => {
    const name = $('playlistNameInput').value.trim();
    if (!name) return;
    await api('/api/playlists', {
        method: 'POST',
        body: JSON.stringify({ name, track_ids: [] }),
    });
    $('playlistNameInput').value = '';
    $('playlistModal').classList.add('hidden');
    load();
};

audio.addEventListener('play', updatePlayer);
audio.addEventListener('pause', updatePlayer);

audio.addEventListener('timeupdate', () => {
    if (!S.dragging && audio.duration) {
        $('seekRange').value = Math.floor((audio.currentTime / audio.duration) * 1000);
    }
    $('timeCurrent').textContent = fmt(audio.currentTime);
    $('timeTotal').textContent = fmt(audio.duration || 0);
});

audio.addEventListener('ended', () => {
    if (S.repeat === 'one') {
        audio.currentTime = 0;
        audio.play();
        return;
    }
    if (S.index < S.queue.length - 1) {
        S.index += 1;
        loadCurrent();
    } else if (S.repeat === 'all') {
        S.index = 0;
        loadCurrent();
    }
});

$('seekRange').addEventListener('input', () => {
    S.dragging = true;
    if (audio.duration) {
        $('timeCurrent').textContent = fmt(($('seekRange').value / 1000) * audio.duration);
    }
});

$('seekRange').addEventListener('change', () => {
    if (audio.duration) {
        audio.currentTime = ($('seekRange').value / 1000) * audio.duration;
    }
    S.dragging = false;
});

load();