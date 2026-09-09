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

  async render(el) {
    this.el = el;
    el.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">What are we working on?</div>
          <div class="page-subtitle" id="home-sub">Reading the record...</div>
        </div>
      </div>

      <div class="card home-box">
        <form id="home-form" class="chat-form">
          <input id="home-input" class="input home-input" type="text" autocomplete="off"
                 placeholder="Say what you want done..." />
          <button class="btn btn-primary" type="submit" id="home-go">Run</button>
        </form>
        <div id="home-block" class="home-block" hidden></div>
      </div>

      <div id="home-brief" class="card home-brief"></div>

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

    this.paintRecent();
    await this.read();
  },

  // ---- the launch ---------------------------------------------------------

  // He types here and lands in the conversation. The turn starts from Home so
  // the launchpad is not a door he passes through empty-handed.
  go() {
    const input = document.getElementById('home-input');
    const q = input.value.trim();
    if (!q) return;
    if (!Run.engineOpen) { toast('No engine is open on this world', 'error'); return; }
    input.value = '';
    Chat.thread.push({ who: 'him', text: q });
    Chat.thread.push({ who: 'council', text: '', live: true });
    Run.start({ objective: q });
    history.pushState(null, '', '/chat');
    App.router();
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
        text: 'No engine is open' + (Run.world ? ' on ' + Run.world : '') + ', so nothing typed above will run. ' +
              'This page will not open one for you — that would start a sitting you never started.',
        act: { label: 'How', hint: 'env_open' }
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
          ${r.act && r.act.to ? `<button class="btn btn-sm" data-goto="${r.act.to}">${escHtml(r.act.label)}</button>` : ''}
          ${r.act && r.act.hint ? `<code>${escHtml(r.act.hint)}</code>` : ''}
          <span class="brief-src">${escHtml(r.source)}</span>
        </div>
      </div>`).join('');
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
