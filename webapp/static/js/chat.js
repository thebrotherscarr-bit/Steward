// ATLAS Watchboard — the council from the inside.
//
// The operator, 2026-09-10: "review that chat panel, do we really need that?
// ... more of the in-depth view", then "have that string all of the CoT,
// thinking, tool calls, etc. basically like a multi-panel watchboard to see
// the backend of all the system and core work so literally every tool call
// and everything is being landed on a page. this would be like the internal
// chat of the models themselves."
//
// WHAT WAS HERE BEFORE, AND WHY IT WENT. This page was a second conversation:
// the same box as the launchpad, the same `Chat.thread` array, the same
// answer bubbles, plus scrollback. Two of its jobs were real and neither
// needed a whole page — answering a gate, and showing each seat's words as
// they stream — and both of those belong in a watchboard. The launchpad keeps
// the conversation; this keeps the machinery.
//
// THE FEED WAS ALREADY THERE. council.js has kept EVERY event of every turn
// since it was written — "the record of a run is the events" — and nothing
// rendered them but a single-column card, which deliberately drops the one
// kind that matters most here:
//
//     case 'token': return '';   // in App.runRow
//
// The seats' own words. The step-by-step shows what the council DID; this
// shows what the models SAID while doing it. Same wire, nothing new asked of
// the engine, nothing new stored, no second definition of anything.
//
// FOUR PANELS, because they answer four different questions and reading them
// interleaved is what made the single column unreadable:
//
//   THE TURN   what was asked, under which pipeline, and what came back
//   THE FLOOR  every seat that took it, its model, and its raw output whole
//   THE TOOLS  every call: who made it, the arguments in, the result out
//   THE WIRE   every event in order, unreduced, including kinds this build
//              has never heard of — an unknown event is still something that
//              happened, and an omission here looks like nothing happening
//
// AND THE PAST. The live turn is one turn; `logs/` holds every run this
// ground has ever made, served whole with a sha256 by `records`. That list is
// on this page, so the in-depth view is not only the in-depth view of now.
//
// WHAT THIS PAGE MAY NEVER HIDE, carried over unchanged:
//   · a failed or refused tool, on the face of the turn, never behind a click
//   · a question from the council, answered in a field, never a prompt(),
//     never a default, never a guess (RULE 6)
//   · that no engine is open: a disabled box with the reason written out
//
// The object is still called Chat because it still owns the conversation with
// the council — home.js and flows.js both read `Chat.thread` — and the thread
// is genuinely the chat. The PAGE it draws is the watchboard.
const Chat = {
  thread: [],          // [{who:'him'|'council', text, turn?}] — shared with Home
  bound: false,
  shut: {},            // seats folded shut by hand, by index; open by default
  raw: false,          // the wire: every frame, or tokens folded

  async render(el) {
    this.el = el;
    if (!this.bound) { Run.on((w) => this.onRun(w)); this.bound = true; }

    el.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">Watchboard</div>
          <div class="page-subtitle">Every seat, every tool, every event — the council from the inside</div>
        </div>
        <div class="flex">
          <span id="wb-state" class="badge">&mdash;</span>
          <button class="btn btn-sm" id="wb-cancel" type="button" hidden>Cancel</button>
        </div>
      </div>

      <div class="card" id="wb-turn"></div>

      <div class="wb-grid mt-16">
        <div class="card wb-panel">
          <div class="card-header"><span class="card-title">The floor</span>
            <span class="muted" id="wb-floor-n"></span></div>
          <div id="wb-floor" class="wb-scroll"></div>
        </div>
        <div class="card wb-panel">
          <div class="card-header"><span class="card-title">The tools</span>
            <span class="muted" id="wb-tools-n"></span></div>
          <div id="wb-tools" class="wb-scroll"></div>
        </div>
      </div>

      <div class="card mt-16 wb-panel">
        <div class="card-header"><span class="card-title">The wire</span>
          <span class="flex"><span class="muted" id="wb-wire-n"></span>
            <button class="btn btn-sm" id="wb-raw" type="button">raw</button></span></div>
        <div id="wb-wire" class="wb-scroll wb-wire"></div>
      </div>

      <div class="card home-box mt-16">
        <div id="wb-gate"></div>
        <form id="wb-form" class="chat-form">
          <button class="btn btn-mic" type="button" id="wb-mic" title="Speak (local whisper, nothing leaves this machine)">&#127908;</button>
          <input id="wb-input" class="input" type="text" autocomplete="off"
                 placeholder="Say what you want done..." />
          <button class="btn btn-primary" type="submit" id="wb-send">Send</button>
        </form>
        <div id="wb-foot" class="muted chat-foot"></div>
      </div>

      <div class="card mt-16">
        <div class="card-header"><span class="card-title">Earlier runs</span>
          <span class="muted" id="wb-past-n">reading the record...</span></div>
        <div id="wb-past"></div>
      </div>`;

    const form = document.getElementById('wb-form');
    const input = document.getElementById('wb-input');
    form.onsubmit = (e) => { e.preventDefault(); this.send(); };
    // A form's implicit submit is not reliable in every host, and a send box
    // that ignores Enter reads as broken.
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.send(); }
    });
    document.getElementById('wb-cancel').onclick = () => Run.cancel();
    document.getElementById('wb-raw').onclick = () => {
      this.raw = !this.raw;
      document.getElementById('wb-raw').textContent = this.raw ? 'folded' : 'raw';
      this.paintWire();
    };
    document.getElementById('wb-mic').onclick = () => this.mic();

    this.paint();
    // ADOPT A TURN ALREADY IN FLIGHT — started on the launchpad, or one he
    // walked away from. The controls read Run's state, never an event this
    // page may not have been present to hear.
    if (Run.running) this.tick(true);
    await Run.check();
    this.readPast();
  },

  mic() {
    const btn = document.getElementById('wb-mic');
    const input = document.getElementById('wb-input');
    if (Run.listening) { Run.stopHearing(); btn.classList.remove('hot'); return; }
    if (!Run.engineOpen) { toast('No engine is open on this world', 'error'); return; }
    btn.classList.add('hot');
    Run.hear(
      () => {},
      (text) => {
        btn.classList.remove('hot');
        input.value = (input.value ? input.value + ' ' : '') + text;
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      },
      (why) => { btn.classList.remove('hot'); toast(why, 'error'); });
  },

  // ---- painting -----------------------------------------------------------

  paint() {
    this.paintState();
    this.paintTurn();
    this.paintFloor();
    this.paintTools();
    this.paintWire();
    this.paintGate();
  },

  paintState() {
    const b = document.getElementById('wb-state');
    const c = document.getElementById('wb-cancel');
    const t = Run.turn;
    if (c) c.hidden = !Run.running;
    if (b) {
      b.className = 'badge ' + (Run.running ? 'badge-blue' : t ? 'badge-green' : '');
      b.textContent = Run.running ? 'running · ' + Run.elapsed()
        : t ? (t.verdict || 'done') + ' · ' + Run.elapsed(t)
        : (Run.engineOpen ? 'engine open · sitting ' + (Run.sitting || '?') : 'no engine');
    }
    const send = document.getElementById('wb-send');
    if (send) send.disabled = !Run.engineOpen || Run.running;
    const foot = document.getElementById('wb-foot');
    if (foot) foot.textContent = Run.engineOpen ? '' :
      'No engine is open on this world. This page will not start one behind ' +
      'your back — that opens a sitting you never opened, and the sitting line ' +
      'is the lock. Boot one from the Dashboard.';
  },

  // THE TURN: what was asked, under what, and what came back. The delivery's
  // failures are on its face, never folded away (LAW 5).
  paintTurn() {
    const box = document.getElementById('wb-turn');
    if (!box) return;
    const t = Run.turn;
    if (!t) {
      box.innerHTML = `<div class="empty-text">Nothing has run in this tab yet.
        Say something below, or open an earlier run from the record at the foot
        of this page.</div>`;
      return;
    }
    const seats = Run.steps(t).length || (t.seats || []).length;
    const tools = (t.tools || []).length;
    const fails = Run.failures(t);
    const oot = Run.outOfTime ? Run.outOfTime(t) : [];
    box.innerHTML = `
      <div class="wb-obj">${escHtml(t.objective || '')}</div>
      <div class="wb-facts">
        <span><b>${escHtml(t.pipeline || 'default')}</b> pipeline</span>
        <span>${seats} seat${seats === 1 ? '' : 's'}</span>
        <span>${tools} tool call${tools === 1 ? '' : 's'}</span>
        <span>${(t.events || []).length} events</span>
        <span id="wb-elapsed">${escHtml(Run.elapsed(t))}</span>
        <span class="${t.refusal ? 'tool-bad' : ''}">${escHtml(t.verdict || (Run.running ? 'running' : 'done'))}</span>
      </div>
      ${t.thinned ? `<div class="wb-bad"><b>the events were not kept</b> — this turn
        came back from storage without its record. The delivery is whole; the
        panels below are not.</div>` : ''}
      ${fails.length ? `<div class="wb-bad"><b>NOT EVERYTHING RAN</b><br>${
        fails.map(escHtml).join('<br>')}<br><span class="muted">machine-emitted
        from what happened, not a seat's account of it</span></div>` : ''}
      ${oot.length ? `<div class="wb-bad"><b>OUT OF TIME</b><br>${oot.map(escHtml).join('<br>')}</div>` : ''}
      ${t.dropped ? `<div class="wb-bad"><b>${t.dropped} events were dropped</b>
        — this page did not see everything that ran</div>` : ''}
      ${t.refusal ? `<div class="wb-bad"><b>${escHtml((t.verdict || 'refused').toUpperCase())}</b>
        ${escHtml(t.refusal)}</div>` : ''}
      ${t.answer && !Run.running ? `<div class="wb-delivery">
        <div class="wb-label">The delivery — the recompose, which is what he is answered with</div>
        <div class="wb-words">${escHtml(t.answer)}</div></div>` : ''}
      ${t.transcript ? `<div class="brief-src">transcript ${escHtml(t.transcript)}</div>` : ''}`;
  },

  // THE FLOOR: the thing this page exists for. Every seat that took it, its
  // model, and its OWN WORDS whole — not the recompose, not a summary. The
  // step-by-step card drops these on purpose; this is where they live.
  paintFloor() {
    const box = document.getElementById('wb-floor');
    if (!box) return;
    const t = Run.turn;
    const seats = (t && t.seats) || [];
    const n = document.getElementById('wb-floor-n');
    if (n) n.textContent = seats.length ? seats.length + ' took the floor' : '';
    if (!seats.length) {
      box.innerHTML = `<div class="empty-text">No seat has spoken yet.</div>`;
      return;
    }
    box.innerHTML = seats.map((s, i) => {
      const shut = this.shut[i] === true;
      const words = (s.text || '').trim();
      return `<div class="wb-seat${shut ? ' shut' : ''}">
        <button class="wb-seat-head" type="button" data-seat="${i}">
          <span class="wb-seat-name">${escHtml(s.seat || 'seat')}</span>
          <span class="wb-seat-model">${escHtml(s.model || '')}</span>
          <span class="wb-seat-n">${words.length ? words.length + ' chars' : 'silent so far'}</span>
        </button>
        ${shut ? '' : `<div class="wb-words">${words
          ? escHtml(words)
          : '<span class="muted">nothing on the wire from this seat yet</span>'}</div>`}
      </div>`;
    }).join('');
    box.querySelectorAll('[data-seat]').forEach(b => {
      b.onclick = () => {
        const i = +b.dataset.seat;
        this.shut[i] = !this.shut[i];
        this.paintFloor();
      };
    });
    if (Run.running) box.scrollTop = box.scrollHeight;
  },

  // THE TOOLS: who called what, with which arguments, and what came back.
  // `failed` is the ENGINE'S own field — the pipeline's test, not a reading of
  // the words that came back.
  paintTools() {
    const box = document.getElementById('wb-tools');
    if (!box) return;
    const t = Run.turn;
    const calls = ((t && t.events) || []).filter(e => e._kind === 'tool' || e._kind === 'tool_result');
    const n = document.getElementById('wb-tools-n');
    const tools = (t && t.tools) || [];
    if (n) n.textContent = tools.length ? tools.length + ' called' : '';
    if (!calls.length) {
      box.innerHTML = `<div class="empty-text">No skill has been called in this turn.</div>`;
      return;
    }
    box.innerHTML = calls.map(d => {
      const name = d.action || d.tool || d.name || '?';
      if (d._kind === 'tool') {
        return `<div class="wb-call">
          <div class="wb-call-head"><b>${escHtml(name)}</b>${d.seat
            ? ` <span class="muted">called by ${escHtml(d.seat)}</span>` : ''}</div>
          ${d.args ? `<pre class="wb-args">${escHtml(JSON.stringify(d.args, null, 1))}</pre>` : ''}
        </div>`;
      }
      return `<div class="wb-call ${d.failed ? 'bad' : 'ok'}">
        <div class="wb-call-head"><b>${d.failed ? 'FAILED' : 'ok'}</b> ${escHtml(name)}</div>
        ${d.error ? `<div class="wb-err">${escHtml(d.error)}</div>` : ''}
        ${d.text ? `<pre class="wb-args">${escHtml(String(d.text).slice(0, 4000))}</pre>` : ''}
      </div>`;
    }).join('');
    if (Run.running) box.scrollTop = box.scrollHeight;
  },

  // THE WIRE: every event, in order, unreduced. `raw` prints each whole
  // payload; folded prints one line each. Tokens are COUNTED rather than
  // listed when folded — a turn carries hundreds and they are shown whole on
  // the floor — but `raw` lists them too, because "every event" has to mean
  // every event or this panel is only another summary.
  paintWire() {
    const box = document.getElementById('wb-wire');
    if (!box) return;
    const t = Run.turn;
    const evs = (t && t.events) || [];
    const n = document.getElementById('wb-wire-n');
    if (n) n.textContent = evs.length ? evs.length + ' events' : '';
    if (!evs.length) {
      box.innerHTML = `<div class="empty-text">The wire is quiet.</div>`;
      return;
    }
    if (this.raw) {
      box.innerHTML = evs.map(d =>
        `<div class="wb-ev"><span class="wb-kind">${escHtml(String(d._kind))}</span>` +
        `<code>${escHtml(JSON.stringify(d))}</code></div>`).join('');
    } else {
      let frames = 0, chars = 0;
      const out = [];
      const flush = () => {
        if (!frames) return;
        out.push(`<div class="wb-ev wb-dim"><span class="wb-kind">token</span>` +
          `<code>${frames} frames · ${chars} chars · shown whole on the floor</code></div>`);
        frames = 0; chars = 0;
      };
      for (const d of evs) {
        if (d._kind === 'token') { frames++; chars += (d.text || '').length; continue; }
        flush();
        out.push(`<div class="wb-ev"><span class="wb-kind">${escHtml(String(d._kind))}</span>` +
          `<code>${escHtml(this.oneLine(d))}</code></div>`);
      }
      flush();
      box.innerHTML = out.join('');
    }
    if (Run.running) box.scrollTop = box.scrollHeight;
  },

  // One line for an event, without inventing a shape for a kind this build has
  // never met: anything unrecognised is printed as its own JSON.
  oneLine(d) {
    const k = d._kind;
    if (k === 'seat') return (d.seat || '') + ' · ' + (d.model || '');
    if (k === 'run') return 'pipeline ' + (d.pipeline || '') + (d.transcript ? ' · ' + d.transcript : '');
    if (k === 'tool') return (d.action || d.tool || d.name || '?') +
      (d.args ? ' ' + JSON.stringify(d.args).slice(0, 160) : '');
    if (k === 'tool_result') return (d.failed ? 'FAILED ' : 'ok ') +
      (d.action || d.tool || d.name || '?') + (d.error ? ' · ' + d.error : '');
    if (k === 'report' || k === 'note') return (d.text || '').trim().slice(0, 200);
    if (k === 'needs_answer') return (d.prompt || '').slice(0, 200);
    if (k === 'delivery') return (d.pipeline || '') + ' · ' + String(d.text || '').length + ' chars';
    const copy = Object.assign({}, d);
    delete copy._kind;
    return JSON.stringify(copy).slice(0, 300);
  },

  // THE GATE. A question from the council is answered in a field on this page,
  // never a prompt(), never a default, never a guess. RULE 6.
  paintGate() {
    const box = document.getElementById('wb-gate');
    if (!box) return;
    const asking = (Run.turn && Run.turn.waiting) || Run.pending || '';
    if (!asking || Run.running) { box.innerHTML = ''; return; }
    box.innerHTML = `<div class="wb-gate">
      <div class="wb-gate-title">The council is asking</div>
      <div class="wb-gate-prompt">${escHtml(asking)}</div>
      <form class="chat-form" id="wb-gate-form">
        <input class="input" type="text" autocomplete="off"
               placeholder="Your answer — nothing is assumed on your behalf" />
        <button class="btn" type="submit">Answer</button>
      </form></div>`;
    const f = document.getElementById('wb-gate-form');
    f.onsubmit = (e) => {
      e.preventDefault();
      const v = f.querySelector('input').value;
      if (v.trim()) this.answer(v);
    };
    f.querySelector('input').focus();
  },

  // ---- the record of every earlier run ------------------------------------
  //
  // The live turn is ONE turn. `logs/` holds every run this ground has made,
  // and `records` serves any of them whole with a sha256 — so the in-depth
  // view is not only the in-depth view of right now. This is the half of his
  // question that started the page: "should we move the session tracking over
  // there?"
  async readPast() {
    const box = document.getElementById('wb-past');
    const n = document.getElementById('wb-past-n');
    if (!box) return;
    let d;
    try {
      d = JSON.parse(await App.tool('records', { kind: 'logs' }));
    } catch (e) {
      box.innerHTML = `<div class="empty-text">The record could not be read:
        ${escHtml(e.message || 'refused')}</div>`;
      if (n) n.textContent = '';
      return;
    }
    const docs = d.documents || [];
    if (n) n.textContent = docs.length + ' written down in logs/';
    if (!docs.length) {
      box.innerHTML = `<div class="empty-text">No run has been written down yet.</div>`;
      return;
    }
    box.innerHTML = `<div class="table-wrap"><table><thead><tr>
        <th>run</th><th>when</th><th class="num">size</th></tr></thead><tbody>` +
      docs.map(x => `<tr class="wb-past-row" data-doc="${escHtml(x.name)}">
        <td>${escHtml(this.runName(x.name))}</td>
        <td>${escHtml(when(Date.parse(x.modified) || 0))}</td>
        <td class="num">${(x.bytes / 1024).toFixed(1)} KB</td></tr>`).join('') +
      `</tbody></table></div><div id="wb-past-doc"></div>`;
    box.querySelectorAll('[data-doc]').forEach(r => {
      r.onclick = () => this.readOne(r.dataset.doc);
    });
  },

  // `logs/2026-09-10_200628_git_commit_a_skill_is_offered....md` is a stamp
  // and an objective welded together. The objective is the part a person
  // recognises, so it is what the row shows.
  runName(name) {
    const base = String(name).replace(/^logs\//, '').replace(/\.md$/, '');
    const m = base.match(/^(\d{4}-\d\d-\d\d)_(\d{6})_(.*)$/);
    return m ? m[3].replace(/_/g, ' ') : base;
  },

  async readOne(name) {
    const box = document.getElementById('wb-past-doc');
    if (!box) return;
    box.innerHTML = `<div class="loading">Reading ${escHtml(name)}...</div>`;
    try {
      const d = JSON.parse(await App.tool('records', { name }));
      box.innerHTML = `<div class="wb-past-open">
        <div class="card-header"><span class="card-title">${escHtml(this.runName(name))}</span>
          <span class="muted">${d.bytes} bytes</span></div>
        <pre class="seat-prompt">${escHtml(d.text || '')}</pre>
        <div class="brief-src">records · sha256 ${escHtml(String(d.sha256 || '').slice(0, 16))}</div>
      </div>`;
    } catch (e) {
      box.innerHTML = `<div class="wb-bad">It could not be served: ${escHtml(e.message || 'refused')}</div>`;
    }
  },

  // ---- sending ------------------------------------------------------------

  send() {
    const input = document.getElementById('wb-input');
    const q = input.value.trim();
    if (!q || Run.running) return;
    if (!Run.engineOpen) { toast('No engine is open on this world', 'error'); return; }
    input.value = '';
    this.thread.push({ who: 'him', text: q });
    this.thread.push({ who: 'council', text: '', live: true });
    Run.start({ objective: q });
  },

  answer(text) {
    if (Run.running) return;
    this.thread.push({ who: 'him', text });
    this.thread.push({ who: 'council', text: '', live: true });
    Run.start({ answer: text });
  },

  // A seat thinking says nothing on the wire, sometimes for a minute. The
  // clock keeps moving on its own, or a working engine reads as a hung one and
  // he cancels a turn that was fine.
  tick(on) {
    clearInterval(this._tick);
    this._tick = null;
    if (!on) return;
    this._tick = setInterval(() => {
      if (!Run.running) { this.tick(false); return; }
      if (!document.getElementById('wb-state')) { this.tick(false); return; }
      this.paintState();
      // AND THE TURN'S OWN CLOCK, into the span the repaint leaves alone.
      // The facts row is painted per EVENT, and a seat can think for a minute
      // without putting one on the wire — so it read 2.6s beside a badge
      // reading 49s. Two clocks on one page disagreeing is the exact fault
      // this console keeps removing, and the stale one was the one sitting
      // next to the objective.
      const e = document.getElementById('wb-elapsed');
      if (e) e.textContent = Run.elapsed();
    }, 1000);
  },

  // ---- what Run tells us --------------------------------------------------

  onRun(what) {
    // The guard names an element this handler actually writes into.
    if (!this.el || !document.getElementById('wb-wire')) return;

    if (what === 'state') { this.paintState(); this.paintGate(); return; }

    const last = this.thread[this.thread.length - 1];

    if (what === 'start') {
      // A turn this browser did not ask for still needs somewhere to land.
      if (Run.turn && Run.turn.watching && !this.thread.some(m => m.live)) {
        this.thread.push({ who: 'him', text: Run.turn.objective || '' });
        this.thread.push({ who: 'council', text: '', live: true });
      }
      this.shut = {};
      this.tick(true);
      this.paint();
      return;
    }

    if (what === 'event') {
      if (last && last.who === 'council') last.turn = Run.turn;
      // The whole board, every event. It is four panels of a few hundred rows,
      // not a conversation re-rendered per token, and the one panel that could
      // get expensive — the wire — folds its tokens into a count.
      this.paintTurn();
      this.paintFloor();
      this.paintTools();
      this.paintWire();
      return;
    }

    if (what === 'end') {
      if (last && last.who === 'council') { last.turn = Run.turn; last.live = false; }
      this.tick(false);
      this.paint();
      Run.check();
    }
  }
};
