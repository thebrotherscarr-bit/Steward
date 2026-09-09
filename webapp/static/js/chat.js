// ATLAS Chat — sessions with receipts. No prompt() anywhere: every input
// is a form field. Live tokens ride WS when the socket is up, SSE when it
// is not, whole answers when neither speaks. History parses the chat_list
// text our own tools render; unparsable history shows raw, never lost.
const Chat = {
  session: null,
  sessions: [],
  ws: null,
  streaming: false,
  fallbackTimer: null,

  parseSessionId(text) {
    const m = /c-\d{8}-\d{6}-[0-9a-f]{8}/.exec(text || '');
    return m ? m[0] : null;
  },

  parseTurns(text) {
    const turns = [];
    let cur = null;
    for (const line of (text || '').split('\n')) {
      let m = /^n=(\d+) (\S+) · (\S+) · receipt ([0-9a-f]+)/.exec(line);
      if (m) { cur = { n: +m[1], voice: m[2], ts: m[3], receipt: m[4], q: '', a: '' }; turns.push(cur); continue; }
      m = /^  Q: (.*)/.exec(line);
      if (m && cur) { cur.q = m[1]; continue; }
      m = /^  A: (.*)/.exec(line);
      if (m && cur) { cur.a = m[1]; continue; }
      if (cur && /^\[flags:/.test(line)) { cur.flags = line; continue; }
      if (cur && line.startsWith('  ') && cur.a) { cur.a += '\n' + line.slice(2); }
    }
    return turns;
  },

  receiptOf(text) {
    const m = /receipt ([0-9a-f]{64})/.exec(text || '');
    return m ? m[1] : '';
  },

  ensureSocket(onToken) {
    if (this.ws) return this.ws;
    this.ws = API.wsChat({
      onFrame: (f) => {
        if (f.type === 'chat.token' && f.session === this.session) onToken(f.data && f.data.token || '');
        if (f.type === 'chat.done' && f.session === this.session) Chat.finishStream(f.data && f.data.text || '');
        if (f.type === 'chat.error') { Chat.streaming = false; toast('Chat refused: ' + ((f.data && f.data.error) || 'unknown'), 'error'); }
        if (f.type === 'chat_done') toast('Turn witnessed');
      }
    });
    return this.ws;
  },

  // THE CHAT REACHES THE COUNCIL BY DEFAULT. `chat_send` reaches ONE MODEL;
  // the council reaches the estate -- the sealed law gate before any model
  // reads a word, the one Router executing tools, the dedup, the recompose
  // that puts every failure in the delivery. Aligning this page on the engine
  // is what makes it a control plane rather than a chat box in front of a
  // model. The voice path stays one click away and is unchanged: it is still
  // the right tool for a quick question at a single seat.
  mode: 'council',

  async render(el) {
    this.el = el;
    if (this.mode === 'council') return Council.renderInto(el, () => this.setMode('voice'));
    el.innerHTML = `
      <div class="page-header"><div><div class="page-title">Chat</div>
      <div class="page-subtitle">One voice, witnessed — a single seat, receipts kept</div></div>
      <div class="flex">
        <button class="btn btn-sm" id="chat-mode">Council</button>
        <button class="btn btn-sm" id="chat-new">New session</button></div></div>
      <div class="grid-2">
        <div class="card"><div class="card-title">Sessions</div><div id="chat-sessions"><div class="loading">Loading...</div></div></div>
        <div class="card"><div class="card-title">Conversation</div>
          <div id="chat-log" class="chat-log"></div>
          <form id="chat-form" class="chat-form">
            <input id="chat-input" class="input" type="text" placeholder="Ask a lawful local voice..." autocomplete="off" />
            <button class="btn" type="submit" id="chat-send">Send</button>
            <button class="btn btn-sm" type="button" id="chat-cancel">Cancel</button>
          </form>
          <div id="chat-status" class="muted"></div>
        </div>
      </div>`;
    document.getElementById('chat-mode').onclick = () => this.setMode('council');
    document.getElementById('chat-new').onclick = () => this.openSession();
    document.getElementById('chat-form').onsubmit = (e) => { e.preventDefault(); this.ask(); };
    document.getElementById('chat-cancel').onclick = () => this.cancel();
    await this.refreshSessions();
    this.ensureSocket((tok) => this.appendToken(tok));
  },

  setMode(m) {
    this.mode = m;
    this.render(this.el || document.getElementById('page'));
  },

  async refreshSessions() {
    const box = document.getElementById('chat-sessions');
    try {
      const r = await API.listSessions();
      const ids = [];
      for (const line of (r.sessions || '').split('\n')) {
        const id = this.parseSessionId(line);
        if (id) ids.push({ id, line: line.trim() });
      }
      this.sessions = ids;
      box.innerHTML = ids.length ? ids.map(s =>
        `<div class="chat-session${s.id === this.session ? ' active' : ''}" data-s="${s.id}">${escHtml(s.line)}</div>`
      ).join('') : '<div class="empty-text">No sessions yet. Open one to begin.</div>';
      box.querySelectorAll('.chat-session').forEach(d => {
        d.onclick = () => { this.session = d.dataset.s; this.refreshSessions(); this.history(); };
      });
    } catch { box.innerHTML = '<div class="empty-text">MCP unreachable.</div>'; }
  },

  async openSession() {
    try {
      const r = await API.startSession('', '');
      this.session = this.parseSessionId(r.text);
      await this.refreshSessions();
      document.getElementById('chat-log').innerHTML = '';
      this.status('Session ' + this.session);
    } catch (e) { toast('Could not open session', 'error'); }
  },

  async history() {
    const log = document.getElementById('chat-log');
    log.innerHTML = '<div class="loading">Loading...</div>';
    try {
      const r = await API.getSession(this.session);
      const turns = this.parseTurns(r.turns);
      log.innerHTML = turns.length ? turns.map(t => this.bubble(t.q, t.a, t)).join('')
        : `<pre>${escHtml(r.turns || '')}</pre>`;
      log.scrollTop = log.scrollHeight;
    } catch { log.innerHTML = '<div class="empty-text">Could not load history.</div>'; }
  },

  bubble(q, a, t) {
    return `<div class="chat-q">${escHtml(q)}</div>
      <div class="chat-a">${escHtml(a)}
      ${t ? `<div><button class="btn btn-sm" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">Details</button>
      <pre style="display:none">n=${t.n} · ${escHtml(t.voice)} · ${escHtml(t.ts)}\nreceipt ${t.receipt}${t.flags ? '\n' + escHtml(t.flags) : ''}</pre></div>` : ''}</div>`;
  },

  appendToken(tok) {
    clearTimeout(this.fallbackTimer);      // the socket spoke; no fallback
    let live = document.getElementById('chat-live');
    if (!live) {
      const log = document.getElementById('chat-log');
      live = document.createElement('div');
      live.id = 'chat-live';
      live.className = 'chat-a live';
      log.appendChild(live);
    }
    live.textContent += tok;
    live.parentElement.scrollTop = live.parentElement.scrollHeight;
  },

  finishStream(text) {
    clearTimeout(this.fallbackTimer);
    const live = document.getElementById('chat-live');
    const receipt = this.receiptOf(text);
    if (live) {
      live.removeAttribute('id');
      live.classList.remove('live');
      const d = document.createElement('div');
      d.innerHTML = `<button class="btn btn-sm" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">Details</button><pre style="display:none">receipt ${receipt}</pre>`;
      live.appendChild(d);
    }
    this.streaming = false;
    this.status(receipt ? 'Witnessed · receipt ' + receipt.slice(0, 16) : 'Done');
    // The list said "no turns yet" beside a turn that had just been witnessed.
    this.refreshSessions();
  },

  status(s) { document.getElementById('chat-status').textContent = s; },

  async ask() {
    const input = document.getElementById('chat-input');
    const q = input.value.trim();
    if (!q || this.streaming) return;
    if (!this.session) await this.openSession();
    if (!this.session) return;
    input.value = '';
    const log = document.getElementById('chat-log');
    const qd = document.createElement('div');
    qd.className = 'chat-q';
    qd.textContent = q;
    log.appendChild(qd);
    this.streaming = true;
    this.status('Asking...');
    const sock = this.ensureSocket((tok) => this.appendToken(tok));
    if (sock.live()) {
      sock.send({ type: 'chat.send', session: this.session, question: q });
      // THE FALLBACK GUARDS THE SOCKET, NOT THE MODEL'S PACE. At 8s with no
      // cancel it raced a cold local voice and lost: one question, two turns,
      // two model calls, BOTH WITNESSED to the ledger (seen 2026-09-09,
      // session c-20260909-165951). A duplicated turn is a lie in a record
      // whose whole claim is that it is the truth. So: the timer is held and
      // cancelled the instant anything arrives, and its window is long enough
      // that only a dead socket reaches it.
      clearTimeout(this.fallbackTimer);
      this.fallbackTimer = setTimeout(() => {
        if (this.streaming) this.wholeFallback(q);
      }, 45000);
      return;
    }
    API.chatStream(this.session, q, '', '',
      (tok) => this.appendToken(tok),
      (text) => this.finishStream(text),
      (err) => { this.streaming = false; this.status('Refused: ' + err); toast('Chat refused', 'error'); });
  },

  async wholeFallback(q) {
    if (!this.streaming || document.getElementById('chat-live')) return;
    try {
      const r = await API.sendChat(this.session, q, '', '');
      const live = document.getElementById('chat-live');
      if (live) live.remove();
      const log = document.getElementById('chat-log');
      const d = document.createElement('div');
      d.innerHTML = this.bubble(q, (r.text || '').split('\n').slice(1).join('\n'), null);
      log.appendChild(d);
      this.streaming = false;
      this.status('Witnessed');
    } catch { this.streaming = false; }
  },

  async cancel() {
    clearTimeout(this.fallbackTimer);
    if (!this.session) return;
    try { await API.callTool('chat_cancel', { session: this.session }); } catch {}
    this.streaming = false;
    const live = document.getElementById('chat-live');
    if (live) live.remove();
    this.status('Cancelled — no partial answer is kept');
  }
};
