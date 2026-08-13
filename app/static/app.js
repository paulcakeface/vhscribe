const elements = {
  badge: document.querySelector('#statusBadge'),
  preview: document.querySelector('#previewFrame'),
  previewCover: document.querySelector('#previewCover'),
  previewCoverTitle: document.querySelector('#previewCoverTitle'),
  previewCoverDetail: document.querySelector('#previewCoverDetail'),
  previewState: document.querySelector('#previewState'),
  previewTimeout: document.querySelector('#previewTimeout'),
  startPreview: document.querySelector('#startPreview'),
  stopPreview: document.querySelector('#stopPreview'),
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
let previewLoaded = false;
let previewUrl = `${location.protocol}//${location.hostname}:8889/vhs`;

const statusLabels = {
  idle: 'Idle',
  starting_preview: 'Starting preview',
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
  if (previewLoaded) return;
  elements.preview.src = previewUrl;
  previewLoaded = true;
}

function unloadPreview() {
  if (!previewLoaded) return;
  elements.preview.removeAttribute('src');
  previewLoaded = false;
}

async function loadConfiguration() {
  const config = await request('/api/config');
  const previewUrlChanged = previewUrl !== config.preview_url;
  previewUrl = config.preview_url;
  if (previewUrlChanged && previewLoaded) {
    unloadPreview();
    if (currentStatus?.preview_available) loadPreview();
  }
  elements.profile.textContent = `${config.video_standard} · ${config.master_resolution} · ${config.master_display_aspect_ratio}`;
  const minutes = config.preview_idle_timeout_seconds / 60;
  const timeout = Number.isInteger(minutes) ? minutes : minutes.toFixed(1);
  elements.previewTimeout.textContent = `Preview automatically stops after ${timeout} minutes without a visible-dashboard heartbeat. Recordings are never stopped by this timer.`;
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
  const busy = ['starting_recording', 'stopping'].includes(status.state);
  const previewProcess = status.process_alive && ['preview', 'recording'].includes(status.mode);
  elements.start.disabled = status.recording || busy;
  elements.stop.disabled = !status.recording || status.state === 'stopping';
  elements.name.disabled = status.recording || busy;
  elements.startPreview.disabled = previewProcess || status.recording || busy;
  elements.stopPreview.disabled = !previewProcess || status.recording || status.state === 'stopping';
  elements.elapsed.textContent = duration(status.elapsed_seconds);
  elements.currentSize.textContent = status.filename ? bytes(status.file_size_bytes) : '—';
  elements.filename.textContent = status.filename || 'No recording active';
  elements.disk.textContent = bytes(status.disk?.free_bytes);
  elements.video.textContent = status.video_device;
  elements.audio.textContent = status.audio_device;
  showMessage(status.last_error);

  if (status.preview_available) loadPreview();
  if (!status.process_alive) unloadPreview();
  elements.previewCover.classList.toggle('hidden', status.preview_available);

  if (status.state === 'starting_preview') {
    elements.previewCoverTitle.textContent = 'Starting preview…';
    elements.previewCoverDetail.textContent = 'Opening the capture devices and waiting for the WebRTC stream.';
    elements.previewState.innerHTML = '<i class="live-dot"></i> Starting preview';
  } else if (status.recording && !status.preview_available) {
    elements.previewCoverTitle.textContent = status.preview_transport_reachable
      ? 'Recording is starting…'
      : 'Preview transport unavailable';
    elements.previewCoverDetail.textContent = status.preview_transport_reachable
      ? 'The master capture is independent of this browser preview.'
      : 'The server-side master recording continues independently of MediaMTX and this browser.';
    elements.previewState.innerHTML = '<i class="live-dot"></i> Recording';
  } else if (status.preview_available) {
    elements.previewState.innerHTML = `<i class="live-dot"></i> ${status.recording ? 'Recording monitor' : 'Live monitor'}`;
  } else if (status.state === 'error') {
    elements.previewCoverTitle.textContent = 'Preview error';
    elements.previewCoverDetail.textContent = 'Check the message below, then retry when the capture device is available.';
    elements.previewState.innerHTML = '<i class="live-dot"></i> Preview unavailable';
  } else {
    elements.previewCoverTitle.textContent = status.state === 'stopping' ? 'Stopping…' : 'Preview is idle';
    elements.previewCoverDetail.textContent = status.state === 'stopping'
      ? 'Releasing the capture devices.'
      : 'Start preview when you are ready to check the tape signal.';
    elements.previewState.innerHTML = '<i class="live-dot"></i> Preview stopped';
  }
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

async function startPreview() {
  showMessage('');
  elements.startPreview.disabled = true;
  try {
    await request('/api/preview/start', { method: 'POST' });
    await pollStatus();
  } catch (error) {
    showMessage(error.message);
    await pollStatus();
  }
}

async function stopPreview() {
  showMessage('');
  elements.stopPreview.disabled = true;
  try {
    await request('/api/preview/stop', { method: 'POST' });
    unloadPreview();
    await pollStatus();
  } catch (error) {
    showMessage(error.message);
    await pollStatus();
  }
}

async function previewHeartbeat() {
  if (!currentStatus?.preview_available || document.hidden) return;
  try {
    await request('/api/preview/heartbeat', { method: 'POST' });
  } catch (_) { /* Status polling reports connectivity failures. */ }
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
    date.textContent += item.recovered ? ' · Recovered copy exists' : ' · Interrupted / recoverable';
    date.className = 'recovery-badge';
  }
  title.append(strong, date);

  const meta = document.createElement('div');
  meta.className = 'recording-meta';
  const qcLabels = { verified: 'Verified', needs_review: 'Needs review' };
  const qc = item.qc_status ? ` · ${qcLabels[item.qc_status] || item.qc_status}` : '';
  meta.textContent = `${duration(item.duration_seconds)} · ${bytes(item.size_bytes)}${qc}`;

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
elements.startPreview.addEventListener('click', startPreview);
elements.stopPreview.addEventListener('click', stopPreview);
elements.stopDialog.addEventListener('close', () => {
  if (elements.stopDialog.returnValue === 'confirm') stopRecording();
});
document.querySelector('#refreshRecordings').addEventListener('click', loadRecordings);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) previewHeartbeat();
});

loadConfiguration().catch(error => showMessage(`Configuration unavailable: ${error.message}`));
loadDevices();
pollStatus();
loadRecordings();
setInterval(pollStatus, 1000);
setInterval(loadRecordings, 15000);
setInterval(previewHeartbeat, 15000);
