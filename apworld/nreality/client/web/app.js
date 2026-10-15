const $ = id => document.getElementById(id);
let loadedSession, filesReady, panelKey, uploadError = '', lastLog = 0, loadingLog = false, uploading = false;
const inputHistory = [];
let historyPos = 0;

function loadGame(session) {
  loadedSession = session;
  const player = window.RufflePlayer.newest().createPlayer();
  $('game').replaceChildren(player);
  // The session reaches the SWF as FlashVar _root.mwSession.
  player.ruffle().load({url:'/game.swf',autoplay:'on',unmuteOverlay:'hidden',allowScriptAccess:false,openUrlMode:'deny',parameters:{mwSession:session}});
}

// Panel shown instead of the game: setup until the player's NReality build exists, then "not connected".
function showPanel(files) {
  const busy = uploading || files.busy, message = files.message || uploadError;
  const key = files.ready ? 'waiting' : `setup|${busy}|${message}`;
  if (key === panelKey) return;
  panelKey = key;
  const panel = $('panel');
  if (files.ready) { panel.innerHTML = '<p>Nicht verbunden · <code>/connect adresse</code></p>'; return; }
  if (busy) { panel.innerHTML = '<p>Wird eingerichtet …</p>'; return; }
  panel.innerHTML = '<label class="file"><input type="file" id="archive" accept=".zip">NReality6g2.zip auswählen</label>'
    + '<p class="dim">Download: <a href="https://n.infunity.com/" target="_blank" rel="noopener">n.infunity.com</a></p>';
  if (message) {
    const error = document.createElement('p');
    error.className = 'error'; error.textContent = message;
    panel.append(error);
  }
  $('archive').addEventListener('change', event => upload(event.target.files[0]));
}

async function upload(file) {
  if (!file) return;
  uploading = true; uploadError = '';
  showPanel({ready: false, busy: true, message: ''});
  try {
    const response = await fetch('/api/setup', {method: 'POST', headers: {'Content-Type': 'application/zip'}, body: file});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
  } catch (error) { uploadError = error.message; }
  uploading = false;
  refresh();
}

function render(state) {
  const files = state.files;
  // Ruffle and the SWF only exist after the setup; reload once to pick them up.
  if (filesReady === false && files.ready) { location.reload(); return; }
  filesReady = files.ready;
  if (state.session && loadedSession && state.session !== loadedSession) { location.reload(); return; }
  if (files.ready && state.session && !loadedSession && window.RufflePlayer) loadGame(state.session);
  if (!loadedSession) showPanel(files);
  const local = state.mode === 'local';
  $('local').hidden = !local;
  const progress = `${state.checks.length}/${state.episodes.length * 5} Checks`;
  const goal = state.goal ? (state.goal.done ? 'Ziel erreicht' : `Ziel ${state.goal.completed}/${state.goal.required}`) : '';
  $('status').textContent = local ? `Testmodus · ${progress}`
    : !state.session ? '' : [state.server.connected ? state.server.slot : 'Server getrennt', goal, progress].join(' · ');
  const input = $('input');
  input.disabled = $('command').querySelector('button').disabled = local;
  input.placeholder = local ? 'Nur mit MultiworldGG' : state.inputRequested ? 'Eingabe angefordert …' : 'Chat, !hint, /connect …';
  input.classList.toggle('requested', !!state.inputRequested);
  if (state.logId > lastLog) loadLog();
}

function entryElement(entry) {
  const div = document.createElement('div');
  div.className = `entry ${entry.kind}${entry.relevant ? '' : ' foreign'}`;
  const time = document.createElement('time');
  time.textContent = new Date(entry.time * 1000).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
  div.append(time);
  for (const part of entry.parts) {
    const span = document.createElement('span');
    span.textContent = part.text;
    if (part.color) span.style.color = part.color;
    div.append(span);
  }
  return div;
}

async function loadLog() {
  if (loadingLog) return;
  loadingLog = true;
  try {
    const response = await fetch(`/api/log?after=${lastLog}`);
    if (!response.ok) return;
    const {entries} = await response.json();
    const log = $('log');
    const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    for (const entry of entries) { log.append(entryElement(entry)); lastLog = Math.max(lastLog, entry.id); }
    while (log.childElementCount > 500) log.firstElementChild.remove();
    if (atBottom) log.scrollTop = log.scrollHeight;
  } finally { loadingLog = false; }
}

async function post(url, data) {
  const response = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result = await response.json(); if (!response.ok) throw new Error(result.error);
  return result;
}

$('command').addEventListener('submit', async event => {
  event.preventDefault();
  const input = $('input'), text = input.value.trim();
  if (!text) return;
  const prompted = input.classList.contains('requested');
  try {
    await post('/api/command', {text});
    if (!prompted) inputHistory.push(text);  // prompts may be passwords
    historyPos = inputHistory.length;
    input.value = '';
    refresh();
  } catch (error) { $('log').append(entryElement({time: Date.now() / 1000, kind: 'error', relevant: true, parts: [{text: error.message}]})); }
});
$('input').addEventListener('keydown', event => {
  if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
  event.preventDefault();
  historyPos = Math.max(0, Math.min(inputHistory.length, historyPos + (event.key === 'ArrowUp' ? -1 : 1)));
  $('input').value = inputHistory[historyPos] ?? '';
});
$('others').addEventListener('change', event => $('log').classList.toggle('others', event.target.checked));
$('local').addEventListener('submit', async event => {
  event.preventDefault(); const value = Number($('item').value);
  try { render(await post('/api/item', {episode:value, receipt:`local-episode-${value}`})); } catch(error) { $('status').textContent = error.message; }
});
async function refresh() {
  try { const response = await fetch('/api/state'); if (!response.ok) throw new Error(); render(await response.json()); }
  catch { $('status').textContent = 'Client nicht erreichbar'; }
}
refresh();setInterval(refresh,1000);
