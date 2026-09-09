// ATLAS Council — the chat that reaches the ESTATE, not a voice.
//
// Chat (chat.js) sends a question to ONE MODEL: rack.Ask, one voice, one
// answer. This sends an OBJECTIVE to the whole council: it goes into the
// world's own Manjuel process, so the sealed law gate stamps it before any
// model reads a word, the one Router executes the tools, the dedup refuses an
// identical call, and the recompose puts every failure into the delivery.
//
// EVERYTHING ON THIS PAGE IS THE ENGINE'S OWN EVENT. Nothing is inferred from a
// seat's prose, nothing is summarised, nothing is invented while waiting. The
// per-seat facts under a delivery (elapsed, skipped, failures) are read off the
// engine's StepResults, never off what a seat said about itself (LAW 5).
//
// PROTOCOL 1's seventeen, verbatim from manjuel/serve.py:
//   opened text run report seat token tool tool_result needs_answer
//   delivery refused aborted cancelled unreachable error note closed
//
// They all arrive on ONE SSE frame (`event: engine`) with the kind inside, so
// an event this file has never heard of still lands and is shown verbatim.
// EventSource has no wildcard listener; naming frames per-kind would mean this
// page silently loses anything the core adds later, and on a surface whose
// whole claim is "this is what actually ran", a dropped event looks exactly
// like nothing having happened.
const Council = {
  es: null,
  running: false,
  engineOpen: false,
  seats: {},        // seat name -> the element its tokens stream into

  // ---- the page -----------------------------------------------------------

  // renderInto, not render: the council is not its own page. It is what
  // /chat opens on (RULE 5 -- the operator named the chat page; a second
  // page beside it was never asked for).
  async renderInto(el, toVoice) {
    // A LIVE STREAM MUST NOT SURVIVE THE PAGE THAT OWNED IT. Navigating away
    // mid-turn and back used to leave the old EventSource reading into a log
    // element that no longer exists, with `running` stuck true -- so the Run
    // button stayed disabled forever and the feed showed nothing. The turn
    // itself keeps going inside the engine, which is right: a closed glass
    // does not cancel the council's work. Only the reader is dropped.
    if (this.es) { try { this.es.close(); } catch {} }
    this.es = null;
    this.running = false;
    this.seats = {};
    el.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">Chat</div>
          <div class="page-subtitle">The whole estate — law gate, one Router, every tool, the recompose</div>
        </div>
        <div class="flex">
          <span id="council-engine" class="badge">checking...</span>
          <button class="btn btn-sm" id="council-voice" type="button">Voice</button>
          <button class="btn btn-sm" id="council-refresh" type="button">Refresh</button>
        </div>
      </div>
      <div class="card">
        <div class="card-title">Objective</div>
        <form id="council-form" class="chat-form">
          <input id="council-input" class="input" type="text" autocomplete="off"
                 placeholder="Set the objective and watch the council work..." />
          <button class="btn" type="submit" id="council-send">Run</button>
          <button class="btn btn-sm" type="button" id="council-cancel">Cancel</button>
        </form>
        <div id="council-status" class="muted" style="margin-top:8px"></div>
      </div>
      <div class="card">
        <div class="card-title">What is actually happening</div>
        <div id="council-log" class="chat-log council-log"></div>
      </div>`;
    document.getElementById('council-form').onsubmit = (e) => { e.preventDefault(); this.go(); };
    document.getElementById('council-cancel').onclick = () => this.cancel();
    document.getElementById('council-refresh').onclick = () => this.checkEngine();
    const v = document.getElementById('council-voice');
    if (v && toVoice) v.onclick = () => toVoice();
    // Enter sends. The form's implicit submit is not reliable in every
    // host, and a send box that ignores Enter reads as broken.
    document.getElementById('council-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.go(); }
    });
    await this.checkEngine();
  },

  // The send box is only honest if it says up front whether an engine is even
  // standing. A disabled button with a reason is the same information as a
  // failed turn, delivered before he spends one.
  async checkEngine() {
    const b = document.getElementById('council-engine');
    if (!b) return;
    try {
      const r = await fetch(API.base + '/council/state').then(x => x.json());
      this.engineOpen = !!r.open;
      if (r.open) {
        b.className = 'badge badge-green';
        b.textContent = 'engine open · sitting ' + (r.sitting || '?');
        this.status(r.pending ? 'The council is waiting on an answer.' : '');
        if (r.pending) this.askGate(r.pending);
      } else {
        b.className = 'badge badge-yellow';
        b.textContent = 'no engine';
        this.status('No engine is open on this world. The glass will not start one ' +
                    'behind your back — that opens a sitting you never opened, and the ' +
                    'sitting line is the lock. Open one with env_open.');
      }
    } catch {
      b.className = 'badge badge-red';
      b.textContent = 'door unreachable';
      this.engineOpen = false;
      this.status('The MCP door did not answer.');
    }
    const send = document.getElementById('council-send');
    if (send) send.disabled = !this.engineOpen;
  },

  status(s) {
    const el = document.getElementById('council-status');
    if (el) el.textContent = s;
  },

  log() { return document.getElementById('council-log'); },

  row(cls, html) {
    const log = this.log();
    if (!log) return document.createElement('div');
    const d = document.createElement('div');
    d.className = 'cev ' + cls;
    d.innerHTML = html;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  },

  // ---- firing -------------------------------------------------------------

  go() {
    const input = document.getElementById('council-input');
    const objective = input.value.trim();
    if (!objective || this.running) return;
    input.value = '';
    this.log().innerHTML = '';
    this.seats = {};
    this.row('cev-obj', escHtml(objective));
    this.start({ objective });
  },

  answer(text) {
    if (this.running) return;
    this.row('cev-obj', escHtml(text));
    this.start({ answer: text });
  },

  start(params) {
    this.running = true;
    this.status('Running...');
    const send = document.getElementById('council-send');
    if (send) send.disabled = true;
    const qs = new URLSearchParams(params).toString();
    const es = new EventSource(API.base + '/council/stream?' + qs);
    es.addEventListener('engine', (e) => {
      let d = {};
      try { d = JSON.parse(e.data); } catch { return; }
      this.on(d.event || 'unnamed', d);
    });
    es.addEventListener('stream_open', () => this.status('Engine reached.'));
    es.addEventListener('stream_end', (e) => {
      let d = {};
      try { d = JSON.parse(e.data); } catch {}
      if (d.dropped) this.row('cev-fail', `<b>${d.dropped} events were dropped</b> — this glass did not see everything that ran`);
      if (this.running) this.finish(d.waiting ? 'Waiting on you' : 'Done');
    });
    es.addEventListener('stream_error', (e) => {
      let d = {};
      try { d = JSON.parse(e.data); } catch {}
      this.row('cev-fail', `<b>REFUSED</b> ${escHtml(d.error || 'unknown')}`);
      this.finish('Refused');
    });
    es.onerror = () => {
      if (!this.running) return;
      this.finish('The stream broke — the turn may still be running inside the engine');
    };
    this.es = es;
  },

  finish(msg) {
    this.running = false;
    try { if (this.es) this.es.close(); } catch {}
    this.es = null;
    this.status(msg);
    const send = document.getElementById('council-send');
    if (send) send.disabled = !this.engineOpen;
  },

  async cancel() {
    if (!this.running) return;
    try { await API.callTool('run_cancel', {}); } catch {}
    this.finish('Cancelled — the turn was interrupted; the sitting stands');
  },

  // ---- the estate at work -------------------------------------------------

  // seatBox returns the element this seat's tokens stream into, making the row
  // if the tokens arrived before (or without) the seat event.
  seatBox(seat) {
    seat = seat || 'the council';
    if (!this.seats[seat]) {
      const r = this.row('cev-seat',
        `<b>${escHtml(seat)}</b> <span class="cev-mark cev-dots"></span><div class="cev-tok"></div>`);
      this.seats[seat] = r.querySelector('.cev-tok');
    }
    return this.seats[seat];
  },

  on(kind, d) {
    switch (kind) {
      // `text` is the console copy of everything below; showing it too would
      // print the whole turn twice. The structured events are the record.
      case 'text':
        return;

      case 'opened':
        this.row('cev-meta', `<b>opened</b> sitting ${escHtml(String(d.sitting ?? ''))} · session ${escHtml(d.session || '')}`);
        return;

      case 'run':
        this.row('cev-meta',
          `<b>run</b> pipeline <b>${escHtml(d.pipeline || '')}</b>` +
          (d.review_only ? ' · <span class="badge badge-yellow">review only</span>' : '') +
          (d.feed_chars ? ` · feed ${d.feed_chars} chars` : '') +
          (d.transcript ? `<br><span class="muted">transcript <code>${escHtml(d.transcript)}</code></span>` : ''));
        return;

      case 'report':
        this.row('cev-report', escHtml((d.text || '').trim()));
        return;

      case 'seat': {
        const seat = d.seat || 'seat';
        const r = this.row('cev-seat',
          `<b>${escHtml(seat)}</b> <span class="muted">${escHtml(d.model || '')}` +
          (d.timeout ? ` · timeout ${d.timeout}s` : '') + `</span> ` +
          `<span class="cev-mark cev-dots"></span><div class="cev-tok"></div>`);
        this.seats[seat] = r.querySelector('.cev-tok');
        return;
      }

      case 'token':
        // Tokens stream into the seat that is speaking, so it is visible WHICH
        // seat is producing which words.
        this.seatBox(d.seat).textContent += (d.text || '');
        this.log().scrollTop = this.log().scrollHeight;
        return;

      case 'tool':
        this.row('cev-tool', `<b>tool</b> ${escHtml(d.action || d.tool || d.name || '?')}` +
          (d.args ? ` <code>${escHtml(JSON.stringify(d.args)).slice(0, 200)}</code>` : ''));
        return;

      case 'tool_result':
        // `failed` is the ENGINE's own field — the pipeline's test, not a
        // reading of the words.
        this.row(d.failed ? 'cev-fail' : 'cev-ok',
          `<b>${d.failed ? 'FAILED' : 'ok'}</b> ${escHtml(d.action || d.tool || d.name || '?')}` +
          (d.error ? ` — ${escHtml(d.error)}` : '') +
          (d.text && d.failed ? ` — ${escHtml(String(d.text).slice(0, 300))}` : ''));
        return;

      case 'note':
        this.row('cev-note', `<b>note</b> ${escHtml(d.text || JSON.stringify(d))}`);
        return;

      case 'needs_answer':
        this.finish('The council is asking. Nothing is assumed on your behalf.');
        this.askGate(d.prompt || '');
        return;

      case 'delivery':
        this.delivery(d);
        this.finish('Delivered' + (d.elapsed != null ? ' · ' + d.elapsed + 's' : ''));
        return;

      case 'refused':
      case 'aborted':
      case 'cancelled':
      case 'unreachable':
      case 'error':
        this.row('cev-fail', `<b>${escHtml(kind.toUpperCase())}</b> ${escHtml(d.text || d.error || '')}`);
        // `error` is NOT terminal on this wire — serve.py emits it for a
        // malformed command and keeps going — so it does not end the turn.
        if (kind !== 'error') this.finish(kind);
        return;

      case 'closed':
        this.row('cev-meta', `<b>closed</b> ${escHtml(d.text || 'the sitting is tolled')}`);
        this.engineOpen = false;
        this.checkEngine();
        return;

      default:
        // An event this glass does not know is still something that happened.
        this.row('cev-other', `<b>${escHtml(kind)}</b> <code>${escHtml(JSON.stringify(d)).slice(0, 400)}</code>`);
    }
  },

  // The gate. A question from the council is answered by the operator in a form
  // field — never a prompt(), never a default, never a guess (RULE 6).
  askGate(prompt) {
    const d = this.row('cev-gate',
      `<b>THE COUNCIL IS ASKING</b><div class="cev-prompt">${escHtml(prompt)}</div>
       <form class="chat-form" style="margin-top:8px">
         <input class="input cev-answer" type="text" autocomplete="off"
                placeholder="Your answer — nothing is assumed on your behalf" />
         <button class="btn" type="submit">Answer</button>
       </form>`);
    const form = d.querySelector('form');
    form.onsubmit = (e) => {
      e.preventDefault();
      const v = form.querySelector('.cev-answer').value;
      if (!v.trim()) return;
      form.remove();
      this.answer(v);
    };
    const box = form.querySelector('.cev-answer');
    if (box) box.focus();
  },

  // The delivery, with what ACTUALLY ran under it. The failure list is the
  // engine's machine-emitted field, whatever the prose above it says.
  delivery(d) {
    const list = (arr) => arr.map(f =>
      escHtml(typeof f === 'string' ? f : JSON.stringify(f))).join('<br>');
    let extra = '';
    if ((d.failures || []).length) {
      extra += `<div class="cev-notrun"><b>NOT EVERYTHING RAN</b><br>${list(d.failures)}
        <br><span class="muted">machine-emitted from what happened, not a seat's account of it</span></div>`;
    }
    if ((d.out_of_time || []).length) {
      extra += `<div class="cev-notrun"><b>OUT OF TIME</b><br>${list(d.out_of_time)}</div>`;
    }
    if ((d.notes || []).length) {
      extra += `<div class="muted" style="margin-top:6px">${list(d.notes)}</div>`;
    }
    const steps = (d.steps || []).map(s =>
      `<tr><td>${escHtml(String(s.seat || ''))}</td>
           <td>${escHtml(String(s.elapsed ?? ''))}s</td>
           <td>${escHtml(String(s.tools ?? ''))}</td>
           <td>${s.skipped ? '<span class="badge badge-yellow">skipped</span>'
                           : s.error ? '<span class="badge badge-red">error</span>'
                                     : '<span class="badge badge-green">ran</span>'}</td></tr>`).join('');
    this.row('cev-delivery',
      `<b>DELIVERY</b> ${escHtml(d.pipeline || '')}${d.elapsed != null ? ' · ' + escHtml(String(d.elapsed)) + 's' : ''}
       <div class="cev-text">${escHtml(d.text || '')}</div>${extra}
       ${steps ? `<table class="cev-steps"><thead><tr><th>seat</th><th>elapsed</th><th>tools</th><th></th></tr></thead><tbody>${steps}</tbody></table>` : ''}
       ${d.transcript ? `<div class="muted" style="margin-top:6px">transcript <code>${escHtml(d.transcript)}</code></div>` : ''}`);
  }
};
