async function loadStatus() {
  const container = document.getElementById('status-cards');
  try {
    const res = await fetch('/api/debug/upstreams');
    const data = await res.json();
    const services = [
      { key: 'music_player', label: 'Music Player', icon: '🎵' },
      { key: 'files',        label: 'Files',        icon: '📁' },
      { key: 'pihole',       label: 'Pi-hole',      icon: '🛡'  },
    ];
    container.innerHTML = services.map(({ key, label, icon }) => {
      const s = data[key] || {};
      const ok = s.ok;
      return `<div class="card ${ok ? 'card-ok' : 'card-err'}">
        <div class="card-icon">${icon}</div>
        <div class="card-body">
          <div class="card-name">${label}</div>
          <div class="card-status ${ok ? 'status-ok' : 'status-err'}">${ok ? 'Online' : 'Offline'}</div>
        </div>
      </div>`;
    }).join('');
  } catch {
    container.innerHTML = '<p class="error">Could not fetch upstream status.</p>';
  }
}

loadStatus();
