const elements = {
  badge: document.querySelector('#statusBadge'),
  preview: document.querySelector('#previewFrame'),
  previewCover: document.querySelector('#previewCover'),
  start: document.querySelector('#startButton'),
  stop: document.querySelector('#stopButton'),
  name: document.querySelector('#recordingName'),
  elapsed: document.querySelector('#elapsed'),
  currentSize: document.querySelector('#currentSize'),
  filename: document.querySelector('#outputFilename'),
  disk: document.querySelector('#diskSpace'),
  video: document.querySelector('#videoDevice'),
  audio: document.querySelector('#audioDevice'),
  profile: document.querySelector('#captureProfile'),
  devices: document.querySelector('#deviceSuggestions'),
  message: document.querySelector('#message'),
  list: document.querySelector('#recordingsList'),
  stopDialog: document.querySelector('#stopDialog'),
};

let currentStatus = null;
let previewWasAvailable = false;
let previewUrl = `${location.protocol}//${location.hostname}:8889/vhs`;

const statusLabels = {
  initialising: 'Initialising',
  preview_available: 'Preview available',
  starting_recording: 'Starting recording',
  recording: 'Recording',
  stopping: 'Stopping',
  error: 'Error',
};

function bytes(value) {
  if (value === null || value === undefined) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = Number(value);
  let unit = 0;
  while (size >= 1000 && unit < units.length - 1) { size /= 1000; unit += 1; }
  const precision = unit === 0 ? 0 : size >= 10 ? 1 : 2;
  return `${size.toFixed(precision)} ${units[unit]}`;
}

