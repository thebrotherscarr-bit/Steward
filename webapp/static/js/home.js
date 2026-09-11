// ATLAS Home — the launchpad.
//
// The operator, 2026-09-09: "the dashboard should basically be a launchpad for
// getting things done, a little simple brief showing the system health, and
// then an obvious box for 'what we are working on'."
//
// THE RULE THIS PAGE IS HELD TO: a line earns its place only if it changes what
// you do next. The old dashboard reported eleven true things -- the rack's
// three tiers, 68 tools with no forbidden verb, can_approve false in every
// declaration, the covenant hash. All true, none of them a decision. They came
// off. What is left is the three questions that actually gate the next move:
//
//   Can I work at all?      no engine open means nothing typed here will run
//   Is something waiting?   a gate, a council question, a refused tag
//   Is something broken?    the rack unreachable, the law chain not whole
//
// GREEN IS SILENCE. When all three are well the brief is ONE line. The page
// grows only when something needs him, so a quiet screen is information and a
// loud one is a to-do list. That is how the transparency stays readable
// without a wall of text.
//
// EVERY LINE STILL NAMES THE TOOL IT CAME FROM. That was the old dashboard's
// best idea and it survives the rewrite: a number the record cannot prove is
// not shown (SPEC 3 invariant 10).
const Home = {
  brief: null,
  // An objective staged from another page (Version control's Recent), waiting
  // for the next render to put it in the box. Never run on its own.
  pending: '',

  bound: false,

  async render(el) {
    this.el = el;
    if (!this.bound) { Run.on((w) => this.onRun(w)); this.bound = true; }
    el.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">What are we working on?</div>
          <div class="page-subtitle" id="home-sub">Reading the record...</div>
        </div>
      </div>

      <!-- WHAT THIS BUILD HAS PROVED, FIRST. The scores lived at the top of
           Records, a page you go to; they answer "is the build sound", which
           is the question the launchpad should answer before you type into it.
           Moved here 2026-09-10 at the operator's word. One proofs call,
           read by App.paintProof, which still paints the estate half on
           Records. -->
      <div id="home-proof"></div>

      <div class="card home-box mt-16">
        <div id="home-thread" class="home-thread" hidden></div>
        <form id="home-form" class="chat-form">
          <button class="btn btn-mic" type="button" id="home-mic" title="Speak (local whisper, nothing leaves this machine)">&#127908;</button>
          <input id="home-input" class="input home-input" type="text" autocomplete="off"
                 placeholder="Say what you want done..." />
          <button class="btn btn-primary" type="submit" id="home-go">Run</button>
        </form>
        <div id="home-block" class="home-block" hidden></div>
      </div>

      <!-- THE RUN, UNDER THE BOX HE TYPED INTO. It was a card on Evals, a page
           away from the thing that started it. The id stays ev-run so
           App.paintRun draws it unchanged -- the turn is the same turn, and a
           second copy of that renderer would be the drift this estate keeps
           writing docstrings about. -->
      <div class="card" id="home-run-card">
        <div class="card-header">
          <span class="card-title">The run, step by step</span>
          <span class="flex"><span id="ev-run-state" class="badge">&mdash;</span>
            <button class="btn btn-sm" id="ev-run-cancel" type="button" hidden>Cancel</button></span>
        </div>
        <div id="ev-run" class="chat-log council-log"></div>
      </div>

      <!-- THE ENGINE, LOWER. It opened the page and crowded it: a card whose
           whole content is one sentence, above everything you came here to do.
           It is still above the brief, because nothing below it runs until an
           engine is open. -->
      <div class="card" id="home-engine-card">
        <div class="card-header">
          <span class="card-title">The engine</span>
          <span class="flex" id="home-engine-controls"></span>
        </div>
        <div id="home-engine"></div>
        <pre id="home-boot" class="home-boot" hidden></pre>
      </div>

      <div id="home-brief" class="card home-brief"></div>

      <!-- The repository card MOVED TO FLOWS (2026-09-10): "this needs to go
           with the other github stuff". Flows already carries the per-world
           overwatch, so every git surface is now on one page. -->

      <!-- Recent MOVED TO VERSION CONTROL, 2026-09-10, with the repository
           card it sat under. -->`;

    const form = document.getElementById('home-form');
    const input = document.getElementById('home-input');
    form.onsubmit = (e) => { e.preventDefault(); this.go(); };
    // Enter runs. A form's implicit submit is not reliable in every host.
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.go(); }
    });
    // A recent objective clicked on Version control lands here, in the box,
    // unrun. Cleared as it is taken so a later visit is not haunted by it.
    if (this.pending) { input.value = this.pending; this.pending = ''; }
    input.focus();
    document.getElementById('home-mic').onclick = () => this.mic();
    // The thread renders before anything is asked, so a conversation
    // survives navigating away and back.
    this.thread();

    // The scores, and the turn's own step-by-step. Both are App's renderers:
    // one `proofs` read and one `paintRun`, shared with Records and with
    // whatever else asks -- never a second copy that can drift.
    App.paintProof('home-proof', 'scores');
    if (!App._runBound) { Run.on(() => App.paintRun()); App._runBound = true; }
    App.paintRun();
    const cancel = document.getElementById('ev-run-cancel');
    if (cancel) cancel.onclick = () => Run.cancel();
    await this.read();
    await this.showKeptBoot();
    await this.showKeptThread();
    this.watch(true);
  },

  // THE GLASS GOES STALE IF NOBODY REPAINTS IT. He read an open sitting off
  // this page an hour after it closed -- the page was right when it was
  // painted, and was never painted again. Nothing here is cached between
  // reads; the fault was that there was only ever one read.
  //
  // Paused while the tab is hidden, refreshed the moment it comes back (which
  // is the moment he looks at it), and stopped as soon as the dashboard is no
  // longer on screen -- guarded on the element this page actually writes into,
  // because a route away leaves the interval holding a dead document.
  watch(on) {
    clearInterval(this._watch);
    this._watch = null;
    if (this._vis) { document.removeEventListener('visibilitychange', this._vis); this._vis = null; }
    if (!on) return;
    this._vis = () => {
      if (document.hidden) return;
      if (!document.getElementById('home-brief')) { this.watch(false); return; }
      this.read();
    };
    document.addEventListener('visibilitychange', this._vis);
    this._watch = setInterval(() => {
      if (!document.getElementById('home-brief')) { this.watch(false); return; }
      if (document.hidden) return;      // resumed by the listener above
      this.read();
    }, 15000);
  },

  // HOW LONG THIS ENGINE HAS BEEN STANDING, ticking, beside the clock time.
  //
  // ONE SECOND, NOT FIFTEEN. The card repaints on the 15s poll; hanging the
  // elapsed off that would make it jump in fifteen-second steps, which reads
  // as a broken clock rather than a live one. This writes into a span the
  // repaint leaves alone.
  //
  // IT STOPS ITSELF. The interval clears the moment the span is gone -- a
  // navigation away, or a repaint with no engine open -- so leaving this page
  // does not leave a timer running. An idle-engine warning that leaks timers
  // would be its own joke.
  age(on) {
    clearInterval(this._age);
    this._age = null;
    if (!on) return;
    const paint = () => {
      const el = document.getElementById('eng-age');
      if (!el) { this.age(false); return; }
      const ms = Date.now() - new Date(Run.started).getTime();
      if (!isFinite(ms) || ms < 0) { el.textContent = ''; return; }
      const s = Math.floor(ms / 1000);
      const txt = s < 60 ? s + 's'
        : s < 3600 ? Math.floor(s / 60) + 'm ' + (s % 60) + 's'
        : Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
      // IDLE IS MEASURED FROM THE LAST TURN, NOT FROM BOOT. A first cut went
      // amber only when NOTHING had ever run, which misses the shape the waste
      // actually takes: sitting 74 held an engine thirty minutes for 2 runs,
      // 82 held one fifty-four minutes for 5. Both did work. Both then sat.
      // What costs the machine is the gap since the last turn.
      //
      // THE DOOR IS ASKED, NOT THIS PAGE. `Run.turn` is only what THIS tab has
      // seen, and it is empty after a reload -- an engine that ran ten turns an
      // hour ago read as untouched. The door counts every turn it pumped, so
      // `last_run` is the truth and the tab's own memory is only the fallback
      // for an engine mid-turn.
      //
      // A RUNNING TURN IS NEVER IDLE, however long it takes. This must not
      // scold him for a slow model, only for an engine nobody is using.
      // AND IT CAN NEVER PREDATE THE ENGINE. A first cut fell back to this
      // tab's own `turn.ended` when the door reported no runs -- and that
      // memory survives a reboot, so a THIRTY-EIGHT-SECOND-OLD engine reported
      // "idle 14m", counting from a turn a previous engine had run. The floor
      // is this engine's own start: whatever else is true, it cannot have been
      // idle for longer than it has existed.
      const born = new Date(Run.started).getTime();
      const since = Math.max(
        born,
        Run.lastRun ? new Date(Run.lastRun).getTime() : 0,
        (Run.turn && Run.turn.ended) || 0);
      const idleS = Math.floor((Date.now() - since) / 1000);
      const idle = !Run.running && idleS >= 300;
      const n = Run.runs || 0;
      const ran = n === 1 ? '1 run' : n + ' runs';
      el.textContent = 'open ' + txt + ' · ' + ran
        + (idle ? ' — idle ' + Math.floor(idleS / 60) + 'm' : '');
      el.className = idle ? 'eng-idle' : '';
    };
    paint();
    this._age = setInterval(paint, 1000);
  },

  // ---- the launch ---------------------------------------------------------

  // He types here and lands in the conversation. The turn starts from Home so
  // the launchpad is not a door he passes through empty-handed.
  // HE STAYS WHERE HE TYPED. Being thrown to another page mid-thought is the
  // opposite of the loop he asked for. The turn runs here, the answer lands
  // under the box, and the whole trace still goes to Evals for inspecting.
  // Chat keeps the conversation, and this turn joins it there too, so the two
  // pages never hold different histories.
  go() {
    const input = document.getElementById('home-input');
    const q = input.value.trim();
    if (!q) return;
    if (!Run.engineOpen) { toast('No engine is open on this world', 'error'); return; }
    if (Run.running) { toast('A turn is already running', 'error'); return; }
    input.value = '';
    Chat.thread.push({ who: 'him', text: q });
    Chat.thread.push({ who: 'council', text: '', live: true });
    this.thread();
    Run.start({ objective: q });
  },

  // The last few exchanges of the SHARED thread. Chat renders all of it;
  // this renders the tail. One array, so the two views cannot disagree.
  TAIL: 6,

  thread() {
    const box = document.getElementById('home-thread');
    if (!box) return;
    const all = Chat.thread || [];
    const tail = all.slice(-this.TAIL);
    box.hidden = !tail.length;
    if (!tail.length) return;
    const more = all.length - tail.length;
    box.innerHTML =
      (more > 0 ? `<div class="home-more">${more} earlier — the whole conversation is on Chat</div>` : '') +
      tail.map(m => this.line(m)).join('');
    box.scrollTop = box.scrollHeight;
  },

  line(m) {
    if (m.who === 'him') return `<div class="home-said">${escHtml(m.text)}</div>`;
    const t = m.turn;
    if (m.live) return `<div class="home-heard live">${escHtml((t && t.answer) || '')}</div>`;
    if (t && t.waiting) {
      return `<div class="home-heard home-gate"><b>The council is asking</b>
        <div>${escHtml(t.waiting)}</div>
        <div class="muted">Answer it on Chat — the gate is yours.</div></div>`;
    }
    if (t && t.refusal && !t.answer) {
      return `<div class="home-heard home-bad"><b>REFUSED</b> ${escHtml(t.refusal)}</div>`;
    }
    // The failures go on the ANSWER's face, wherever the answer is shown.
    // An answer that ran on a broken tool says so here too, or this page is
    // lying by omission the way the old stat cards did.
    let foot = '';
    if (t) {
      const fails = Run.failures(t);
      if (fails.length) {
        foot += `<div class="home-bad-note"><b>NOT EVERYTHING RAN</b><br>${fails.map(escHtml).join('<br>')}</div>`;
      }
      foot += `<div class="home-said-meta">${escHtml(t.pipeline || 'default')} · ${escHtml(Run.elapsed(t))}</div>`;
    }
    return `<div class="home-heard">${escHtml((t && t.answer) || m.text || '')}${foot}</div>`;
  },

  // The dashboard's half of a turn: the answer as it streams, one line of what
  // is happening, and -- when it lands -- anything that FAILED, because an
  // answer that ran on a broken tool says so wherever it is shown (LAW 5).
  onRun(what) {
    // The guard names the element this handler actually writes into. It
    // named `home-out` after that element was replaced by the thread, so
    // every event returned here and no finished turn was ever attached:
    // the bubbles rendered empty while the answers streamed past.
    if (!document.getElementById('home-thread')) return;   // not the live page
    if (what === 'state') { this.paintEngine(); this.paint(); return; }
    if (what === 'start') {
      // A TURN THIS BROWSER DID NOT ASK FOR STILL NEEDS SOMEWHERE TO LAND.
      // The runner pushes its own pair into the thread in ask(); a window
      // MIRRORING a turn started elsewhere never did, so every event found no
      // live bubble and the page sat on "waiting for the engine" while the
      // answer streamed past it. Watching and running paint the same way; only
      // who created the bubble differs.
      if (Run.turn && Run.turn.watching &&
          !Chat.thread.some(m => m.live)) {
        Chat.thread.push({ who: 'him', text: Run.turn.objective || '' });
        Chat.thread.push({ who: 'council', text: '', live: true });
        this.thread();
      }
      this.block('starting...');
      this.tick(true);
      return;
    }
    if (what === 'event') {
      // Only the live bubble moves per event; rebuilding the tail on every
      // token would fight the scroll and re-render the whole conversation
      // hundreds of times in one turn.
      const live = document.querySelector('#home-thread .home-heard.live');
      if (live) live.textContent = Run.turn.answer || '';
      else this.thread();
      this.block(Run.nowLine() + ' \u00b7 ' + Run.elapsed());
      const box = document.getElementById('home-thread');
      if (box) box.scrollTop = box.scrollHeight;
      return;
    }
    if (what === 'end') {
      this.tick(false);
      // Chat owns the thread's entries; this marks the one it was streaming
      // into so both views agree the turn is over.
      const last = (Chat.thread || [])[Chat.thread.length - 1];
      if (last && last.who === 'council') { last.turn = Run.turn; last.live = false; }
      this.thread();
      this.block('');
      const input = document.getElementById('home-input');
      if (input) input.focus();      // the loop: he can answer without reaching
      // A turn can commit, or open a sitting, or close one, and it can turn a
      // suite green. The panels that read those follow it -- a score still
      // saying RED after the run that fixed it is the two halves disagreeing.
      // The repository card moved to Flows and is repainted there.
      App.paintProof('home-proof', 'scores');
      // `this.readSittings()` stood here and HAS NOT EXISTED SINCE a014c77,
      // the pass that took the sittings strip off this page at his markup --
      // the function went, the call stayed. Every turn since has thrown a
      // TypeError on this line, silently, killing the rest of the handler. It
      // cost nothing while it was the last statement; the moment anything was
      // added after it, that thing simply never ran. Which is exactly how the
      // kept conversation appeared to work and stored nothing.
      this.keepThread();
    }
  },

  // ---- THE CONVERSATION IS KEPT WHERE BOTH BROWSERS CAN READ IT ----------
  //
  // His ask was "keep the boot report AND THE RUN TURNS", and mirroring the
  // live events only did half of it: `Chat.thread` is in-memory per tab and
  // `Run.turn` is sessionStorage, which is also per tab. So a browser that
  // reloaded AFTER a turn showed an empty box -- engine card, nothing else --
  // and that is exactly how he was checking parity: "i have been reloading my
  // external browser tab every once in a while to watch and see if there is
  // parity between the two." There never could be. The mirror only ever showed
  // a turn that ran WHILE a tab was already open.
  //
  // WHAT IS KEPT IS WHAT RENDERS: who spoke and what was said. The events,
  // seats and tokens behind a turn stay in the transcript on disk, which is
  // the real record; putting them here would push a long run past the store
  // for nothing anyone reads twice.
  //
  // KEYED TO THE SESSION, like the boot report, so one engine's conversation
  // is never painted under another's.
  keepThread() {
    clearTimeout(this._threadSave);
    this._threadSave = setTimeout(() => {
      // A COUNCIL BUBBLE'S WORDS ARE IN `turn.answer`, NOT IN `text`. line()
      // renders from m.turn and leaves m.text empty, so a first cut filtered
      // on m.text and threw away every answer in the conversation -- keeping
      // only what HE typed, which is the half nobody needs kept.
      const said = (Chat.thread || [])
        .slice(-this.TAIL)
        .map(m => ({
          who: m.who,
          text: m.who === 'him' ? (m.text || '')
            : ((m.turn && (m.turn.answer || m.turn.refusal)) || m.text || '')
        }))
        .filter(m => m.text.trim());
      if (!said.length) return;
      API.setSetting('thread.' + (Run.world || 'research'),
        JSON.stringify({ session: Run.session || '', said })).catch(() => {});
    }, 600);
  },

  async showKeptThread() {
    if ((Chat.thread || []).length) return;      // this tab already has one
    try {
      const r = await API.getSetting('thread.' + (Run.world || 'research'));
      const kept = JSON.parse((r && r.value) || '{}');
      if (!kept.said || !kept.said.length) return;
      if (!Run.engineOpen || (kept.session && kept.session !== Run.session)) return;
      Chat.thread = kept.said.map(m => ({ who: m.who, text: m.text }));
      this.thread();
    } catch { /* nothing kept yet */ }
  },

  // The clock keeps moving while a seat thinks. Thinking is withheld from the
  // wire on purpose, so without this a working engine reads as a hung one.
  tick(on) {
    clearInterval(this._tick);
    this._tick = null;
    if (!on) return;
    this._tick = setInterval(() => {
      if (!Run.running || !document.getElementById('home-thread')) { this.tick(false); return; }
      this.block(Run.nowLine() + ' \u00b7 ' + Run.elapsed());
    }, 1000);
  },

  // Speak, and the words land IN THE BOX. He reads them, fixes whatever
  // whisper misheard, and presses Enter. Nothing is sent on his behalf.
  mic() {
    const btn = document.getElementById('home-mic');
    const input = document.getElementById('home-input');
    if (Run.listening) { Run.stopHearing(); this.block(''); btn.classList.remove('hot'); return; }
    if (!Run.engineOpen) { toast('No engine is open on this world', 'error'); return; }
    btn.classList.add('hot');
    this.block('opening the microphone...');
    Run.hear(
      (note) => this.block(note),
      (text) => {
        btn.classList.remove('hot');
        this.block('');
        input.value = (input.value ? input.value + ' ' : '') + text;
        input.focus();
        // The caret goes to the end so he can keep talking or keep typing.
        input.setSelectionRange(input.value.length, input.value.length);
      },
      (why) => { btn.classList.remove('hot'); this.block(why); toast(why, 'error'); });
  },

  // THE REPOSITORY MOVED TO FLOWS, 2026-09-10 ("this needs to go with the
  // other github stuff"). readGit, commit, push and the ask() that carried
  // them through the council went with it, whole -- Flows already held the
  // per-world overwatch, so the two git surfaces now sit on one page instead
  // of one per page.

  // THE SITTINGS, read from the record. Every one of them is a real sitting
  // with a toll owed or paid; a run of them with no toll is a thing he can
  // see rather than discover at a release gate.
  block(text) {
    const el = document.getElementById('home-block');
    if (!el) return;
    el.hidden = !text;
    el.textContent = text || '';
  },

  // The engine, as the door reports it -- never cached. A dashboard that
  // remembered "open" would keep saying so after a crash.
  paintEngine() {
    const box = document.getElementById('home-engine');
    const bar = document.getElementById('home-engine-controls');
    if (!box || !bar) return;
    const t = (iso) => { try { return new Date(iso).toLocaleTimeString(); } catch { return iso; } };

    if (Run.unreachable) {
      this.age(false);
      box.innerHTML = '<div class="eng-row eng-bad">The MCP door did not answer. ' +
        'Nothing can be opened or closed until it does.' +
        '<span class="brief-src">run/state</span></div>';
      bar.innerHTML = '';
      return;
    }
    if (!Run.engineOpen) {
      this.age(false);
      box.innerHTML = '<div class="eng-row eng-warn">No engine on <b>' +
        escHtml(Run.world || 'this world') + '</b>. Nothing will run until one is open. ' +
        'Booting starts a sitting; closing pays its toll.' +
        '<span class="brief-src">run/state</span></div>';
      bar.innerHTML = '<button class="btn btn-sm btn-primary" id="eng-boot">Boot</button>';
      document.getElementById('eng-boot').onclick = () => this.boot();
      return;
    }

    const rows = ['<div class="eng-row">Engine open on <b>' + escHtml(Run.world) +
      '</b> — sitting <b>' + escHtml(Run.sitting || '?') + '</b>' +
      (Run.session ? ' · session <code>' + escHtml(Run.session) + '</code>' : '') +
      (Run.started ? '<span class="muted"> · started ' + escHtml(t(Run.started)) +
        ' · <span id="eng-age"></span></span>' : '') +
      '<span class="brief-src">run/state</span></div>'];

    // AN ENGINE OPEN AND DOING NOTHING IS THE MOST EXPENSIVE THING IN THE
    // RECORD, and until now nothing on this page said so. Measured across
    // every sitting ever recorded: a standup gets 69 seconds of engine time
    // per run; sittings of two runs or fewer get 208, and there are 63 of
    // them -- 5.3 engine-hours for 91 runs. Twenty-two sittings were never
    // closed at all. Sitting 74 held an engine thirty minutes for 2 runs, 82
    // held one fifty-four minutes for 5, and 166 held one SIXTEEN MINUTES FOR
    // ZERO while the operator watched a hand do nothing with it.
    //
    // `started` was already on this card, as a fixed clock time -- a number
    // you have to subtract from to learn anything. The elapsed is the part a
    // person reads without doing arithmetic, so it ticks, and it turns amber
    // once an engine has been standing this long with no turn behind it.
    // His word: "we can just add that to the dashboard to view as tasks are
    // running in real time, right?"
    if (Run.started) this.age(true);

    // THE ROW THAT USED TO BE A SENTENCE IN A CHANGELOG. The engine runs
    // whatever manjuel/*.py said when it was spawned, and he no longer has a
    // REPL to restart. Seats, skills and pipelines hot-reload at the next turn
    // and are deliberately NOT counted here -- an alarm over a doc edit would
    // teach him to ignore the one row that matters.
    if (Run.stale) {
      rows.push('<div class="eng-row eng-warn">This engine is running code from before ' +
        'your last edit — <code>' + escHtml(Run.staleFile || 'manjuel') + '</code> changed at ' +
        escHtml(t(Run.codeChanged)) + ', and this process started at ' +
        escHtml(t(Run.started)) + '. Reboot to pick it up. ' +
        '<span class="muted">(Seats, skills and pipelines hot-reload; only code needs this.)</span>' +
        '<span class="brief-src">run/state</span></div>');
    }
    box.innerHTML = rows.join('');
    bar.innerHTML = '<button class="btn btn-sm" id="eng-close">Close sitting</button>' +
      '<button class="btn btn-sm ' + (Run.stale ? 'btn-primary' : '') + '" id="eng-boot">Reboot</button>';
    document.getElementById('eng-close').onclick = () => this.closeSitting();
    document.getElementById('eng-boot').onclick = () => this.boot();
  },

  // THE BOOT REPORT IS KEPT, AND KEPT WHERE BOTH BROWSERS CAN SEE IT.
  //
  // It used to live only in this <pre>, which render() rebuilds empty and
  // hidden on every navigation. Refresh the page and the report was gone --
  // the RECORD, the GATE, the RACK and VOICE, everything the boot actually
  // told you -- and the only way back was to reboot an engine that was working
  // perfectly well. His word: "keep the boot report ... i want to be able to
  // see it runing in sync on my chromium browser with your internal browser."
  //
  // SO IT GOES TO THE SERVER, NOT TO STORAGE. sessionStorage is per-tab and
  // localStorage is per-browser; neither can put two browsers on the same
  // page. The settings store is the one place both can read.
  //
  // KEYED TO THE SESSION, so a dead engine's boot log is never painted over a
  // live one. The engine that wrote it is named in the value, and a report
  // whose session does not match the engine standing now is discarded.
  bootLine(text, append) {
    const el = document.getElementById('home-boot');
    if (!el) return;
    el.hidden = false;
    el.textContent = append ? (el.textContent + text) : text;
    el.scrollTop = el.scrollHeight;
    this._boot = el.textContent;
    this.keepBoot();
  },

  // Written after the last line rather than on every one: a boot streams
  // dozens of lines and this must not become dozens of POSTs.
  keepBoot() {
    clearTimeout(this._bootSave);
    this._bootSave = setTimeout(() => {
      const text = this._boot || '';
      if (!text.trim()) return;
      API.setSetting('boot.' + (Run.world || 'research'),
        JSON.stringify({ session: Run.session || '', text })).catch(() => {});
    }, 800);
  },

  // Painted on arrival, so a refresh -- or a second browser opening the page
  // for the first time -- shows the report the engine actually gave.
  async showKeptBoot() {
    const el = document.getElementById('home-boot');
    if (!el || el.textContent.trim()) return;      // a live boot is streaming
    try {
      const r = await API.getSetting('boot.' + (Run.world || 'research'));
      const kept = JSON.parse((r && r.value) || '{}');
      if (!kept.text) return;
      // A report from an engine that is no longer standing is not the truth
      // about this one. Silence beats a stale wall of text.
      if (!Run.engineOpen || (kept.session && kept.session !== Run.session)) return;
      el.hidden = false;
      el.textContent = kept.text;
      el.scrollTop = el.scrollHeight;
      this._boot = kept.text;
    } catch { /* no report kept yet */ }
  },

  busy(on, what) {
    const bar = document.getElementById('home-engine-controls');
    if (bar) bar.querySelectorAll('button').forEach(b => { b.disabled = on; });
    if (what) this.bootLine(what + '\n', true);
  },

  // Closing is not a formality: it pays the toll and writes `ended`. A sitting
  // left open is exactly what makes the next open refuse, and a killed engine
  // is what leaves one open.
  async closeSitting() {
    this.busy(true, 'closing the sitting (the toll is paid, `ended` is written)...');
    try {
      this.bootLine(await App.tool('env_close', {}) + '\n', true);
    } catch (e) {
      this.bootLine('REFUSED: ' + e.message + '\n', true);
    }
    await Run.check();
    this.busy(false);
    this.paintEngine();
    this.paint();
  },

  // The boot, in the order the REPL does it. Each step shows its own words,
  // and a step that fails says so while the rest still runs -- boot.py's own
  // rule: "a boot report that vanishes when one thing is down is worse than
  // no boot report".
  async boot() {
    this.bootLine('', false);
    this.busy(true, '');
    if (Run.engineOpen) {
      this.bootLine('closing the open sitting first...\n', true);
      try { this.bootLine(await App.tool('env_close', {}) + '\n', true); }
      catch (e) { this.bootLine('close refused: ' + e.message + '\n', true); }
    }
    this.bootLine('\nopening a fresh engine...\n', true);
    try {
      this.bootLine(await App.tool('env_open', {}) + '\n', true);
    } catch (e) {
      this.bootLine('REFUSED: ' + e.message + '\n', true);
      await Run.check();
      this.busy(false);
      this.paintEngine();
      return;
    }
    await Run.check();
    this.paintEngine();
    this.paint();
    await this.bootStep('/warm', "\nloading this pipeline's models (/warm)...\n");
    await this.bootStep('/status', '\nthe boot report (/status)...\n');
    this.busy(false);
    await Run.check();
    this.paintEngine();
    this.paint();
  },

  // One /command through the council stream, its printed text shown as it
  // arrives. A command's output IS its text; its delivery carries nothing
  // extra worth repeating.
  bootStep(command, header) {
    return new Promise((done) => {
      this.bootLine(header, true);
      const es = new EventSource(API.base + '/council/stream?' +
                                 new URLSearchParams({ objective: command }));
      es.addEventListener('engine', (e) => {
        let d; try { d = JSON.parse(e.data); } catch { return; }
        if (d.event === 'text' || d.event === 'report') this.bootLine(d.text || '', true);
        if (d.event === 'error') this.bootLine('\n' + (d.text || '') + '\n', true);
      });
      es.addEventListener('stream_end', () => { es.close(); done(); });
      es.addEventListener('stream_error', (e) => {
        let d = {}; try { d = JSON.parse(e.data); } catch {}
        this.bootLine('\nREFUSED: ' + (d.error || 'the step was refused') + '\n', true);
        es.close(); done();
      });
      es.onerror = () => { es.close(); done(); };
    });
  },

  // ---- the brief ----------------------------------------------------------

  // Each fact is asked for on its own and is allowed to fail on its own. A
  // silent organ is REPORTED silent, never guessed at -- an unreachable rack
  // that renders as a green tick is worse than no dashboard.
  async read() {
    const ask = async (n, a) => {
      try { return await App.tool(n, a); }
      catch (e) { return { err: e.message || 'unreadable' }; }
    };
    const [state, muster, rack, proofs] = await Promise.all([
      Run.check().then(() => null).catch(() => null),
      ask('muster'),
      ask('rack_list'),
      ask('proofs')
    ]);
    void state;
    // proofs is asked for ONCE and kept. It carries four things -- the suites,
    // the standups, the parity runs and the record -- and this page used to
    // fetch the whole document twice and render only the record.
    let p = null;
    try { p = typeof proofs === 'string' ? JSON.parse(proofs) : null; } catch {}
    this.proofs = p;
    this.brief = { muster, rack };
    this.readAt = Date.now();       // stamped so the quiet line cannot lie
    this.paint();
    this.paintEngine();
    App.paintProof('home-proof', 'scores');
  },

  bad(v) { return v && typeof v === 'object'; },

  // A row is {tone, text, source}. Only rows that change the next move are
  // built; `ok` rows are collapsed into the single quiet line.
  rows() {
    const out = [];
    const b = this.brief || {};

    // 1. CAN I WORK -- ANSWERED BY THE CARD ABOVE, NOT HERE. The engine card
    // moved to the top of this page at his word, and it already says both
    // things this row used to: that the door is unreachable, or that no engine
    // is open, each with the Boot button beside it. Saying it again three
    // inches lower was the same duplication that came off the Chat header in
    // the same pass -- one fact printed twice, the smaller copy looking like a
    // second, separate fault.

    // 2. IS SOMETHING WAITING ON ME. Nothing on this page outranks it.
    if (Run.pending) {
      out.push({ tone: 'wait', source: 'run/state',
                 text: 'The council is asking: “' + Run.pending + '”', act: { label: 'Answer', to: 'chat' } });
    }
    if (Run.turn && Run.turn.waiting && !Run.running) {
      out.push({ tone: 'wait', source: 'the last run', text: 'A turn is paused on its gate.', act: { label: 'Answer', to: 'chat' } });
    }

    // 3. IS SOMETHING BROKEN. Only speaks when it is.
    if (this.bad(b.rack)) {
      out.push({ tone: 'bad', text: 'The rack could not be read: ' + b.rack.err, source: 'rack_list' });
    } else if (typeof b.rack === 'string' && /unreachable|refused|error/i.test(b.rack)) {
      out.push({ tone: 'bad', text: b.rack.split('\n')[0], source: 'rack_list' });
    }
    if (this.bad(b.muster)) {
      out.push({ tone: 'bad', text: 'The worlds could not be read: ' + b.muster.err, source: 'muster' });
    }

    // 4. DO THE PROOFS STILL HOLD. Silent when they do.
    out.push(...this.proofRows());
    return out;
  },

  // Epoch milliseconds, or null if the value cannot be read as a time. NULL IS
  // THE POINT: the two stamps compared below come from different clocks --
  // `at` is epoch SECONDS from the Python suites, `code_changed` is an RFC3339
  // STRING from Go -- and a guard that quietly coerced a bad one would date a
  // live proof to 1970 and cry stale forever. Unreadable means silent.
  ms(v) {
    if (v == null || v === '') return null;
    if (typeof v === 'number') {
      if (!isFinite(v) || v <= 0) return null;
      return v > 1e12 ? v : v * 1000;      // ms already, or seconds
    }
    if (typeof v === 'string') {
      const t = Date.parse(v);
      return isFinite(t) ? t : null;
    }
    return null;
  },

  // The suites and the standup, read from what `proofs` already served. A row
  // appears only when it changes the next move.
  proofRows() {
    const out = [];
    const p = this.proofs;
    if (!p) return out;

    if (p.suites_error) {
      out.push({ tone: 'warn', source: 'tests/last_run.json',
                 text: 'The suites have left no verdict on disk: ' + p.suites_error });
    }

    const suites = p.suites || {};
    let newest = null;
    for (const name of Object.keys(suites)) {
      const r = suites[name] || {};
      const at = this.ms(r.at);
      if (at != null && (newest == null || at > newest)) newest = at;

      if (r.green === false || (r.state && r.state !== 'finished')) {
        const failed = Array.isArray(r.failures) ? r.failures : [];
        const first = failed.length ? String(failed[0]) : '';
        out.push({
          tone: 'bad', source: 'tests/last_run.json',
          text: (r.state && r.state !== 'finished')
            ? 'The ' + name + ' suite did not finish — it stopped at ' +
              (r.passed != null ? r.passed : '?') + ' of ' + (r.total != null ? r.total : '?') + '.'
            : ((r.total - r.passed) || failed.length || '?') + ' of ' + r.total + ' ' + name +
              ' failed' + (first ? ': ' + first : '') + '.',
          act: { label: 'Evals', to: 'evals' }
        });
      }
    }

    // THE PROOF PREDATES THE CODE. Same reasoning the engine's own stale row
    // uses, and skipped outright if either clock is unreadable.
    const changed = this.ms(Run.codeChanged);
    if (newest != null && changed != null && changed > newest && !out.length) {
      out.push({
        tone: 'warn', source: 'tests/last_run.json',
        text: 'The suites were last proven ' + when(newest) + ', and ' +
              (Run.staleFile || 'the core') + ' changed at ' + when(changed) +
              '. That verdict is about code the disk no longer holds.'
      });
    }

    // The standup he runs himself. Newest line wins; never run is not a fault.
    const runs = Array.isArray(p.standups) ? p.standups : [];
    const last = runs.length ? runs[runs.length - 1] : null;
    if (last && (last.green === false || (last.state && last.state !== 'finished'))) {
      const failed = Array.isArray(last.failed) ? last.failed : [];
      out.push({
        tone: 'bad', source: last.report || 'tests/run_history.jsonl',
        text: 'The last standup failed ' + when(last.at) + ' — ' +
              (last.passed != null ? last.passed : '?') + ' of ' +
              (last.total != null ? last.total : '?') + ' held' +
              (failed.length ? ', starting with ' + String(failed[0]) : '') + '.'
      });
    }
    return out;
  },

  paint() {
    const box = document.getElementById('home-brief');
    if (!box) return;
    const rows = this.rows();
    const sub = document.getElementById('home-sub');

    // A PAGE SHOWING OLD BYTES SAYS SO, on every path. Judged before either
    // branch below, because what he read off the stale glass was a ROW -- an
    // engine card an hour out of date -- and a confession that only fired on
    // the quiet line would have missed it completely. The stale rows still
    // render: old facts plus "these are old" beats hiding them, since half of
    // them are still true and this way he can see which.
    if (this.readAt && Date.now() - this.readAt > 60000) {
      rows.unshift({
        tone: 'warn', source: 'last read',
        text: 'Nothing has been read since ' + when(this.readAt) +
              '. Everything below is that old.'
      });
    }

    if (!rows.length) {
      // GREEN IS SILENCE: one line, and it names where it read that from.
      const worlds = this.bad(this.brief.muster) ? '' :
        (this.brief.muster || '').split('\n').slice(1).map(s => s.trim()).filter(Boolean).length;
      if (sub) sub.textContent = 'Nothing is waiting on you.';
      box.className = 'card home-brief quiet';
      // IT SAYS WHAT IS TRUE, not one fixed sentence. This line hardcoded
      // "engine open on X" and only ever ran while one WAS open, because the
      // no-engine row above used to stop the page reaching it. That row moved
      // to the engine card this pass, and the first paint afterwards read
      // "The estate is standing. engine open on research, sitting —" with no
      // engine open at all -- the exact class of lie this whole page was just
      // fixed for.
      const eng = Run.engineOpen
        ? `engine open on <b>${escHtml(Run.world || '—')}</b>, sitting ${escHtml(Run.sitting || '—')}`
        : 'no engine open — see the card above';
      box.innerHTML = `<div class="brief-ok">The estate is standing.
        <span class="muted">${eng}${worlds ? ` · ${worlds} worlds carried` : ''}</span>
        <span class="brief-src">run/state · muster</span></div>`;
      return;
    }

    if (sub) sub.textContent = rows.some(r => r.tone === 'wait')
      ? 'Something is waiting on you.' : 'Something needs looking at.';
    box.className = 'card home-brief';
    box.innerHTML = rows.map(r => `
      <div class="brief-row brief-${r.tone}">
        <div class="brief-text">${escHtml(r.text)}</div>
        <div class="brief-side">
          ${r.act && r.act.to === 'engine' ? `<button class="btn btn-sm btn-primary" data-boot="1">${escHtml(r.act.label)}</button>` : ''}
          ${r.act && r.act.to && r.act.to !== 'engine' ? `<button class="btn btn-sm" data-goto="${r.act.to}">${escHtml(r.act.label)}</button>` : ''}
          ${r.act && r.act.hint ? `<code>${escHtml(r.act.hint)}</code>` : ''}
          <span class="brief-src">${escHtml(r.source)}</span>
        </div>
      </div>`).join('');
    box.querySelectorAll('[data-boot]').forEach(btn => { btn.onclick = () => this.boot(); });
    box.querySelectorAll('[data-goto]').forEach(btn => {
      btn.onclick = () => { history.pushState(null, '', '/' + btn.dataset.goto); App.router(); };
    });
  },

  // ---- recent ----------------------------------------------------------
  // MOVED TO VERSION CONTROL, 2026-09-10, at the operator's word -- it sat
  // under the repository card and went with it. It still reads Chat's own
  // thread, so the two pages cannot disagree about what was said.

};
