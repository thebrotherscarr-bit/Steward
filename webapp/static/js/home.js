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
  recent: [],

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

      <div class="card home-box">
        <div id="home-thread" class="home-thread" hidden></div>
        <form id="home-form" class="chat-form">
          <button class="btn btn-mic" type="button" id="home-mic" title="Speak (local whisper, nothing leaves this machine)">&#127908;</button>
          <input id="home-input" class="input home-input" type="text" autocomplete="off"
                 placeholder="Say what you want done..." />
          <button class="btn btn-primary" type="submit" id="home-go">Run</button>
        </form>
        <div id="home-block" class="home-block" hidden></div>
      </div>

      <div id="home-brief" class="card home-brief"></div>

      <div class="card" id="home-git-card" hidden>
        <div class="card-header">
          <span class="card-title">The repository</span>
          <span class="flex" id="home-git-controls"></span>
        </div>
        <div id="home-git"></div>
      </div>

      <div class="card" id="home-sittings-card" hidden>
        <div class="card-title">Recent sittings</div>
        <div id="home-sittings"></div>
      </div>

      <div class="card" id="home-engine-card">
        <div class="card-header">
          <span class="card-title">The engine</span>
          <span class="flex" id="home-engine-controls"></span>
        </div>
        <div id="home-engine"></div>
        <pre id="home-boot" class="home-boot" hidden></pre>
      </div>

      <div class="card" id="home-recent-card" hidden>
        <div class="card-title">Recent</div>
        <div id="home-recent"></div>
      </div>`;

    const form = document.getElementById('home-form');
    const input = document.getElementById('home-input');
    form.onsubmit = (e) => { e.preventDefault(); this.go(); };
    // Enter runs. A form's implicit submit is not reliable in every host.
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.go(); }
    });
    input.focus();
    document.getElementById('home-mic').onclick = () => this.mic();
    // The thread renders before anything is asked, so a conversation
    // survives navigating away and back.
    this.thread();

    this.paintRecent();
    await this.read();
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
      this.paintRecent();
      // A turn can commit, or open a sitting, or close one. The panels that
      // read those follow it -- a repository card still saying "2 changed"
      // after the commit it just watched is the two halves disagreeing again.
      this.readGit();
      this.readSittings();
    }
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

  // THE REPOSITORY, as it stands now. Read by the door, not the engine: "is
  // my tree dirty" is what he asks BEFORE deciding to boot anything, and a
  // panel that needs an engine to answer it cannot answer it.
  async readGit() {
    const card = document.getElementById('home-git-card');
    const box = document.getElementById('home-git');
    const bar = document.getElementById('home-git-controls');
    if (!card || !box) return;
    let g;
    try { g = JSON.parse(await App.tool('git', {})); }
    catch (e) {
      card.hidden = false;
      box.innerHTML = `<div class="eng-row eng-bad">git could not be read:
        ${escHtml(e.message || 'refused')}<span class="brief-src">git</span></div>`;
      return;
    }
    this._git = g;
    card.hidden = false;

    if (!g.is_repo) {
      box.innerHTML = `<div class="eng-row">${escHtml(g.note || 'not a repository')}
        <span class="brief-src">git</span></div>`;
      bar.innerHTML = '';
      return;
    }

    const rows = [];
    // GREEN IS SILENCE: clean and level is one line.
    if (!g.dirty && !g.ahead) {
      rows.push(`<div class="eng-row"><b>${escHtml(g.branch || '?')}</b>
        <code>${escHtml(g.head || '')}</code> — clean${g.upstream ? ', level with <code>' +
        escHtml(g.upstream) + '</code>' : ''}
        <span class="muted"> · ${escHtml(g.subject || '')} (${escHtml(g.when || '')})</span>
        <span class="brief-src">git</span></div>`);
    } else {
      if (g.dirty) {
        rows.push(`<div class="eng-row eng-warn"><b>${g.changed} changed, ${g.untracked} untracked</b>
          on ${escHtml(g.branch || '?')} — uncommitted work
          <div class="git-files">${(g.files || []).map(escHtml).join('<br>')}</div>
          <span class="brief-src">git</span></div>`);
      }
      if (g.ahead) {
        rows.push(`<div class="eng-row eng-warn">${g.ahead} commit${g.ahead === 1 ? '' : 's'}
          ahead of <code>${escHtml(g.upstream || 'the remote')}</code> — landed locally, not pushed
          <span class="brief-src">git</span></div>`);
      }
      if (g.behind) {
        rows.push(`<div class="eng-row eng-warn">${g.behind} behind <code>${escHtml(g.upstream)}</code>
          <span class="brief-src">git</span></div>`);
      }
    }
    // THE WALL, named precisely. Being walled and being unauthenticated are
    // different problems with the same symptom, and telling them apart is the
    // difference between "set a flag" and "your credentials broke".
    if (!g.remote_allowed) {
      rows.push(`<div class="eng-row"><span class="muted">${escHtml(g.remote_note || '')}
        This is the estate's own wall, not a credentials problem.</span>
        <span class="brief-src">gitstate.py</span></div>`);
    }
    box.innerHTML = rows.join('');

    bar.innerHTML = `<input id="git-msg" class="input git-msg" type="text"
        placeholder="what changed (optional — the council writes one if you don't)" />
      <button class="btn btn-sm ${g.dirty ? 'btn-primary' : ''}" id="git-commit"
        ${g.dirty ? '' : 'disabled'}>Commit</button>
      <button class="btn btn-sm" id="git-push"
        ${g.remote_allowed && g.ahead ? '' : 'disabled'}>Push</button>`;
    document.getElementById('git-commit').onclick = () => this.commit();
    const push = document.getElementById('git-push');
    push.title = !g.remote_allowed
      ? 'remote operations are walled by MANJUEL_GIT_REMOTE (the estate, not your credentials)'
      : (g.ahead ? 'push ' + g.ahead + ' commit(s) to ' + (g.upstream || 'the remote')
                 : 'nothing to push');
    push.onclick = () => this.push();
  },

  // Through the council, never around it: the law gate stamps it, the Router
  // runs git_commit, and the run lands in the record like any other turn. A
  // button that shelled out to git would be a second write-path past
  // everything this estate checks.
  commit() {
    // HIS OWN PHRASING, from the record: "git commit" appears 36 times in
    // sessions.jsonl and the estate composes the message from what changed.
    // The first wrapper here read "Commit the working tree with this message:
    // X" and the Router passed that WHOLE SENTENCE as the message -- a commit
    // titled after its own instruction. A quoted message reads the way he
    // types one, and an empty field falls back to what already works.
    const msg = (document.getElementById('git-msg') || {}).value || '';
    this.ask(msg.trim() ? `git commit: "${msg.trim()}"` : 'git commit');
  },

  push() {
    const g = this._git || {};
    if (!g.remote_allowed) {
      toast('Remote operations are walled by MANJUEL_GIT_REMOTE', 'error');
      return;
    }
    this.ask('Push the committed work to the remote.');
  },

  // One objective, into the same loop as anything he types.
  ask(objective) {
    if (!Run.engineOpen) { toast('No engine is open — boot first', 'error'); return; }
    if (Run.running) { toast('A turn is already running', 'error'); return; }
    Chat.thread.push({ who: 'him', text: objective });
    Chat.thread.push({ who: 'council', text: '', live: true });
    this.thread();
    Run.start({ objective });
  },

  // THE SITTINGS, read from the record. Every one of them is a real sitting
  // with a toll owed or paid; a run of them with no toll is a thing he can
  // see rather than discover at a release gate.
  async readSittings() {
    const card = document.getElementById('home-sittings-card');
    const box = document.getElementById('home-sittings');
    if (!card || !box) return;
    let p;
    try { p = JSON.parse(await App.tool('proofs', {})); }
    catch { return; }
    const rc = (p && p.record) || {};
    const rows = (rc.recent || []).slice(-6).reverse();
    if (!rows.length) return;
    card.hidden = false;
    box.innerHTML = `<div class="sit-head">${rc.sittings} sittings · ${rc.tolled} tolled ·
        ${rc.runs} runs${rc.still_open ? ' · <span class="tool-bad">' + rc.still_open +
        ' never closed</span>' : ''}<span class="brief-src">sessions/sessions.jsonl</span></div>` +
      rows.map(r => `<div class="sit-row">
        <span class="sit-n">${escHtml(String(r.n))}</span>
        <span class="muted">${escHtml(String(r.started || '').replace('T', ' '))}</span>
        <span>${escHtml(String(r.runs))} runs</span>
        <span>${r.ended ? (r.toll_paid ? '<span class="badge badge-green">tolled</span>'
                                       : '<span class="badge badge-yellow">no toll</span>')
                        : '<span class="tool-bad">still open</span>'}</span></div>`).join('');
  },

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
      box.innerHTML = '<div class="eng-row eng-bad">The MCP door did not answer. ' +
        'Nothing can be opened or closed until it does.' +
        '<span class="brief-src">run/state</span></div>';
      bar.innerHTML = '';
      return;
    }
    if (!Run.engineOpen) {
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
      (Run.started ? '<span class="muted"> · started ' + escHtml(t(Run.started)) + '</span>' : '') +
      '<span class="brief-src">run/state</span></div>'];

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

  bootLine(text, append) {
    const el = document.getElementById('home-boot');
    if (!el) return;
    el.hidden = false;
    el.textContent = append ? (el.textContent + text) : text;
    el.scrollTop = el.scrollHeight;
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
    const [state, muster, rack] = await Promise.all([
      Run.check().then(() => null).catch(() => null),
      ask('muster'),
      ask('rack_list')
    ]);
    void state;
    this.brief = { muster, rack };
    this.paint();
    this.paintEngine();
    this.readGit();
    this.readSittings();
  },

  bad(v) { return v && typeof v === 'object'; },

  // A row is {tone, text, source}. Only rows that change the next move are
  // built; `ok` rows are collapsed into the single quiet line.
  rows() {
    const out = [];
    const b = this.brief || {};

    // 1. CAN I WORK. This one gates everything else on the page.
    if (Run.unreachable) {
      out.push({ tone: 'bad', text: 'The MCP door did not answer. Nothing here can run until it does.', source: 'run/state' });
    } else if (!Run.engineOpen) {
      out.push({
        tone: 'warn', source: 'run/state',
        // The Boot button below now DOES open one. What still holds is the
        // part that matters: nothing opens BY ITSELF. Opening starts a
        // sitting, and a sitting nobody meant to start is what every
        // refusal in this system guards against.
        text: 'No engine is open' + (Run.world ? ' on ' + Run.world : '') + ', so nothing typed above will run. ' +
              'Booting starts a sitting; nothing opens one on its own.',
        act: { label: 'Boot', to: 'engine' }
      });
    }

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
    return out;
  },

  paint() {
    const box = document.getElementById('home-brief');
    if (!box) return;
    const rows = this.rows();
    const sub = document.getElementById('home-sub');

    if (!rows.length) {
      // GREEN IS SILENCE: one line, and it names where it read that from.
      const worlds = this.bad(this.brief.muster) ? '' :
        (this.brief.muster || '').split('\n').slice(1).map(s => s.trim()).filter(Boolean).length;
      if (sub) sub.textContent = 'Nothing is waiting on you.';
      box.className = 'card home-brief quiet';
      box.innerHTML = `<div class="brief-ok">The estate is standing.
        <span class="muted">engine open on <b>${escHtml(Run.world || '—')}</b>, sitting ${escHtml(Run.sitting || '—')}${worlds ? ` · ${worlds} worlds carried` : ''}</span>
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

  // ---- recent -------------------------------------------------------------

  // Read off Chat's own thread, so it cannot disagree with what he can scroll
  // back and read for himself.
  paintRecent() {
    const said = (Chat.thread || []).filter(m => m.who === 'him').slice(-5).reverse();
    const card = document.getElementById('home-recent-card');
    const box = document.getElementById('home-recent');
    if (!card || !box) return;
    card.hidden = !said.length;
    box.innerHTML = said.map(m => `
      <div class="home-recent-row" data-say="${escHtml(m.text)}">
        <span class="home-recent-text">${escHtml(m.text)}</span>
      </div>`).join('');
    box.querySelectorAll('[data-say]').forEach(r => {
      r.onclick = () => {
        const i = document.getElementById('home-input');
        i.value = r.dataset.say;
        i.focus();
      };
    });
  }
};