function duration(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Unknown duration';
  const total = Math.max(0, Math.floor(Number(value)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function showMessage(text) {
  elements.message.textContent = text || '';
  elements.message.hidden = !text;
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  let payload = {};
  try { payload = await response.json(); } catch (_) { /* no JSON body */ }
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}

function loadPreview() {
  elements.preview.src = previewUrl;
}

async function loadConfiguration() {
  const config = await request('/api/config');
  previewUrl = config.preview_url;
  elements.profile.textContent = `${config.video_standard} · ${config.master_resolution} · ${config.master_display_aspect_ratio}`;
  loadPreview();
}

async function loadDevices() {
  try {
    const payload = await request('/api/devices');
    const suggestions = [];
    if (payload.video.length) {
      suggestions.push(`Video: ${payload.video.map(item => `${item.device} (${item.label})`).join(', ')}`);
    }
    if (payload.audio.length) {
      suggestions.push(`Audio: ${payload.audio.map(item => `${item.device} (${item.label})`).join(', ')}`);
    }
    if (!suggestions.length) suggestions.push('No additional host devices are visible to this container.');
    elements.devices.replaceChildren(...suggestions.map(text => {
      const line = document.createElement('div');
      line.textContent = text;
      return line;
    }));
  } catch (error) {
    elements.devices.textContent = `Device scan unavailable: ${error.message}`;
  }
}

function renderStatus(status) {
  currentStatus = status;
  elements.badge.className = `status status-${status.state}`;
  elements.badge.querySelector('strong').textContent = statusLabels[status.state] || status.state;
  const busy = ['starting_recording', 'stopping', 'initialising'].includes(status.state);
  elements.start.disabled = status.recording || busy || status.state === 'error';
  elements.stop.disabled = !status.recording || status.state === 'stopping';
  elements.name.disabled = status.recording || busy;
  elements.elapsed.textContent = duration(status.elapsed_seconds);
  elements.currentSize.textContent = status.filename ? bytes(status.file_size_bytes) : '—';
  elements.filename.textContent = status.filename || 'No recording active';
  elements.disk.textContent = bytes(status.disk?.free_bytes);
  elements.video.textContent = status.video_device;
  elements.audio.textContent = status.audio_device;
  showMessage(status.last_error);

  if (status.preview_available && !previewWasAvailable) loadPreview();
  previewWasAvailable = status.preview_available;
  elements.previewCover.classList.toggle('hidden', status.preview_available);
}

async function pollStatus() {
  try {
    renderStatus(await request('/api/status'));
  } catch (error) {
    elements.badge.className = 'status status-error';
    elements.badge.querySelector('strong').textContent = 'Disconnected';
    showMessage(`Control service unavailable: ${error.message}`);
    elements.start.disabled = true;
    elements.stop.disabled = true;
  }
}

async function startRecording() {
  showMessage('');
  elements.start.disabled = true;
  try {
    await request('/api/recordings/start', {
      method: 'POST',
      body: JSON.stringify({ name: elements.name.value || 'recording' }),
    });
    await pollStatus();
  } catch (error) {
    showMessage(error.message);
    await pollStatus();
  }
}

async function stopRecording() {
  showMessage('');
  try {
    await request('/api/recordings/stop', { method: 'POST' });
    await Promise.all([pollStatus(), loadRecordings()]);
  } catch (error) {
    showMessage(error.message);
    await pollStatus();
  }
}

function recordingRow(item) {
  const row = document.createElement('article');
  row.className = 'recording-item';

  const title = document.createElement('div');
  title.className = 'recording-title';
  const strong = document.createElement('strong');
  strong.textContent = item.filename;
  const date = document.createElement('span');
  date.textContent = new Date(item.date).toLocaleString();
  if (item.interrupted) {
    date.textContent += ' · Interrupted / recoverable';
    date.className = 'recovery-badge';
  }
  title.append(strong, date);

  const meta = document.createElement('div');
  meta.className = 'recording-meta';
  meta.textContent = `${duration(item.duration_seconds)} · ${bytes(item.size_bytes)}`;

  const actions = document.createElement('div');
  actions.className = 'recording-actions';
  if (item.interrupted) {
    if (item.recoverable) {
      const recover = document.createElement('button');
      recover.className = 'small-button recover';
      recover.type = 'button';
      recover.textContent = 'Recover';
      recover.addEventListener('click', () => recoverRecording(item.filename, recover));
      actions.append(recover);
    }
  } else {
    const play = document.createElement('a');
    play.className = 'small-button';
    play.href = `/recordings/${encodeURIComponent(item.filename)}`;
    play.target = '_blank';
    play.rel = 'noopener';
    play.textContent = 'Play';
    const download = document.createElement('a');
    download.className = 'small-button';
    download.href = `/recordings/${encodeURIComponent(item.filename)}?download=true`;
    download.textContent = 'Download';
    actions.append(play, download);
  }
  row.append(title, meta, actions);
  return row;
}

async function loadRecordings() {
  try {
    const payload = await request('/api/recordings');
    elements.list.replaceChildren();
    if (!payload.recordings.length) {
      const empty = document.createElement('p');
      empty.className = 'empty';
      empty.textContent = 'No recordings found.';
      elements.list.append(empty);
      return;
    }
    payload.recordings.slice(0, 30).forEach(item => elements.list.append(recordingRow(item)));
  } catch (error) {
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = `Could not load recordings: ${error.message}`;
    elements.list.replaceChildren(empty);
  }
}

async function recoverRecording(filename, button) {
  if (!confirm(`Create a recovered MKV from ${filename}? The partial file will be preserved.`)) return;
  button.disabled = true;
  try {
    await request(`/api/recordings/${encodeURIComponent(filename)}/recover`, { method: 'POST' });
    await loadRecordings();
  } catch (error) {
    showMessage(error.message);
    button.disabled = false;
  }
}

elements.start.addEventListener('click', startRecording);
elements.stop.addEventListener('click', () => elements.stopDialog.showModal());
elements.stopDialog.addEventListener('close', () => {
  if (elements.stopDialog.returnValue === 'confirm') stopRecording();
});
document.querySelector('#restartPreview').addEventListener('click', async () => {
  try {
    await request('/api/preview/restart', { method: 'POST' });
    previewWasAvailable = false;
    await pollStatus();
  } catch (error) { showMessage(error.message); }
});
document.querySelector('#refreshRecordings').addEventListener('click', loadRecordings);

loadConfiguration().catch(error => showMessage(`Configuration unavailable: ${error.message}`));
loadDevices();
pollStatus();
loadRecordings();
setInterval(pollStatus, 1000);
setInterval(loadRecordings, 15000);
