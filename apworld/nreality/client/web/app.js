// Game page: shows the setup panel or the game, the status line and the console. Polls /api/state every second.
const $ = id => document.getElementById(id);

const page = {
  gameSession: null,       // session the game was loaded with; a different one reloads the page
  filesWereReady: null,    // false until the player's build exists, then the page reloads once
  shownPanel: null,        // which setup panel is on screen, so it is only rebuilt when that changes
  uploading: false,
  uploadError: '',
  lastLogId: 0,
  fetchingLog: false,
  inputHistory: [],
  historyPosition: 0,
};

// ---- Game ----

function loadGame(session) {
  page.gameSession = session;
  const player = window.RufflePlayer.newest().createPlayer();
  $('game').replaceChildren(player);
  // The session reaches the game as FlashVar _root.mwSession. The game always scales to fit the player element.
  player.ruffle().load({
    url: '/game.swf', autoplay: 'on', unmuteOverlay: 'hidden', allowScriptAccess: false, openUrlMode: 'deny',
    scale: 'showAll', forceScale: true, parameters: {mwSession: session},
  });
}

// Shown instead of the game: the setup until the player's NReality build exists, then "not connected".
function renderSetupPanel(files) {
  const busy = page.uploading || files.busy;
  const message = files.message || page.uploadError;
  const panelKey = files.ready ? 'not connected' : `setup|${busy}|${message}`;
  if (panelKey === page.shownPanel) return;
  page.shownPanel = panelKey;
  const panel = $('setup-panel');
  if (files.ready) {
    panel.innerHTML = '<p>Not connected · <code>/connect address</code></p>';
    return;
  }
  if (busy) {
    panel.innerHTML = '<p>Setting up …</p>';
    return;
  }
  panel.innerHTML =
    '<label class="file-button"><input type="file" id="archive" accept=".zip">Select NReality6g2.zip</label>'
    + '<p class="hint">Download: <a href="https://n.infunity.com/" target="_blank" rel="noopener">n.infunity.com</a></p>';
  if (message) {
    const error = document.createElement('p');
    error.className = 'error';
    error.textContent = message;
    panel.append(error);
  }
  $('archive').addEventListener('change', event => uploadArchive(event.target.files[0]));
}

async function uploadArchive(file) {
  if (!file) return;
  page.uploading = true;
  page.uploadError = '';
  renderSetupPanel({ready: false, busy: true, message: ''});
  try {
    const headers = {'Content-Type': 'application/zip'};
    const response = await fetch('/api/setup', {method: 'POST', headers, body: file});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
  } catch (error) {
    page.uploadError = error.message;
  }
  page.uploading = false;
  pollState();
}

// ---- Status line and input ----

function statusText(state) {
  const progress = `${state.checks.length}/${state.episodes.length * 5} Checks`;
  if (state.mode === 'local') return `Test mode · ${progress}`;
  if (!state.session) return '';
  const goal = !state.goal ? ''
    : state.goal.done ? 'Goal reached' : `Goal ${state.goal.completed}/${state.goal.required}`;
  return [state.server.connected ? state.server.slot : 'Disconnected', goal, progress].filter(Boolean).join(' · ');
}

function renderState(state) {
  const files = state.files;
  // Ruffle and the SWF only exist after the setup; reload once to pick them up.
  if (page.filesWereReady === false && files.ready) { location.reload(); return; }
  page.filesWereReady = files.ready;
  if (state.session && page.gameSession && state.session !== page.gameSession) { location.reload(); return; }
  if (files.ready && state.session && !page.gameSession && window.RufflePlayer) loadGame(state.session);
  if (!page.gameSession) renderSetupPanel(files);

  const local = state.mode === 'local';
  $('test-item-form').hidden = !local;
  document.documentElement.classList.toggle('test-mode', local);
  $('status').textContent = statusText(state);
  const input = $('command-input');
  input.disabled = $('command-send').disabled = local;
  input.placeholder = local ? 'MultiworldGG only'
    : state.inputRequested ? 'Input requested …' : 'Chat, !hint, /connect …';
  input.classList.toggle('requested', !!state.inputRequested);
  if (state.logId > page.lastLogId) fetchLogEntries();
}

// ---- Console ----

function logEntryElement(entry) {
  const row = document.createElement('div');
  row.className = `entry ${entry.kind}${entry.relevant ? '' : ' foreign'}`;
  const time = document.createElement('time');
  time.textContent = new Date(entry.time * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
  row.append(time);
  for (const part of entry.parts) {
    const span = document.createElement('span');
    span.textContent = part.text;
    if (part.color) span.style.color = part.color;
    row.append(span);
  }
  return row;
}

function showError(message) {
  const entry = {time: Date.now() / 1000, kind: 'error', relevant: true, parts: [{text: message}]};
  $('log').append(logEntryElement(entry));
}

async function fetchLogEntries() {
  if (page.fetchingLog) return;
  page.fetchingLog = true;
  try {
    const response = await fetch(`/api/log?after=${page.lastLogId}`);
    if (!response.ok) return;
    const {entries} = await response.json();
    const log = $('log');
    const scrolledToBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    for (const entry of entries) {
      log.append(logEntryElement(entry));
      page.lastLogId = Math.max(page.lastLogId, entry.id);
    }
    while (log.childElementCount > 500) log.firstElementChild.remove();
    if (scrolledToBottom) log.scrollTop = log.scrollHeight;
  } finally {
    page.fetchingLog = false;
  }
}

// ---- Requests ----

async function postJson(url, data) {
  const headers = {'Content-Type': 'application/json'};
  const response = await fetch(url, {method: 'POST', headers, body: JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result;
}

async function pollState() {
  try {
    const response = await fetch('/api/state');
    if (!response.ok) throw new Error();
    renderState(await response.json());
  } catch {
    $('status').textContent = 'Client not reachable';
  }
}

// ---- Events ----

$('command-form').addEventListener('submit', async event => {
  event.preventDefault();
  const input = $('command-input');
  const text = input.value.trim();
  if (!text) return;
  const answeringPrompt = input.classList.contains('requested');
  try {
    await postJson('/api/command', {text});
    if (!answeringPrompt) page.inputHistory.push(text);  // prompts may be passwords
    page.historyPosition = page.inputHistory.length;
    input.value = '';
    pollState();
  } catch (error) {
    showError(error.message);
  }
});

$('command-input').addEventListener('keydown', event => {
  if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
  event.preventDefault();
  const step = event.key === 'ArrowUp' ? -1 : 1;
  page.historyPosition = Math.max(0, Math.min(page.inputHistory.length, page.historyPosition + step));
  $('command-input').value = page.inputHistory[page.historyPosition] ?? '';
});

$('show-others').addEventListener('change', event => $('log').classList.toggle('show-others', event.target.checked));

$('test-item-form').addEventListener('submit', async event => {
  event.preventDefault();
  const episode = Number($('test-episode').value);
  try {
    renderState(await postJson('/api/item', {episode, receipt: `local-episode-${episode}`}));
  } catch (error) {
    $('status').textContent = error.message;
  }
});

pollState();
setInterval(pollState, 1000);
