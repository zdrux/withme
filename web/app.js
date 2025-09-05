const state = {
  token: localStorage.getItem('token') || 'dev',
  nextBefore: null,
  loading: false,
  poll: null,
};

const el = (id) => document.getElementById(id);

function setToken(t) {
  state.token = t;
  localStorage.setItem('token', t);
}

function authHeaders() {
  return { Authorization: 'Bearer ' + (state.token || 'dev') };
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function renderAgentHeader(agent, s) {
  const parts = [];
  if (agent?.name) parts.push(agent.name);
  if (s) parts.push(`mood ${s.mood >= 0 ? '+' : ''}${s.mood}`);
  if (s?.availability) parts.push(s.availability);
  el('agentHeader').textContent = parts.join(' · ');
}

function renderMessages(items, { prepend = false } = {}) {
  const history = el('history');
  const scroller = document.querySelector('.chat');
  const prevBottom = scroller.scrollHeight - scroller.scrollTop;
  const frag = document.createDocumentFragment();
  for (const m of items) {
    const wrap = document.createElement('div');
    wrap.className = 'bubble ' + (m.role === 'user' ? 'user' : 'agent');
    const meta = document.createElement('div');
    meta.className = 'meta';
    const when = new Date(m.created_at || Date.now());
    meta.textContent = `${m.role} • ${when.toLocaleString()}`;
    wrap.appendChild(meta);
    if (m.image_url) {
      const img = document.createElement('img');
      img.src = m.image_url;
      img.className = 'image';
      img.alt = 'image';
      wrap.appendChild(img);
    }
    if (m.text) {
      const p = document.createElement('div');
      p.textContent = m.text;
      wrap.appendChild(p);
    }
    frag.appendChild(wrap);
  }
  if (prepend) {
    history.prepend(frag);
    // preserve viewport after prepending
    scroller.scrollTop = scroller.scrollHeight - prevBottom;
  } else {
    history.appendChild(frag);
    // scroll to bottom for new messages
    scroller.scrollTop = scroller.scrollHeight;
  }
}

async function loadInitial() {
  try {
    el('token').value = state.token;
    const [agent, s, page] = await Promise.all([
      api('/agent'),
      api('/state'),
      api('/messages'),
    ]);
    renderAgentHeader(agent, s);
    const items = (page.items || []).slice().sort((a,b) => new Date(a.created_at) - new Date(b.created_at));
    renderMessages(items);
    state.nextBefore = page.next_before;
  } catch (e) {
    console.error(e);
  }
}

async function loadMore() {
  if (!state.nextBefore || state.loading) return;
  state.loading = true;
  try {
    const page = await api(`/messages?before=${encodeURIComponent(state.nextBefore)}`);
    if (page.items?.length) {
      const items = page.items.slice().sort((a,b) => new Date(a.created_at) - new Date(b.created_at));
      renderMessages(items, { prepend: true });
      state.nextBefore = page.next_before;
    } else {
      state.nextBefore = null;
    }
  } finally { state.loading = false; }
}

async function sendMessage() {
  const text = el('message').value.trim();
  if (!text) return;
  el('message').value = '';
  try {
    await api('/chat/send', { method: 'POST', body: { text } });
    // Poll messages briefly to catch the reply
    await refreshRecent();
    if (state.poll) clearInterval(state.poll);
    state.poll = setInterval(refreshRecent, 1500);
    setTimeout(() => state.poll && clearInterval(state.poll), 10000);
  } catch (e) {
    console.error(e);
  }
}

async function refreshRecent() {
  try {
    const page = await api('/messages?limit=10');
    // Replace tail then scroll to bottom
    const history = el('history');
    history.innerHTML = '';
    const items = (page.items || []).slice().sort((a,b) => new Date(a.created_at) - new Date(b.created_at));
    renderMessages(items);
  } catch {}
}

async function requestImage() {
  const prompt = el('imgPrompt').value.trim();
  if (!prompt) return;
  el('imgPrompt').value = '';
  try {
    await api('/chat/request_image', { method: 'POST', body: { prompt } });
    // Poll for the image message
    if (state.poll) clearInterval(state.poll);
    state.poll = setInterval(refreshRecent, 2000);
    setTimeout(() => state.poll && clearInterval(state.poll), 20000);
  } catch (e) { console.error(e); }
}

// Wire events
window.addEventListener('DOMContentLoaded', () => {
  el('saveToken').onclick = () => setToken(el('token').value.trim());
  el('send').onclick = sendMessage;
  el('message').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  el('requestImg').onclick = requestImage;
  el('loadMore').onclick = loadMore;
  loadInitial();
});
