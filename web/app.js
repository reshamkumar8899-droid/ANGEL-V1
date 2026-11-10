/* =============================================
   A.N.G.E.L — Variant I  |  Frontend Logic
   WebSocket-based communication
   ============================================= */

'use strict';

const WS_URL = 'ws://127.0.0.1:7772';
let socket = null;
let micActive = false;
let isWaiting = false;
let currentBackend = 'gemini';   // updated on config message

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
      currentBackend = msg.backend || 'gemini';
      if (msg.has_key) {
        hideSetup();
      } else if (currentBackend === 'gemini') {
        showSetup();   // only show Gemini key modal for Gemini backend
      } else {
        hideSetup();   // OpenAI backend — key comes from .env, no modal
      }
      // Show model picker for OpenAI-compatible backends
      if (currentBackend === 'openai') {
        const picker = document.getElementById('modelPicker');
        if (picker) picker.style.display = '';
        if (msg.current_model) setCurrentModelDisplay(msg.current_model);
        // Auto-fetch models on connect
        send({ type: 'fetch_models' });
      }
      break;
    case 'models':
      populateModelDropdown(msg.models || [], msg.current || '');
      break;
    case 'model_changed':
      setCurrentModelDisplay(msg.model);
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

// ── Chat overlay toggle ───────────────────────────────
function toggleChat() {
  const overlay = document.getElementById('chatOverlay');
  const btn     = document.getElementById('chatToggleBtn');
  const isOpen  = overlay.classList.toggle('open');
  btn.classList.toggle('active', isOpen);
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
  if (currentBackend === 'openai') {
    alert('Open the .env file in your Angel folder, set OPENAI_API_KEY and OPENAI_BASE_URL, then restart Angel.');
  } else {
    alert('Open the .env file in your Angel folder, set GEMINI_API_KEY=your_key, then restart Angel.');
  }
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
  const rp = document.getElementById('responsePanel');
  const el = document.getElementById('responseText');
  // Double-check: strip any raw HTML tags that aren't our safe formatting
  const safe = html.replace(/<(?!\/?(?:strong|br|em|b|i)\s*\/?>)[^>]+>/gi, '');
  el.innerHTML = safe;
  if (rp) rp.classList.add('visible');
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

// ── Model picker ──────────────────────────────────────────
function setCurrentModelDisplay(modelId) {
  const el = document.getElementById('currentModelName');
  if (el) {
    // Show a shorter display name (strip provider prefix like "openai/")
    const short = modelId.includes('/') ? modelId.split('/').pop() : modelId;
    el.textContent = short;
    el.title = modelId;
  }
}

function toggleModelPicker() {
  const dropdown = document.getElementById('modelDropdown');
  if (dropdown) dropdown.classList.toggle('open');
}

function refreshModels() {
  const list = document.getElementById('modelList');
  if (list) list.innerHTML = '<div class="model-loading">Loading models...</div>';
  send({ type: 'fetch_models' });
}

function populateModelDropdown(models, currentModel) {
  const list = document.getElementById('modelList');
  if (!list) return;
  if (models.length === 0) {
    list.innerHTML = '<div class="model-loading">No models available</div>';
    return;
  }
  list.innerHTML = '';
  // Group by owned_by (provider)
  const groups = {};
  models.forEach(m => {
    const provider = m.owned_by || 'other';
    if (!groups[provider]) groups[provider] = [];
    groups[provider].push(m);
  });
  Object.keys(groups).sort().forEach(provider => {
    const header = document.createElement('div');
    header.className = 'model-group-header';
    header.textContent = provider.toUpperCase();
    list.appendChild(header);
    groups[provider].forEach(m => {
      const item = document.createElement('div');
      item.className = 'model-item' + (m.id === currentModel ? ' active' : '');
      item.textContent = m.id;
      item.title = m.id;
      item.onclick = () => selectModel(m.id);
      list.appendChild(item);
    });
  });
  setCurrentModelDisplay(currentModel);
}

function selectModel(modelId) {
  send({ type: 'switch_model', model: modelId });
  // Close dropdown
  const dropdown = document.getElementById('modelDropdown');
  if (dropdown) dropdown.classList.remove('open');
  // Immediately update display
  setCurrentModelDisplay(modelId);
  // Mark the selected item
  document.querySelectorAll('.model-item').forEach(el => {
    el.classList.toggle('active', el.textContent === modelId);
  });
}

// Close model dropdown when clicking outside
document.addEventListener('click', (e) => {
  const picker = document.getElementById('modelPicker');
  const dropdown = document.getElementById('modelDropdown');
  if (picker && dropdown && !picker.contains(e.target)) {
    dropdown.classList.remove('open');
  }
});

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
const isOverlayMode = new URLSearchParams(window.location.search).has('overlay');

window.addEventListener('load', () => {
  setState('CONNECTING');
  connect();

  // Activate overlay mode if launched via Electron overlay
  if (isOverlayMode) {
    document.body.classList.add('overlay-mode');
    initOverlayClickThrough();
  }
});

// ── Overlay mode: click-through on transparent areas ──────
function initOverlayClickThrough() {
  if (!window.angelOverlay) return;

  // Elements that should always be interactive (not click-through)
  const interactiveSelectors = [
    '.composer', '.chat-overlay.open', '.header-left',
    '.overlay-controls', '.setup-modal.visible'
  ];

  document.addEventListener('mousemove', (e) => {
    // Check if mouse is over any interactive element
    const isOverInteractive = interactiveSelectors.some(sel => {
      const el = document.querySelector(sel);
      if (!el) return false;
      const rect = el.getBoundingClientRect();
      return (
        e.clientX >= rect.left && e.clientX <= rect.right &&
        e.clientY >= rect.top && e.clientY <= rect.bottom
      );
    });

    // Check if mouse is over the 3D avatar (non-transparent pixel)
    const canvas = document.getElementById('vrm-canvas');
    if (canvas && !isOverInteractive) {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
      if (gl) {
        const pixel = new Uint8Array(4);
        const px = Math.floor(x * (canvas.width / rect.width));
        const py = canvas.height - Math.floor(y * (canvas.height / rect.height));
        gl.readPixels(px, py, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
        // If pixel has alpha > threshold, it's the avatar — make interactive
        if (pixel[3] > 10) {
          window.angelOverlay.setIgnoreMouse(false);
          return;
        }
      }
    }

    if (isOverInteractive) {
      window.angelOverlay.setIgnoreMouse(false);
    } else {
      window.angelOverlay.setIgnoreMouse(true);
    }
  });
}

// ── Overlay control buttons ───────────────────────────────
function minimizeOverlay() {
  if (window.angelOverlay) window.angelOverlay.minimize();
}
function closeOverlay() {
  if (window.angelOverlay) window.angelOverlay.close();
}

// ── Expose functions to HTML onclick handlers ─────────────
window.sendMessage      = sendMessage;
window.toggleMic        = toggleMic;
window.toggleChat       = toggleChat;
window.saveApiKey        = saveApiKey;
window.minimizeOverlay  = minimizeOverlay;
window.closeOverlay     = closeOverlay;
window.toggleModelPicker = toggleModelPicker;
window.refreshModels     = refreshModels;
window.selectModel       = selectModel;
