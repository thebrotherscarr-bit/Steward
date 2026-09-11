// ATLAS API Client
const API = {
  base: '/api',

  async get(path) {
    const r = await fetch(this.base + path);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  async post(path, body) {
    const r = await fetch(this.base + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  health()        { return this.get('/health'); },
  listAgents()    { return this.get('/agents'); },
  getAgent(id)    { return this.get('/agents/' + id); },
  listTraces(a)   { return this.get('/traces' + (a ? '?agent=' + a : '')); },
  getTrace(id)    { return this.get('/traces/' + id); },
  listEvals(t)    { return this.get('/evals' + (t ? '?trace=' + t : '')); },
  search(q)       { return this.get('/search?q=' + encodeURIComponent(q)); },
  listMessages(c) { return this.get('/messages' + (c ? '?channel=' + c : '')); },
  tools()         { return this.get('/tools'); },

  addTrace(t)       { return this.post('/traces', t); },
  addEval(e)        { return this.post('/evals', e); },
  callTool(t, a)    { return this.post('/tools/call', { tool: t, args: a }); },
  sendMessage(m)    { return this.post('/messages/send', m); },
  upsertAgent(a)    { return this.post('/agents', a); },
  setSetting(k, v)  { return this.post('/settings/' + k, { value: v }); },
  // Read side of the same store. THE SERVER IS THE ONLY PLACE TWO
  // BROWSERS CAN AGREE: sessionStorage is per-tab and localStorage is per
  // browser, so neither can put his Chromium and another browser on the
  // same page. Anything both must see lives here.
  getSetting(k)     { return this.get('/settings/' + k); },
  listSessions() { return this.get('/chat/sessions'); },
  getSession(s)  { return this.get('/chat/session?session=' + encodeURIComponent(s)); },
  startSession(actor, voice) { return this.post('/chat/start', { actor: actor || '', voice: voice || '' }); },
  sendChat(s, q, actor, voice) { return this.post('/chat/send', { session: s, question: q, actor: actor || '', voice: voice || '' }); },
  listPrompts() { return this.get('/prompts'); },
  getPrompt(n, v) { return this.get('/prompts/get?name=' + encodeURIComponent(n) + '&version=' + (v || 0)); },
  savePrompt(n, b, d) { return this.post('/prompts/save', { name: n, body: b, description: d || '' }); },
  runPrompt(n, vars, v, voice) { return this.post('/prompts/run', { name: n, vars: vars, version: v || 0, voice: voice || '' }); },
  comparePrompts(n, a, b, vars, voice) { return this.post('/prompts/compare', { name: n, vera: a, verb: b, vars: vars, voice: voice || '' }); },
  evalPrompt(n, d, v, voice) { return this.post('/prompts/eval', { name: n, dataset: d, version: v || 0, voice: voice || '' }); },
  seatAsk(q, s, voice, method) { return this.post('/seat/ask', { question: q, seat: s || '', voice: voice || '', method: method || '' }); },
  listFlows() { return this.get('/flows'); },
  getFlow(n, v) { return this.get('/flows/get?name=' + encodeURIComponent(n) + '&version=' + (v || 0)); },
  saveFlow(n, spec) { return this.post('/flows/save', { name: n, spec: spec }); },
  fireFlow(n, inputs) { return this.post('/flows/run', { name: n, inputs: inputs || '{}' }); },
  resumeFlow(run, d) { return this.post('/flows/resume', { run: run, decision: d }); },
  flowStatus(run) { return this.get('/flows/status?run=' + encodeURIComponent(run)); },
  compareFlows(a, b) { return this.post('/flows/compare', { runa: a, runb: b }); },
  replayFlow(run) { return this.post('/flows/replay', { run: run }); },
  listRuns(f) { return this.get('/flows/runs?flow=' + encodeURIComponent(f || '')); },
  townBeat() { return this.post('/town/beat', {}); },
  townStatus() { return this.get('/town/status'); },
  teamSend(p, c, content) { return this.post('/team/send', { platform: p, channel: c, content: content }); },
  teamHistory(c, p, last) { return this.get('/team/history?channel=' + encodeURIComponent(c || '') + '&platform=' + encodeURIComponent(p || '') + '&last=' + (last || 100)); },
  teamStatus() { return this.get('/team/status'); },

  chatStream(s, q, voice, actor, onToken, onDone, onErr) {
    const url = this.base + '/chat/stream?session=' + encodeURIComponent(s)
      + '&question=' + encodeURIComponent(q)
      + '&voice=' + encodeURIComponent(voice || '')
      + '&actor=' + encodeURIComponent(actor || '');
    const es = new EventSource(url);
    es.addEventListener('token', (e) => { try { onToken(JSON.parse(e.data).token); } catch {} });
    es.addEventListener('done', (e) => { es.close(); try { onDone(JSON.parse(e.data).text); } catch { onDone(''); } });
    es.addEventListener('refused', (e) => { es.close(); try { onErr(JSON.parse(e.data).error); } catch { onErr('refused'); } });
    es.onerror = () => { es.close(); onErr('stream broke'); };
    return es;
  },

  wsChat(handlers) {
    let ws;
    const connect = () => {
      try { if (ws) ws.close(); } catch {}
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      ws = new WebSocket(proto + '//' + location.host + '/ws');
      ws.onmessage = (e) => {
        try { handlers.onFrame(JSON.parse(e.data)); } catch {}
      };
      ws.onclose = () => { setTimeout(connect, 3000); };
      ws.onerror = () => { try { ws.close(); } catch {} };
    };
    connect();
    return {
      send(obj) { try { ws.send(JSON.stringify(obj)); } catch {} },
      live() { return ws && ws.readyState === 1; }
    };
  },

  sse(onEvent) {
    let es;
    const connect = () => {
      if (es) es.close();
      es = new EventSource(this.base + '/events');
      es.onmessage = (e) => {
        try { onEvent(JSON.parse(e.data)); } catch {}
      };
      es.onerror = () => { setTimeout(connect, 3000); };
    };
    connect();
    return es;
  }
};

function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast ' + type + ' show';
  setTimeout(() => el.className = 'toast', 3000);
}

// Epoch SECONDS -- what the suites and the standup stamp -- into something a
// human reads. Milliseconds are accepted too, because timeAgo below takes
// those, and mixing the two silently would date a live run to 1970.
function when(at) {
  if (at == null) return 'unknown';
  const n = Number(at);
  if (!isFinite(n)) return String(at);
  const d = new Date(n > 1e12 ? n : n * 1000);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric',
                                       hour: '2-digit', minute: '2-digit' });
}

function timeAgo(d) {
  const s = Math.floor((Date.now() - new Date(d)) / 1000);
  if (s < 60) return s + 's ago';
  if (s < 3600) return Math.floor(s/60) + 'm ago';
  if (s < 86400) return Math.floor(s/3600) + 'h ago';
  return Math.floor(s/86400) + 'd ago';
}

// THE QUOTES MUST GO TOO, and for months they did not.
//
// textContent -> innerHTML escapes & < > and NOTHING ELSE -- a double quote
// comes back through untouched. That is fine in a text position and WRONG in
// an attribute, and this file's callers build 17 attributes with it. Measured
// 2026-09-10: a Recent row for the objective
//     git commit: "a test of the recent card"
// rendered as data-say="git commit: " -- the attribute ended at the operator's
// own quote and the rest of his sentence became stray markup. Clicking it
// refilled the box with half a command.
//
// Escaped here rather than at seventeen call sites, because a rule that has to
// be remembered at every use is a rule that gets forgotten at the eighteenth.
// &quot; and &#39; render as " and ' in a text position too, so the 209 uses
// that are NOT attributes are unaffected.
function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
