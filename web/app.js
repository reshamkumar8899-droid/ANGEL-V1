/* =============================================
   A.N.G.E.L — Variant I  |  Frontend Logic
   WebSocket-based communication
   ============================================= */

'use strict';

const WS_URL = 'ws://127.0.0.1:7772';
let socket = null;
let micActive = false;
let isWaiting = false;

// ── WebSocket ─────────────────────────────────────────────
function connect() {
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    console.log('[Angel] Connected');
    isWaiting = false;      // a dropped connection must not leave the input locked
    resetMic();
    setState('LISTENING');
    hideSetup();
  };

  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleEvent(msg);
    } catch (e) {
      console.error('[Angel] Bad message:', e);
    }
  };

  socket.onclose = () => {
    isWaiting = false;
    resetMic();
    setState('OFFLINE');
    setTimeout(connect, 2500);   // auto-reconnect
  };

  socket.onerror = () => {
    setState('OFFLINE');
  };
}

function send(obj) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(obj));
  }
}

// ── Event handler ─────────────────────────────────────────
function handleEvent(msg) {
  switch (msg.type) {
    case 'status':
      setState(msg.state);
      isWaiting = (msg.state === 'THINKING' || msg.state === 'SPEAKING');
      break;
    case 'message':
      addMessage(msg.role, formatText(msg.content));
      if (msg.role === 'assistant') setResponseText(formatText(msg.content));
      break;
    case 'voice_input':
      resetMic();           // mic session is over — without this the wake word only worked once
      document.getElementById('cmdInput').value = msg.text;
      setTranscript(msg.text);
      sendMessage();
      break;
    case 'transcript':
      setTranscript(msg.content || '');
      break;
    case 'mic_stopped':
      resetMic();
      clearTranscript();
      break;
    case 'config':
      if (msg.has_key) hideSetup(); else showSetup();
      break;
    case 'wake':
      handleWake();
      break;
    case 'reminder':
      handleReminder(msg.content);
      break;
    case 'pong':
      break;
  }
}

// Reset the mic button/state (backend finished listening, or the connection dropped)
function resetMic() {
  micActive = false;
  const btn = document.getElementById('micBtn');
  if (btn) btn.classList.remove('active');
}

// ── Wake word activation ───────────────────────────────
function handleWake() {
  if (isWaiting || micActive) return;
  setState('WAKING');
  setTranscript('Wake word detected — listening...');
  setTimeout(() => {
    if (!micActive) {
      micActive = true;
      const btn = document.getElementById('micBtn');
      if (btn) btn.classList.add('active');
      send({ type: 'mic_start' });
      setState('LISTENING');
    }
  }, 800);
}


// ── Reminder notification ─────────────────────────────
function handleReminder(content) {
  // Add to chat log as a special reminder card
  const log = document.getElementById('chatLog');
  const div = document.createElement('div');
  div.className = 'message assistant reminder-card';
  div.style.cssText = 'border: 1px solid #00ffcc; box-shadow: 0 0 12px #00ffcc55; animation: pulse-border 1s ease 3;';
  div.innerHTML = `<span class="msg-label" style="color:#00ffcc;">REMINDER</span><span class="msg-text">${escapeHtml(content)}</span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  setResponseText(escapeHtml(content));
  // Flash state
  setState('REMINDER');
  // Auto-reset state after 5s
  setTimeout(() => setState('LISTENING'), 5000);
  // Remove the glow after 8s (keep message in log)
  setTimeout(() => { div.style.border = ''; div.style.boxShadow = ''; }, 8000);
}


// ── State machine ─────────────────────────────────────────
const STATE_COLORS = {
  LISTENING:  '#00d4ff',
  THINKING:   '#f59e0b',
  SPEAKING:   '#10b981',
  SEARCHING:  '#a855f7',
  WAKING:     '#00ffcc',
  REMINDER:   '#00ffcc',
  MUTED:      '#6b7280',
  CONNECTING: '#8b5cf6',
  OFFLINE:    '#4b5563',
};

function setState(state) {
  const dot   = document.getElementById('stateDot');
  const label = document.getElementById('stateLabel');
  label.textContent = state;
  const color = STATE_COLORS[state] || '#00d4ff';
  dot.style.background = color;
  dot.style.boxShadow  = `0 0 8px ${color}`;
  // Tell 3D avatar engine the new state
  if (window.setAvatarState) window.setAvatarState(state);
}

// ── Send message ──────────────────────────────────────────
function sendMessage() {
  if (isWaiting) return;
  const input = document.getElementById('cmdInput');
  const text  = input.value.trim();
  if (!text) return;
  input.value = '';
  input.focus();
  clearTranscript();
  addMessage('user', escapeHtml(text));
  send({ type: 'message', content: text });
}

// ── Microphone ────────────────────────────────────────────
function toggleMic() {
  const btn = document.getElementById('micBtn');
  if (!micActive) {
    micActive = true;
    btn.classList.add('active');
    setTranscript('Listening...');
    send({ type: 'mic_start' });
  } else {
    micActive = false;
    btn.classList.remove('active');
    clearTranscript();
    send({ type: 'mic_stop' });
  }
}

// ── Setup modal ───────────────────────────────────────────
function showSetup() {
  document.getElementById('setupModal').classList.add('visible');
}
function hideSetup() {
  document.getElementById('setupModal').classList.remove('visible');
}
async function saveApiKey() {
  // The key lives in .env (never in the browser) — keeps it out of the page and out of reach of scripts.
  alert('Open the .env file in your Angel folder, set GEMINI_API_KEY=your_key, then restart Angel.');
}

// ── Chat log helpers ──────────────────────────────────────
function addMessage(role, html) {
  const log = document.getElementById('chatLog');
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.innerHTML = `<span class="msg-label">${role === 'assistant' ? 'ANGEL' : 'YOU'}</span><span class="msg-text">${html}</span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}
function setResponseText(html) {
  document.getElementById('responseText').innerHTML = html;
}
function setTranscript(text) {
  document.getElementById('transcript').textContent = text;
}
function clearTranscript() {
  document.getElementById('transcript').textContent = '';
}

// ── Text formatting ───────────────────────────────────────
function formatText(text) {
  return escapeHtml(text)
    .replace(/\bDaddy\b/g, '<strong>Daddy</strong>')
    .replace(/\n/g, '<br/>');
}
function escapeHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function flash(el) {
  el.style.borderColor='#ef4444'; el.style.boxShadow='0 0 0 2px rgba(239,68,68,.25)';
  setTimeout(()=>{ el.style.borderColor=''; el.style.boxShadow=''; }, 900);
}

// ── Keyboard ──────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
  const input = document.getElementById('cmdInput');
  if (e.key === 'Enter' && document.activeElement === input && !e.shiftKey) {
    e.preventDefault(); sendMessage();
  }
  if (e.key === '/' && document.activeElement !== input) {
    e.preventDefault(); input.focus();
  }
});

// ── Init ──────────────────────────────────────────────────
window.addEventListener('load', () => {
  setState('CONNECTING');
  connect();
});
