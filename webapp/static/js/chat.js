// ATLAS Chat — the conversation with the council.
//
// The operator, 2026-09-09: "rebuild the chat page clean." So this page is a
// conversation and nothing else: what he said, what came back, and ONE line of
// what is happening while it streams. The waterfall — every seat, every tool,
// every result, the per-seat table — moved to Evals, which is where a run is
// inspected ("this looks like the evals loops. lets put it there").
//
// Every message goes through the whole estate: the sealed law gate stamps the
// objective before any model reads a word, the one Router executes the tools,
// the dedup refuses a repeat, and the recompose puts every failure into the
// delivery. Run (council.js) owns that wire; this file only draws.
//
// WHAT THIS PAGE MAY NEVER HIDE, however clean it gets:
//   · a failed or refused tool  — the delivery's own `failures`, shown red
//     under the answer it belongs to, never folded away behind a click
//   · a question from the council — answered in a form field, never a
//     prompt(), never a default, never a guess (RULE 6)
//   · that no engine is open — a disabled box with the reason, not a turn
//     that fails
// Clean means less furniture, not less truth.
const Chat = {
  thread: [],          // [{who:'him'|'council', text, turn?}]
  bound: false,

  async render(el) {
    this.el = el;
    // A live stream must not outlive the page that owned it. Navigating away
    // mid-turn used to leave the reader attached to a log element that no
    // longer existed. The turn itself keeps running inside the engine.
    if (!this.bound) { Run.on((w) => this.onRun(w)); this.bound = true; }

    el.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">Chat</div>
          <div class="page-subtitle">The whole estate — law gate, one Router, every tool, the recompose</div>
        </div>
        <div class="flex">
          <span id="chat-engine" class="badge">checking...</span>
          <button class="btn btn-sm" id="chat-clear" type="button">Clear</button>
        </div>
      </div>
      <div class="card chat-card">
        <div id="chat-thread" class="chat-thread"></div>
        <div id="chat-now" class="chat-now" hidden></div>
        <form id="chat-form" class="chat-form">
          <input id="chat-input" class="input" type="text" autocomplete="off"
                 placeholder="Say what you want done..." />
          <button class="btn btn-primary" type="submit" id="chat-send">Send</button>
          <button class="btn btn-sm" type="button" id="chat-cancel" hidden>Cancel</button>
        </form>
        <div id="chat-foot" class="muted chat-foot"></div>
      </div>`;

    const form = document.getElementById('chat-form');
    const input = document.getElementById('chat-input');
    form.onsubmit = (e) => { e.preventDefault(); this.send(); };
    // Enter sends. A form's implicit submit is not reliable in every host, and
    // a send box that ignores Enter reads as broken.
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.send(); }
    });
    document.getElementById('chat-cancel').onclick = () => Run.cancel();
    document.getElementById('chat-clear').onclick = () => {
      this.thread = []; this.draw();
    };

    this.draw();
    await Run.check();
  },

  // ---- drawing ------------------------------------------------------------

  draw() {
    const box = document.getElementById('chat-thread');
    if (!box) return;
    box.innerHTML = this.thread.length
      ? this.thread.map((m, i) => this.bubble(m, i)).join('')
      : `<div class="empty-text chat-empty">Nothing said yet.</div>`;
    // wire each answer's Details toggle and any open gate
    // In-app, not a reload: a reload would drop the run this link exists to
    // show (it is restored from storage, but the common path should never
    // need that).
    box.querySelectorAll('[data-nav]').forEach(a => {
      a.onclick = (e) => {
        e.preventDefault();
        history.pushState(null, '', '/' + a.dataset.nav);
        App.router();
      };
    });
    box.querySelectorAll('[data-toggle]').forEach(b => {
      b.onclick = () => {
        const d = b.parentElement.querySelector('.chat-detail');
        if (d) d.hidden = !d.hidden;
      };
    });
    const gate = box.querySelector('.chat-gate form');
    if (gate) {
      gate.onsubmit = (e) => {
        e.preventDefault();
        const v = gate.querySelector('input').value;
        if (!v.trim()) return;
        this.answer(v);
      };
      const gi = gate.querySelector('input');
      if (gi) gi.focus();
    }
    box.scrollTop = box.scrollHeight;
  },

  bubble(m, i) {
    if (m.who === 'him') return `<div class="chat-q">${escHtml(m.text)}</div>`;

    const t = m.turn;
    // The council asking is not an answer — it is a gate, and it looks like one.
    if (t && t.waiting && i === this.thread.length - 1 && !Run.running) {
      return `<div class="chat-a chat-gate">
        <div class="chat-gate-title">The council is asking</div>
        <div class="chat-gate-prompt">${escHtml(t.waiting)}</div>
        <form class="chat-form">
          <input class="input" type="text" autocomplete="off"
                 placeholder="Your answer — nothing is assumed on your behalf" />
          <button class="btn" type="submit">Answer</button>
        </form></div>`;
    }

    if (t && t.refusal && !t.answer) {
      return `<div class="chat-a chat-refused"><b>REFUSED</b><br>${escHtml(t.refusal)}</div>`;
    }

    const live = m.live ? ' live' : '';
    let foot = '';
    if (t && !m.live) {
      const fails = Run.failures(t);
      const oot = Run.outOfTime(t);
      // THE FAILURES ARE NOT BEHIND THE TOGGLE. An answer that ran on a tool
      // that failed says so on its face, or the page is lying by omission.
      if (fails.length) {
        foot += `<div class="chat-notrun"><b>NOT EVERYTHING RAN</b><br>` +
          fails.map(escHtml).join('<br>') +
          `<br><span class="muted">machine-emitted from what happened, not a seat's account of it</span></div>`;
      }
      if (oot.length) {
        foot += `<div class="chat-notrun"><b>OUT OF TIME</b><br>${oot.map(escHtml).join('<br>')}</div>`;
      }
      if (t.dropped) {
        foot += `<div class="chat-notrun"><b>${t.dropped} events were dropped</b> — this page did not see everything that ran</div>`;
      }
      const seats = Run.steps(t).length || t.seats.length;
      foot += `<div class="chat-meta">
        ${escHtml(t.pipeline || 'default')} · ${escHtml(Run.elapsed(t))}${seats ? ' · ' + seats + ' seats' : ''}
        <button class="chat-link" data-toggle="1" type="button">what ran</button>
        <a class="chat-link" href="/evals" data-nav="evals">inspect</a></div>
        <div class="chat-detail" hidden>${this.detail(t)}</div>`;
    }
    return `<div class="chat-a${live}">${escHtml(t ? t.answer : m.text)}${foot}</div>`;
  },

  // A short summary here; the full waterfall is the Evals page's job.
  detail(t) {
    const steps = Run.steps(t);
    const rows = steps.length
      ? steps.map(s => `<tr><td>${escHtml(String(s.seat || ''))}</td>
          <td>${escHtml(String(s.elapsed ?? ''))}s</td>
          <td>${s.skipped ? 'skipped' : s.error ? 'error' : 'ran'}</td></tr>`).join('')
      : t.seats.map(s => `<tr><td>${escHtml(s.seat)}</td><td>${escHtml(s.model)}</td><td>ran</td></tr>`).join('');
    const tools = t.tools.map(x =>
      `<div>${x.failed ? 'FAILED' : x.done ? 'ok' : 'ran'} · ${escHtml(x.name)}` +
      (x.error ? ' — ' + escHtml(x.error) : '') + `</div>`).join('');
    return `${tools ? `<div class="chat-tools">${tools}</div>` : ''}
      ${rows ? `<table class="chat-steps"><tbody>${rows}</tbody></table>` : ''}
      ${t.transcript ? `<div class="muted">transcript <code>${escHtml(t.transcript)}</code></div>` : ''}`;
  },

  now(text) {
    const el = document.getElementById('chat-now');
    if (!el) return;
    el.hidden = !text;
    el.textContent = text || '';
  },

  foot(text) {
    const el = document.getElementById('chat-foot');
    if (el) el.textContent = text || '';
  },

  // ---- sending ------------------------------------------------------------

  send() {
    const input = document.getElementById('chat-input');
    const q = input.value.trim();
    if (!q || Run.running) return;
    if (!Run.engineOpen) { toast('No engine is open on this world', 'error'); return; }
    input.value = '';
    this.thread.push({ who: 'him', text: q });
    this.thread.push({ who: 'council', text: '', live: true });
    this.draw();
    Run.start({ objective: q });
  },

  answer(text) {
    if (Run.running) return;
    this.thread.push({ who: 'him', text });
    this.thread.push({ who: 'council', text: '', live: true });
    this.draw();
    Run.start({ answer: text });
  },

  // ---- what Run tells us --------------------------------------------------

  onRun(what) {
    if (!this.el || !document.getElementById('chat-thread')) return;  // not the live page

    if (what === 'state') {
      const b = document.getElementById('chat-engine');
      if (b) {
        if (Run.unreachable) { b.className = 'badge badge-red'; b.textContent = 'door unreachable'; }
        else if (Run.engineOpen) { b.className = 'badge badge-green'; b.textContent = 'engine open · sitting ' + (Run.sitting || '?'); }
        else { b.className = 'badge badge-yellow'; b.textContent = 'no engine'; }
      }
      const send = document.getElementById('chat-send');
      if (send) send.disabled = !Run.engineOpen;
      this.foot(Run.engineOpen ? '' :
        'No engine is open on this world. This page will not start one behind your ' +
        'back — that opens a sitting you never opened, and the sitting line is the lock. ' +
        'Open one with env_open.');
      // The council may already be mid-question from a previous page load.
      if (Run.pending && !this.thread.some(m => m.turn && m.turn.waiting === Run.pending)) {
        this.thread.push({ who: 'council', text: '', turn: { waiting: Run.pending, answer: '' } });
        this.draw();
      }
      return;
    }

    const last = this.thread[this.thread.length - 1];
    if (!last || last.who !== 'council') return;

    if (what === 'start') {
      document.getElementById('chat-cancel').hidden = false;
      document.getElementById('chat-send').disabled = true;
      return;
    }

    if (what === 'event') {
      last.turn = Run.turn;
      // While it streams the page shows the ANSWER SO FAR plus one line of what
      // is happening. Not the log — the log is Evals.
      const live = document.querySelector('#chat-thread .chat-a.live');
      if (live) live.textContent = Run.turn.answer;
      this.now(Run.nowLine() + ' · ' + Run.elapsed());
      const box = document.getElementById('chat-thread');
      if (box) box.scrollTop = box.scrollHeight;
      return;
    }

    if (what === 'end') {
      last.turn = Run.turn;
      last.live = false;
      this.now('');
      document.getElementById('chat-cancel').hidden = true;
      document.getElementById('chat-send').disabled = !Run.engineOpen;
      this.draw();
      Run.check();
    }
  }
};
