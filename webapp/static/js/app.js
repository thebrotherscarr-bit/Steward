// ATLAS App — SPA router and pages
const App = {
  currentPage: 'dashboard',
  data: {},

  init() {
    this.router();
    window.addEventListener('popstate', () => this.router());
    document.querySelectorAll('.nav-link').forEach(a => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        history.pushState(null, '', a.href);
        this.router();
      });
    });
    this.loadHealth();
    // Ctrl+K / Cmd+K, anywhere. The one global key this console binds.
    Palette.bind();
    this.bindSidebar();
    this.paintBadges();
    API.sse((e) => this.onEvent(e));
    // Every page follows a turn started in another browser, not just the
    // one that asked for it. Idempotent: mirror() returns at once if it is
    // already listening.
    Run.mirror();
  },

  router() {
    const path = location.pathname.slice(1) || 'dashboard';
    const parts = path.split('/');
    this.currentPage = parts[0];
    this.pageParam = parts[1] || null;
    document.querySelectorAll('.nav-link').forEach(a => {
      a.classList.toggle('active', a.dataset.page === this.currentPage);
    });
    this.paintCrumb();
    this.render();
  },

  // THE CRUMB SAYS THE ESTATE AND THE PAGE, AND STOPS -- unless the path
  // really is deeper, which is the only case where a third step is a fact
  // rather than furniture. The page's NAME comes off the nav link itself, so
  // a label renamed in the panel (Flows -> Version control, 2026-09-10) is
  // renamed here in the same stroke and cannot drift.
  paintCrumb() {
    const el = document.getElementById('crumb');
    if (!el) return;
    const link = document.querySelector(`.nav-link[data-page="${this.currentPage}"]`);
    // A page off the panel (traces, messages, playground) still routes, so it
    // still gets a crumb -- titled from the path when the nav has no line.
    const name = link
      ? (link.childNodes[0].textContent || '').trim()
      : this.currentPage.charAt(0).toUpperCase() + this.currentPage.slice(1);
    const home = this.currentPage === 'dashboard';
    const parts = [`<a href="/" onclick="event.preventDefault();history.pushState(null,'','/');App.router();">ATLAS</a>`];
    if (!home) {
      parts.push('<span class="sep">/</span>');
      if (this.pageParam) {
        const back = '/' + this.currentPage;
        parts.push(`<a href="${back}" onclick="event.preventDefault();history.pushState(null,'','${back}');App.router();">${escHtml(name)}</a>`);
        parts.push('<span class="sep">/</span>');
        parts.push(`<span class="here">${escHtml(decodeURIComponent(this.pageParam))}</span>`);
      } else {
        parts.push(`<span class="here">${escHtml(name)}</span>`);
      }
    }
    el.innerHTML = parts.join('');
    el.hidden = home;
  },

  // The two buttons above the nav. The primary one is context-aware, and it
  // reads Run's LIVE state each time rather than a remembered one -- a button
  // offering to close a sitting that already closed is the class of lie this
  // console keeps removing.
  bindSidebar() {
    const search = document.getElementById('side-search');
    if (search) search.onclick = () => Palette.show();
    const prim = document.getElementById('side-primary');
    if (prim) prim.onclick = () => {
      history.pushState(null, '', '/');
      this.router();
      setTimeout(() => (Run.engineOpen ? Home.closeSitting() : Home.boot()), 60);
    };
    // Repainted on every run event, because a turn can open or close a sitting
    // and the button must not go on offering the thing that already happened.
    if (!this._sideBound) {
      this._sideBound = true;
      Run.on(() => this.paintSidebar());
    }
    this.paintSidebar();
  },

  paintSidebar() {
    const prim = document.getElementById('side-primary');
    if (!prim) return;
    prim.textContent = Run.engineOpen ? 'Close the sitting' : 'Boot an engine';
    prim.title = Run.engineOpen
      ? 'pays its toll and reaps the engine · sitting ' + (Run.sitting || '?')
      : 'opens a sitting on ' + (Run.world || 'this world');
  },

  // A BADGE IS A NUMBER THE RECORD CAN PROVE. Each is read from the tool that
  // owns it and stays hidden until that tool answers; a count this page worked
  // out for itself would be the same fault the dashboard carried until P0-11.
  // Each is allowed to fail on its own -- one silent tool must not blank three
  // true numbers.
  async paintBadges() {
    const put = (page, text, warn) => {
      const el = document.getElementById('badge-' + page);
      if (!el) return;
      if (text == null) { el.hidden = true; return; }
      el.textContent = String(text);
      el.className = 'nav-badge' + (warn ? ' warn' : '');
      el.hidden = false;
    };
    const quiet = async (fn) => { try { return await fn(); } catch { return null; } };

    put('agents', await quiet(async () => {
      const d = JSON.parse(await this.tool('seats', {}));
      return (d.seats || []).length || null;
    }));
    put('records', await quiet(async () => {
      const d = JSON.parse(await this.tool('records', {}));
      return d.count || null;
    }));
    put('tools', await quiet(async () => {
      const r = await API.tools();
      return (r.tools || []).length || null;
    }));
    // UNSENT WORK IS A WARNING, not a tally: it is the one number here that
    // means something is OWED rather than something exists.
    //
    // ACROSS EVERY CARRIED WORLD, because that is what the page it badges
    // shows. A first cut read the default world alone and said 2 while atlas
    // sat clean beside it -- a true number about one world, standing in for
    // two, which is the shape of every wrong count this console has removed.
    await this.paintOwed();
  },

  // THE OWED BADGE ON ITS OWN, because it is the only one an act on Version
  // control can change, and repainting all four costs six tool calls in a row
  // — long enough that the panel visibly kept the old number for several
  // seconds after a save. Same shape as paintProof(box, only).
  async paintOwed() {
    const el = document.getElementById('badge-flows');
    if (!el) return;
    let owed = null;
    try {
      const m = await this.tool('muster', {});
      const worlds = (m || '').split(String.fromCharCode(10))
        .map(s => s.trim()).filter(s => s && !s.endsWith(':'));
      let n = 0;
      for (const w of worlds) {
        try {
          const g = JSON.parse(await this.tool('git', { project: w }));
          if (g.is_repo) n += (g.changed || 0) + (g.untracked || 0) + (g.ahead || 0);
        } catch { /* one unreadable world must not blank the others */ }
      }
      owed = n;
    } catch { owed = null; }
    if (!owed) { el.hidden = true; return; }
    el.textContent = String(owed);
    el.className = 'nav-badge warn';
    el.hidden = false;
  },

  async loadHealth() {
    try {
      const h = await API.health();
      document.getElementById('version').textContent = h.version;
      document.getElementById('operator-status').textContent = 'active';
      document.getElementById('status-dot').className = 'status-dot green';
    } catch {
      document.getElementById('operator-status').textContent = 'offline';
      document.getElementById('status-dot').className = 'status-dot red';
    }
    setTimeout(() => this.loadHealth(), 5000);
  },

  onEvent(e) {
    if (e.type === 'trace_added') toast('New trace recorded');
    if (e.type === 'eval_added') toast('New eval recorded');
    if (e.type === 'message_sent') toast('Message sent');
    if (e.type === 'message_received') {
      toast('Message received');
      if (this.currentPage === 'messages') this.render();
    }
    if (e.type === 'chat_opened') toast('Chat session opened');
    if (e.type === 'chat_done') toast('Chat turn witnessed');
    if (e.type === 'prompt_saved') toast('Prompt version folded');
    if (e.type === 'prompt_ran') toast('Prompt measured');
    if (e.type === 'prompt_evaled') toast('Eval scored');
    if (e.type === 'flow_saved') toast('Flow version folded');
    if (e.type === 'flow_ran') toast('Flow fired');
    if (e.type === 'flow_resumed') toast('Flow moved by the hand');
  },

  async render() {
    const el = document.getElementById('content');
    switch (this.currentPage) {
      // The launchpad (home.js). renderDashboard below is the old estate
      // readout -- kept whole, no longer routed, until he says its fate.
      case 'dashboard': await Home.render(el); break;
      case 'agents': this.pageParam ? await this.renderAgentDetail(el) : await this.renderAgents(el); break;
      case 'traces': this.pageParam ? await this.renderTraceDetail(el) : await this.renderTraces(el); break;
      case 'tools': await this.renderTools(el); break;
      case 'evals': await this.renderEvals(el); break;
      case 'records': await this.renderRecords(el); break;
      case 'chat': await Chat.render(el); break;
      case 'playground': await Play.render(el); break;
      case 'flows': await Flows.render(el); break;
      // The DAG builder, back on the panel 2026-09-11 at his word. It is a
      // SEPARATE page from Version control on purpose: /flows is the git
      // overwatch he uses every day, and taking that route back would cost
      // him the one he actually stands on.
      case 'workflows': await Workflows.render(el); break;
      case 'messages': await this.renderMessages(el); break;
      case 'settings': await this.renderSettings(el); break;
      default: el.innerHTML = '<div class="empty"><div class="empty-icon">?</div><div class="empty-text">Page not found</div></div>';
    }
  },

  // === DASHBOARD ===
  // Every row on this page names the tool it was read from. A number the
  // record cannot prove is not shown -- SPEC 3 invariant 10, and the reason
  // this page used to read Agents 0 / Traces 0 / Evals 0 on a full estate:
  // it was counting its own store instead of asking the record (P0-11).
  async tool(name, args) {
    const r = await API.callTool(name, args || {});
    try {
      const env = JSON.parse(r.output);
      if (env.error) throw new Error(env.error.message || 'refused');
      const c = env.result && env.result.content;
      const text = c && c[0] ? c[0].text : '';
      if (env.result && env.result.isError) throw new Error(text || 'refused');
      return text;
    } catch (e) { throw new Error(e.message || 'unreadable answer'); }
  },

  async renderDashboard(el) {
    el.innerHTML = '<div class="loading">Reading the record...</div>';

    // Ask the record. Each one is allowed to fail on its own; a silent organ
    // is reported silent, never guessed at.
    const ask = async (n, a) => { try { return await this.tool(n, a); }
                                  catch (e) { return { err: e.message }; } };
    const [muster, rack, matrix, tenants, health] = await Promise.all([
      ask('muster'), ask('rack_list'), ask('state_matrix'), ask('tenant_list'),
      API.health().catch(() => null)
    ]);

    const bad = v => v && typeof v === 'object';
    const worlds = bad(muster) ? [] :
      muster.split('\n').slice(1).map(l => l.trim()).filter(Boolean);

    // the rack, parsed into its own tiers -- the ladder the card actually holds
    const tiers = [];
    if (!bad(rack)) {
      let cur = null;
      for (const line of rack.split('\n')) {
        let m = /^\s{2}(\S+) \(([^)]+)\):/.exec(line);
        if (m) { cur = { name: m[1], cap: m[2], voices: [] }; tiers.push(cur); continue; }
        m = /^\s{4}- (\S+) · ([0-9.]+)GB · (\S+)/.exec(line);
        if (m && cur) cur.voices.push({ tag: m[1], gb: parseFloat(m[2]), family: m[3] });
      }
    }
    const voiceCount = tiers.reduce((a, t) => a + t.voices.length, 0);
    const biggest = Math.max(1, ...tiers.flatMap(t => t.voices.map(v => v.gb)));

    // open mode is not a state to report calmly: it means RBAC allows all
    const openMode = !bad(tenants) && /open mode/.test(tenants);
    const rackOut = bad(rack) || /nothing fabricated/.test(rack);

    const organ = (name, ok, said, src) => `
      <div class="organ${ok === false ? ' organ-bad' : ok === null ? ' organ-quiet' : ''}">
        <div class="organ-name">${name}</div>
        <div class="organ-said">${said}</div>
        <div class="organ-src"><code>${src}</code></div>
      </div>`;

    const standing = rackOut
      ? 'The estate holds its record, but no voice can answer.'
      : 'The estate is standing.';

    el.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">${standing}</div>
          <div class="page-subtitle">Read from the record just now. Every line below names where it came from.</div>
        </div>
        <div class="flex"><button class="btn" id="dash-again">Read it again</button></div>
      </div>

      <div class="organs">
        ${organ('Ground', worlds.length > 0,
            worlds.length ? worlds.join(', ') + ` carried` : 'no project carried',
            'muster')}
        ${organ('Rack', !rackOut,
            rackOut ? 'unreachable — start <code>ollama serve</code>'
                    : `${voiceCount} local voices across ${tiers.length} tiers, loopback only`,
            'rack_list')}
        ${organ('Record', !bad(matrix),
            bad(matrix) ? matrix.err
              : (matrix.match(/\b(road|state|log)\s+(\d+) bytes/g) || ['nothing folded'])
                  .map(x => x.replace(/\s+/, ' ')).join(' · '),
            'state_matrix')}
        ${organ('Access', !openMode,
            bad(tenants) ? tenants.err
              : openMode
                ? 'a carried project is in <b>open mode</b> — every tool allowed to anyone'
                : tenants.split('\n').slice(1).map(l => l.trim()).join(' · '),
            'tenant_list')}
        ${organ('Door', true,
            `${(await API.tools().catch(() => ({tools:[]}))).tools.length} tools, no forbidden verb among them`,
            'tools/list')}
        ${organ('Gate', true,
            'can_approve is false in every declaration — approval is your hand alone',
            'by construction')}
      </div>

      ${rackOut ? '' : `
      <div class="card mt-16">
        <div class="card-header"><span class="card-title">The rack</span>
          <span class="muted">what one card can hold, largest ${biggest.toFixed(1)}GB</span></div>
        <div class="ladder">
          ${tiers.map(t => `
            <div class="rung">
              <div class="rung-name">${escHtml(t.name)}<span class="muted"> ${escHtml(t.cap)}</span></div>
              <div class="rung-voices">
                ${t.voices.map(v => `
                  <div class="voice">
                    <div class="voice-bar" style="width:${Math.max(4,(v.gb/biggest)*100)}%"></div>
                    <div class="voice-tag">${escHtml(v.tag)}</div>
                    <div class="voice-gb">${v.gb.toFixed(1)}GB</div>
                  </div>`).join('')}
              </div>
            </div>`).join('')}
        </div>
      </div>`}

      <div class="card mt-16">
        <div class="card-header"><span class="card-title">Not shown, and why</span></div>
        <div class="notshown">
          <div>Runs, seats and quality checks are the chain's record, and THE LINE
          has no tool that reads them yet (<code>env_*</code>, <code>run_*</code>).
          This page used to show counts from the webapp's own store instead —
          four zeros on a full estate. It shows nothing rather than something
          it cannot source.</div>
          ${health ? `<div class="muted">Version ${escHtml(health.version)} · glass on :8091 · line on :8090</div>` : ''}
        </div>
      </div>`;

    document.getElementById('dash-again').onclick = () => this.renderDashboard(el);
  },

  // === AGENTS ===
  // THE SEATS, read from agents/*.md and pipelines.md -- the source of truth.
  // This page listed the webapp's own SQLite table, which nothing writes, on a
  // ground holding fourteen declared seats. Third instance of that fault today
  // and the last page carrying it.
  async renderAgents(el) {
    el.innerHTML = '<div class="loading">Reading the seats...</div>';
    let d;
    try {
      d = JSON.parse(await this.tool('seats', {}));
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div>
        <div class="empty-text">The seats could not be read: ${escHtml(e.message || 'refused')}</div></div>`;
      return;
    }
    const seats = d.seats || [];
    this._seats = seats;

    // Which pipelines exist at all, so a seat that stands in none is visibly
    // a racked seat rather than an omission.
    const pipes = [];
    for (const s of seats) for (const st of (s.stands_in || [])) {
      if (pipes.indexOf(st.pipeline) < 0) pipes.push(st.pipeline);
    }

    el.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">Seats</div>
          <div class="page-subtitle">${seats.length} declared in <code>agents/</code> ·
            ${pipes.length} pipelines in <code>pipelines.md</code></div>
        </div>
        <div class="search-bar">
          <input class="input" placeholder="Search seats..." oninput="App.filterAgents(this.value)">
        </div>
      </div>
      ${d.seats_error ? `<div class="card"><div class="eng-row eng-bad">
        agents/ could not be read: ${escHtml(d.seats_error)}
        <span class="brief-src">seats</span></div></div>` : ''}
      <div id="agent-grid">${seats.map((s, i) => this.seatCard(s, i)).join('')}</div>`;

    el.querySelectorAll('[data-prompt]').forEach(b => {
      b.onclick = () => {
        const box = document.getElementById('prompt-' + b.dataset.prompt);
        if (box) { box.hidden = !box.hidden; b.textContent = box.hidden ? 'prompt' : 'hide prompt'; }
      };
    });
  },

  seatCard(s, i) {
    if (s.error) {
      return `<div class="card seat-card"><div class="eng-row eng-bad">
        <b>${escHtml(s.file)}</b> could not be read: ${escHtml(s.error)}</div></div>`;
    }
    const f = s.fields || {};
    const order = s.field_order || Object.keys(f);
    // The model and the gate lead, because they are what he tunes.
    const lead = ['Model Target', 'Stage', 'When', 'Wakes On', 'Wakes'];
    const rest = order.filter(k => lead.indexOf(k) < 0 && (f[k] || '').trim());

    const stands = (s.stands_in || []).map(st =>
      `<span class="badge badge-blue" title="${escHtml(st.note || '')}">${escHtml(st.pipeline)}
       <span class="muted">#${st.step}</span>${st.when ? ' · ' + escHtml(st.when) : ''}</span>`).join(' ');

    // THE NAME IS THE WAY IN. /agents/<file stem> existed for months with
    // nothing on this page pointing at it, which is most of why it was left
    // reading a table nobody writes: a route nobody can reach is a route
    // nobody notices is broken.
    const stem = String(s.file || '').replace(/\.md$/i, '');
    return `<div class="card seat-card" data-seat="${escHtml((s.name || '').toLowerCase())}">
      <div class="card-header">
        <a class="card-title seat-open" href="/agents/${escHtml(stem)}"
           title="The declaration whole, with the file and its receipt"
           onclick="event.preventDefault();history.pushState(null,'','/agents/${escHtml(stem)}');App.router();">${escHtml(s.name)}</a>
        <span class="flex">
          ${f['Model Target'] ? `<code class="seat-model">${escHtml(f['Model Target'])}</code>` : ''}
          ${s.prompt ? `<button class="btn btn-sm" data-prompt="${i}">prompt</button>` : ''}
        </span>
      </div>
      <div class="seat-rows">
        ${lead.filter(k => (f[k] || '').trim()).map(k =>
          `<div class="seat-row"><span class="seat-k">${escHtml(k)}</span>
           <span class="seat-v">${escHtml(f[k])}</span></div>`).join('')}
        ${rest.map(k =>
          `<div class="seat-row"><span class="seat-k">${escHtml(k)}</span>
           <span class="seat-v muted">${escHtml(f[k])}</span></div>`).join('')}
      </div>
      <div class="seat-stands">
        ${stands || '<span class="muted">stands in no pipeline — racked, summoned when its flag is raised</span>'}
        <span class="brief-src">${escHtml(s.file)}</span>
      </div>
      ${s.prompt ? `<pre class="seat-prompt" id="prompt-${i}" hidden>${escHtml(s.prompt)}</pre>` : ''}
    </div>`;
  },

  filterAgents(q) {
    q = (q || '').trim().toLowerCase();
    document.querySelectorAll('#agent-grid .seat-card').forEach(c => {
      const hay = (c.dataset.seat || '') + ' ' + c.textContent.toLowerCase();
      c.hidden = q !== '' && hay.indexOf(q) < 0;
    });
  },

  // ONE SEAT, WHOLE. Reached by clicking its name on /agents.
  //
  // THIS ROUTE WAS AN ORPHAN AND A LIE. Nothing on the seats page linked to
  // it, so the only way in was to type the URL -- and when you did, it read
  // `API.getAgent`, which queries the WEBAPP'S OWN SQLite `agents` table.
  // Nothing writes that table. The list beside it reads agents/*.md through
  // the `seats` tool, so a ground with fourteen declared seats answered 404
  // for every one of them, and the fields it was built to show (office,
  // reports_to, mode, permissions) do not exist in a declaration at all.
  // Fourth instance of a page counting the webapp's store instead of asking
  // the record, and the last one standing.
  //
  // THE KEY IS THE FILE STEM, not a name. `deep_researcher` is stable,
  // unique, url-safe and is already what the record calls the document;
  // a display name ("Deep Researcher") is none of those.
  //
  // WHAT THE DETAIL ADDS over the card: the declaration in full with nothing
  // folded, the system prompt open rather than behind a toggle, and THE FILE
  // ITSELF with its sha256 -- served by `records`, the same receipt the
  // Records page hands out. The card is the summary; this is the document.
  async renderAgentDetail(el) {
    el.innerHTML = '<div class="loading">Reading the seat...</div>';
    const stem = String(this.pageParam || '');
    let seats;
    try {
      seats = (JSON.parse(await this.tool('seats', {})).seats) || [];
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div>
        <div class="empty-text">The seats could not be read: ${escHtml(e.message || 'refused')}</div></div>`;
      return;
    }
    const stemOf = (f) => String(f || '').replace(/\.md$/i, '');
    const s = seats.find(x => stemOf(x.file) === stem);
    if (!s) {
      // AN ABSENT NAME IS DENIED HONESTLY, and the denial names what IS here.
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div>
        <div class="empty-text">No seat is declared as <code>${escHtml(stem)}.md</code> in
        <code>agents/</code>. The ${seats.length} that are:
        ${seats.map(x => `<a href="/agents/${escHtml(stemOf(x.file))}"
          onclick="event.preventDefault();history.pushState(null,'','/agents/${escHtml(stemOf(x.file))}');App.router();"><code>${escHtml(stemOf(x.file))}</code></a>`).join(' ')}
        </div></div>`;
      return;
    }

    const f = s.fields || {};
    const order = s.field_order || Object.keys(f);
    const rows = order.filter(k => (f[k] || '').trim() && k !== 'System Prompt')
      .map(k => `<tr><td>${escHtml(k)}</td><td>${escHtml(f[k])}</td></tr>`).join('');
    const stands = (s.stands_in || []).map(st =>
      `<div class="seat-row"><span class="seat-k">${escHtml(st.pipeline)}
        <span class="muted">step ${escHtml(String(st.step))}</span></span>
       <span class="seat-v">${escHtml(st.when || st.note || '')}</span></div>`).join('');

    el.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">${escHtml(s.name || stem)}</div>
          <div class="page-subtitle">Declared in <code>agents/${escHtml(s.file)}</code>${
            f['Model Target'] ? ` · runs on <code>${escHtml(f['Model Target'])}</code>` : ''}</div>
        </div>
        <a href="/agents" class="btn" onclick="event.preventDefault();history.pushState(null,'','/agents');App.router();">All seats</a>
      </div>
      <div class="grid-2">
        <div class="card">
          <div class="card-header"><span class="card-title">The declaration</span></div>
          ${rows ? `<div class="table-wrap"><table>${rows}</table></div>`
                 : '<div class="empty-text">This declaration carries no fields.</div>'}
          <div class="brief-src">seats · agents/${escHtml(s.file)}</div>
        </div>
        <div class="card">
          <div class="card-header"><span class="card-title">Where it stands</span>
            <span class="badge badge-blue">${(s.stands_in || []).length}</span></div>
          ${stands || `<div class="empty-text">Stands in no pipeline — racked, and
            summoned only when its flag is raised.</div>`}
          <div class="brief-src">pipelines.md</div>
        </div>
      </div>
      <div class="card mt-16">
        <div class="card-header"><span class="card-title">System prompt</span>
          <span class="muted">${s.prompt_chars || (s.prompt || '').length} characters</span></div>
        ${s.prompt ? `<pre class="seat-prompt">${escHtml(s.prompt)}</pre>`
                   : `<div class="empty-text">No system prompt is declared. The seat runs on
                      the pipeline's own framing.</div>`}
      </div>
      <div class="card mt-16" id="seat-file"><div class="loading">Reading the file...</div></div>`;

    // THE DOCUMENT ITSELF, with the receipt. Asked for separately so a seat
    // still renders whole when the records hold cannot serve the file.
    const box = document.getElementById('seat-file');
    try {
      const d = JSON.parse(await this.tool('records', { name: 'agents/' + s.file }));
      box.innerHTML = `<div class="card-header"><span class="card-title">The file, as it is on disk</span>
          <span class="muted">${d.bytes} bytes</span></div>
        <pre class="seat-prompt">${escHtml(d.text || '')}</pre>
        <div class="brief-src">records · sha256 ${escHtml(String(d.sha256 || '').slice(0, 16))}</div>`;
    } catch (e) {
      box.innerHTML = `<div class="eng-row eng-warn">The file could not be served:
        ${escHtml(e.message || 'refused')}<span class="brief-src">records</span></div>`;
    }
  },

  // === TRACES ===
  async renderTraces(el) {
    el.innerHTML = '<div class="loading">Loading traces...</div>';
    try {
      const data = await API.listTraces();
      const traces = data.traces || [];
      el.innerHTML = `
        <div class="page-header">
          <div>
            <div class="page-title">Trace Log</div>
            <div class="page-subtitle">${traces.length} traces recorded</div>
          </div>
          <div class="search-bar">
            <input class="input" placeholder="Filter traces..." oninput="App.filterTraces(this.value)">
          </div>
        </div>
        <div class="card">
          ${traces.length === 0
            ? '<div class="empty"><div class="empty-icon">&#128269;</div><div class="empty-text">No traces yet. Call a tool from the Tools page to start recording.</div></div>'
            : '<div class="table-wrap"><table><thead><tr><th>Tool</th><th>Agent</th><th>Status</th><th>Duration</th><th>Hash</th><th>Time</th></tr></thead><tbody>' +
              traces.map(t => `
                <tr onclick="location.href='/traces/${t.id}'" style="cursor:pointer">
                  <td><code>${escHtml(t.tool)}</code></td>
                  <td>${escHtml(t.agent_id || '—')}</td>
                  <td><span class="badge ${t.status === 'ok' ? 'badge-green' : 'badge-red'}">${escHtml(t.status)}</span></td>
                  <td>${t.duration_ms}ms</td>
                  <td><span class="hash">${escHtml((t.hash || '').slice(0, 16))}...</span></td>
                  <td>${timeAgo(t.created_at)}</td>
                </tr>
              `).join('') +
              '</tbody></table></div>'}
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>`;
    }
  },

  filterTraces(q) {
    q = q.toLowerCase();
    document.querySelectorAll('tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  },

  async renderTraceDetail(el) {
    el.innerHTML = '<div class="loading">Loading trace...</div>';
    try {
      const data = await API.getTrace(this.pageParam);
      const t = data.trace;
      const evals = data.evals || [];
      el.innerHTML = `
        <div class="page-header">
          <div>
            <div class="page-title">Trace: ${escHtml(t.tool)}</div>
            <div class="page-subtitle">${escHtml(t.id)}</div>
          </div>
          <a href="/traces" class="btn" onclick="event.preventDefault();history.pushState(null,'','/traces');App.router();">Back</a>
        </div>
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><span class="card-title">Trace Details</span></div>
            <table>
              <tr><td>Tool</td><td><code>${escHtml(t.tool)}</code></td></tr>
              <tr><td>Agent</td><td>${escHtml(t.agent_id || '—')}</td></tr>
              <tr><td>Status</td><td><span class="badge ${t.status === 'ok' ? 'badge-green' : 'badge-red'}">${escHtml(t.status)}</span></td></tr>
              <tr><td>Duration</td><td>${t.duration_ms}ms</td></tr>
              <tr><td>Time</td><td>${new Date(t.created_at).toLocaleString()}</td></tr>
              <tr><td>Hash</td><td><span class="hash">${escHtml(t.hash || '—')}</span></td></tr>
            </table>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Input / Output</span></div>
            <div class="form-group"><div class="form-label">Input</div><pre style="font-size:12px;color:var(--text-2);background:var(--bg);padding:12px;border-radius:var(--radius);overflow-x:auto;max-height:200px">${escHtml(t.input || '—')}</pre></div>
            <div class="form-group"><div class="form-label">Output</div><pre style="font-size:12px;color:var(--text-2);background:var(--bg);padding:12px;border-radius:var(--radius);overflow-x:auto;max-height:200px">${escHtml(t.output || '—')}</pre></div>
          </div>
        </div>
        <div class="card mt-16">
          <div class="card-header">
            <span class="card-title">Evals</span>
            <button class="btn btn-sm" onclick="App.addEval('${t.id}')">+ Add Eval</button>
          </div>
          ${evals.length === 0
            ? '<div class="empty"><div class="empty-text">No evals for this trace.</div></div>'
            : '<div class="table-wrap"><table><thead><tr><th>Name</th><th>Score</th><th>Passed</th><th>Detail</th></tr></thead><tbody>' +
              evals.map(e => `
                <tr>
                  <td>${escHtml(e.name)}</td>
                  <td><span class="eval-score ${e.passed ? 'pass' : 'fail'}">${e.score}</span></td>
                  <td><span class="badge ${e.passed ? 'badge-green' : 'badge-red'}">${e.passed ? 'PASS' : 'FAIL'}</span></td>
                  <td>${escHtml(e.detail || '—')}</td>
                </tr>
              `).join('') + '</tbody></table></div>'}
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>`;
    }
  },

  async addEval(traceId) {
    const name = prompt('Eval name:');
    if (!name) return;
    const score = parseFloat(prompt('Score (0-1):') || '0');
    let threshold = 0.5;
    try {
      const s = await API.getSetting('eval_threshold');
      if (s.value) threshold = parseFloat(s.value);
    } catch {}
    const passed = score >= threshold;
    const detail = prompt('Detail (optional):') || '';
    try {
      await API.addEval({ id: 'e-' + Date.now(), trace_id: traceId, name, score, passed, detail });
      toast('Eval added');
      this.router();
    } catch (e) { toast(e.message, 'error'); }
  },

  // === TOOLS ===
  async renderTools(el) {
    el.innerHTML = '<div class="loading">Loading tools...</div>';
    try {
      const data = await API.tools();
      const tools = data.tools || [];
      el.innerHTML = `
        <div class="page-header">
          <div>
            <div class="page-title">Tool Surface</div>
            <div class="page-subtitle">${tools.length} tools registered</div>
          </div>
        </div>
        <div class="card">
          <div class="table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Description</th><th>Arguments</th><th>Action</th></tr></thead>
              <tbody>
                ${tools.map(t => `
                  <tr>
                    <td><code>${escHtml(t.name)}</code></td>
                    <td>${escHtml(t.description || '—')}</td>
                    <td><code>${Object.keys(t.inputSchema?.properties || {}).join(', ') || 'none'}</code></td>
                    <td><button class="btn btn-sm btn-primary" onclick="App.invokeTool('${escHtml(t.name)}')">Call</button></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>`;
    }
  },

  async invokeTool(name) {
    const argsStr = prompt(`Arguments for ${name} (JSON):`, '{}');
    if (!argsStr) return;
    let args;
    try { args = JSON.parse(argsStr); } catch { toast('Invalid JSON', 'error'); return; }
    const modal = document.getElementById('modal');
    const content = document.getElementById('modal-content');
    content.innerHTML = `<div class="loading">Calling ${escHtml(name)}...</div>`;
    modal.style.display = 'flex';
    try {
      const result = await API.callTool(name, args);
      content.innerHTML = `
        <h3 style="margin-bottom:12px">Tool Result: <code>${escHtml(name)}</code></h3>
        <div class="form-group"><div class="form-label">Output</div><pre style="font-size:12px;background:var(--bg);padding:12px;border-radius:var(--radius);max-height:300px;overflow:auto">${escHtml(result.output || '')}</pre></div>
        <div class="form-group"><div class="form-label">Hash</div><span class="hash">${escHtml(result.hash || '')}</span></div>
        <div class="flex-between mt-16">
          <span style="font-size:12px;color:var(--text-3)">Trace: ${escHtml(result.trace_id || '')} — ${result.duration_ms || 0}ms</span>
          <button class="btn" onclick="App.closeModal()">Close</button>
        </div>
      `;
    } catch (e) {
      content.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>
        <button class="btn mt-16" onclick="App.closeModal()">Close</button>`;
    }
  },

  closeModal() {
    document.getElementById('modal').style.display = 'none';
  },

  // === EVALS ===
  // === EVALS: the run, then the judgements on it ===
  //
  // The waterfall lives HERE, not on Chat (the operator, 2026-09-09: "this
  // looks like the evals loops. lets put it there"). Chat is the conversation;
  // this page is the evidence -- every seat, every tool, every result, the
  // per-seat table and the transcript, live while a turn runs and kept after
  // it ends. It reads Run (council.js), the same object Chat reads, so the two
  // pages can never tell different stories about the same turn.
  //
  // NOTHING ON THIS PAGE IS INFERRED. Each row is an event the engine emitted.
  // `failed` is the engine's own field, the per-seat numbers are its
  // StepResults -- never a reading of what a seat said about itself (LAW 5).
  async renderEvals(el) {
    el.innerHTML = '<div class="loading">Loading evals...</div>';
    if (!this._runBound) { Run.on(() => this.paintRun()); this._runBound = true; }
    try {
      const data = await API.listEvals();
      const evals = data.evals || [];
      const passed = evals.filter(e => e.passed).length;
      const failed = evals.length - passed;
      el.innerHTML = `
        <div class="page-header">
          <div>
            <div class="page-title">Evaluations</div>
            <div class="page-subtitle">${evals.length} scored evals, ${passed} passed, ${failed} failed. The last run, whole, is on the <a href="/" onclick="event.preventDefault();history.pushState(null,'','/');App.router();">Dashboard</a>; the suites, standups and sittings are on <a href="/records" onclick="event.preventDefault();history.pushState(null,'','/records');App.router();">Records</a>.</div>
          </div>
          <!-- #ev-run-state and #ev-run-cancel WERE HERE and were dead. The
               run card moved to the Dashboard on 2026-09-10 and took the
               ev-run element with it; paintRun returns at its first line when
               that element is
               absent, so this badge was never painted once. It sat in the
               header of every visit showing a hardcoded em dash — a control
               that looks like a reading and is a literal. -->
        </div>
        <div class="card">
          <div class="card-title">Scored evals <span class="muted">— written by the Add-an-eval flow, not by the suites</span></div>
          ${evals.length === 0
            ? '<div class="empty-text">None scored yet. The suites and standups are on <a href="/records" onclick="event.preventDefault();history.pushState(null,&#39;&#39;,&#39;/records&#39;);App.router();">Records</a>, read from the record; this table is what someone scored by hand from a trace.</div>'
            : '<div class="table-wrap"><table><thead><tr><th>Name</th><th>Trace</th><th>Score</th><th>Passed</th><th>Detail</th><th>Time</th></tr></thead><tbody>' +
              evals.map(e => `
                <tr>
                  <td>${escHtml(e.name)}</td>
                  <td><code style="cursor:pointer" onclick="location.href='/traces/${e.trace_id}'">${escHtml(e.trace_id)}</code></td>
                  <td><span class="eval-score ${e.passed ? 'pass' : 'fail'}">${e.score}</span></td>
                  <td><span class="badge ${e.passed ? 'badge-green' : 'badge-red'}">${e.passed ? 'PASS' : 'FAIL'}</span></td>
                  <td>${escHtml(e.detail || '—')}</td>
                  <td>${timeAgo(e.created_at)}</td>
                </tr>
              `).join('') + '</tbody></table></div>'}
        </div>
      `;
      const c = document.getElementById('ev-run-cancel');
      if (c) c.onclick = () => Run.cancel();
      this.paintRun();
      Run.check();
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>`;
    }
  },

  // paintRun draws the whole turn from Run's kept events. It redraws on every
  // event rather than appending, so a page opened halfway through a run shows
  // everything that already happened instead of only the rest.
  paintRun() {
    const box = document.getElementById('ev-run');
    if (!box) return;
    const t = Run.turn;
    const badge = document.getElementById('ev-run-state');
    const cancel = document.getElementById('ev-run-cancel');
    if (badge) {
      badge.className = 'badge ' + (Run.running ? 'badge-blue' : t ? 'badge-green' : '');
      badge.textContent = Run.running ? 'running · ' + Run.elapsed()
        : t ? (t.verdict || 'done') + ' · ' + Run.elapsed()
        : (Run.engineOpen ? 'engine open · sitting ' + (Run.sitting || '?') : 'no engine');
    }
    if (cancel) cancel.hidden = !Run.running;

    if (!t) {
      box.innerHTML = '<div class="empty-text">No run yet. Say something on Chat and the whole turn lands here.</div>';
      return;
    }
    const rows = [`<div class="cev cev-obj">${escHtml(t.objective)}</div>`];
    if (t.thinned) rows.push(`<div class="cev cev-fail"><b>the events were not kept</b> — this turn came back from storage without its record; the delivery below is whole, the step-by-step is not</div>`);
    for (const ev of t.events) rows.push(this.runRow(ev));
    if (t.refusal) rows.push(`<div class="cev cev-fail"><b>${escHtml((t.verdict || 'refused').toUpperCase())}</b> ${escHtml(t.refusal)}</div>`);
    if (t.dropped) rows.push(`<div class="cev cev-fail"><b>${t.dropped} events were dropped</b> — this page did not see everything that ran</div>`);
    box.innerHTML = rows.join('');
    box.scrollTop = box.scrollHeight;
  },

  // One event, one row. An event this build has never heard of is shown
  // verbatim rather than dropped: an unknown event is still something that
  // happened, and on this page an omission looks like nothing happening.
  runRow(d) {
    const k = d._kind;
    switch (k) {
      case 'opened':
        return `<div class="cev cev-meta"><b>opened</b> sitting ${escHtml(String(d.sitting ?? ''))} · session ${escHtml(d.session || '')}</div>`;
      case 'run':
        return `<div class="cev cev-meta"><b>run</b> pipeline <b>${escHtml(d.pipeline || '')}</b>` +
          (d.review_only ? ' · review only' : '') +
          (d.feed_chars ? ` · feed ${d.feed_chars} chars` : '') +
          (d.transcript ? `<br><span class="muted">transcript <code>${escHtml(d.transcript)}</code></span>` : '') + `</div>`;
      case 'report':
        return `<div class="cev cev-report">${escHtml((d.text || '').trim())}</div>`;
      case 'seat':
        return `<div class="cev cev-seat"><b>${escHtml(d.seat || 'seat')}</b> <span class="muted">${escHtml(d.model || '')}` +
          (d.timeout ? ` · timeout ${d.timeout}s` : '') + `</span></div>`;
      case 'token':
        return '';   // the seat's words are shown whole under its delivery
      case 'tool':
        return `<div class="cev cev-tool"><b>skill</b> ${escHtml(d.action || d.tool || d.name || '?')}` +
          (d.seat ? ` <span class="muted">called by ${escHtml(d.seat)}</span>` : '') +
          (d.args ? ` <code>${escHtml(JSON.stringify(d.args)).slice(0, 200)}</code>` : '') + `</div>`;
      case 'tool_result':
        return `<div class="cev ${d.failed ? 'cev-fail' : 'cev-ok'}"><b>${d.failed ? 'FAILED' : 'ok'}</b> ` +
          escHtml(d.action || d.tool || d.name || '?') +
          (d.error ? ` — ${escHtml(d.error)}` : '') +
          (d.failed && d.text ? ` — ${escHtml(String(d.text).slice(0, 300))}` : '') + `</div>`;
      case 'note':
        return `<div class="cev cev-note"><b>note</b> ${escHtml(d.text || '')}</div>`;
      case 'needs_answer':
        return `<div class="cev cev-gate"><b>THE COUNCIL IS ASKING</b><div class="cev-prompt">${escHtml(d.prompt || '')}</div>` +
          `<span class="muted">answered on Chat — the gate is the operator's (RULE 6)</span></div>`;
      case 'delivery':
        return this.runDelivery(d);
      case 'refused': case 'aborted': case 'cancelled': case 'unreachable': case 'error':
        return `<div class="cev cev-fail"><b>${escHtml(k.toUpperCase())}</b> ${escHtml(d.text || d.error || '')}</div>`;
      case 'closed':
        return `<div class="cev cev-meta"><b>closed</b> ${escHtml(d.text || 'the sitting is tolled')}</div>`;
      default:
        return `<div class="cev cev-other"><b>${escHtml(String(k))}</b> <code>${escHtml(JSON.stringify(d)).slice(0, 400)}</code></div>`;
    }
  },

  runDelivery(d) {
    const list = (a) => (a || []).map(f => escHtml(typeof f === 'string' ? f : JSON.stringify(f))).join('<br>');
    let extra = '';
    if ((d.failures || []).length) {
      extra += `<div class="cev-notrun"><b>NOT EVERYTHING RAN</b><br>${list(d.failures)}
        <br><span class="muted">machine-emitted from what happened, not a seat's account of it</span></div>`;
    }
    if ((d.out_of_time || []).length) extra += `<div class="cev-notrun"><b>OUT OF TIME</b><br>${list(d.out_of_time)}</div>`;
    if ((d.notes || []).length) extra += `<div class="muted" style="margin-top:6px">${list(d.notes)}</div>`;
    // Which calls FAILED, off the engine's own tool_result field -- never a
    // reading of the words that came back.
    const failed = {};
    for (const x of (Run.turn && Run.turn.tools) || []) {
      if (x.failed) failed[x.name] = x.error || 'failed';
    }
    const named = (list) => {
      const names = (list || []).filter(Boolean);
      if (!names.length) return '<span class="muted">—</span>';
      return names.map(n => failed[n]
        ? `<span class="tool-bad" title="${escHtml(failed[n])}">${escHtml(n)}</span>`
        : `<span class="tool-ok">${escHtml(n)}</span>`).join(' ');
    };
    const steps = (d.steps || []).map(s =>
      `<tr><td>${escHtml(String(s.seat || ''))}</td>
       <td class="muted">${escHtml(String(s.model || ''))}</td>
       <td>${escHtml(String(s.elapsed ?? ''))}s</td>
       <td>${named(s.tools)}</td>
       <td>${s.drift == null ? '<span class="muted" title="not scored this run">—</span>'
              : '<span class="' + (s.drifted ? 'tool-bad' : '') + '">' + escHtml(Number(s.drift).toFixed(2)) + '</span>'}</td>
       <td>${s.skipped ? '<span class="badge badge-yellow">skipped</span>'
              : s.error ? '<span class="badge badge-red">error</span>'
                        : '<span class="badge badge-green">ran</span>'}</td></tr>`).join('');

    // THE ROLL-UP. The per-seat rows answer "who called what"; this answers
    // "what did this run touch", which is the question an eval asks. A skill
    // and a tool are the same thing in this estate -- the 37 skills ARE the
    // tool surface -- so it is said once here rather than implied as two lists.
    const used = [];
    for (const s of (d.steps || [])) for (const n of (s.tools || [])) {
      if (n && used.indexOf(n) < 0) used.push(n);
    }
    for (const x of (Run.turn && Run.turn.tools) || []) {
      if (x.name && used.indexOf(x.name) < 0) used.push(x.name);
    }
    const roll = used.length
      ? `<div class="cev-skills"><b>skills used</b> ${named(used)}
         <span class="muted">· a skill and a tool are one thing here; the estate's skills are its tool surface</span></div>`
      : `<div class="cev-skills"><b>skills used</b> <span class="muted">none — the seats answered from what they were handed</span></div>`;

    return `<div class="cev cev-delivery"><b>DELIVERY</b> ${escHtml(d.pipeline || '')}` +
      (d.elapsed != null ? ' · ' + escHtml(String(d.elapsed)) + 's' : '') +
      `<div class="cev-text">${escHtml(d.text || '')}</div>${extra}` + roll +
      (steps ? `<table class="cev-steps"><thead><tr><th>seat</th><th>model</th><th>elapsed</th><th>tools</th><th>drift</th><th></th></tr></thead><tbody>${steps}</tbody></table>` : '') +
      (d.transcript ? `<div class="muted" style="margin-top:6px">transcript <code>${escHtml(d.transcript)}</code></div>` : '') +
      `</div>`;
  },


  // WHAT THIS WORLD HAS PROVED, read from its own record and nowhere else.
  // Every card names the file it came from; a world that never ran a suite
  // says so rather than rendering as a zero, because "zero passed" and "never
  // run" are opposite claims.
  // Paints into whichever box it is given -- it lived on Evals, then Records,
  // and the scores now open the Dashboard. The id is the caller's business.
  //
  // `only` SPLITS THE TWO HALVES, because they answer different questions and
  // they belong on different pages now (the operator, 2026-09-10): the SCORES
  // are "is the build sound", which is the first thing the Dashboard should
  // say; the ESTATE is "what has sat here", which is the record and stays on
  // Records. One reader, one `proofs` call, two placements.
  //   'scores' -- strokes, smoke, standup, standups run, parity
  //   'estate' -- sittings, tolls, runs, and the live standups table
  //   omitted  -- both, as before
  async paintProof(boxId, only) {
    const box = document.getElementById(boxId || 'rec-proof');
    if (!box) return;
    box.innerHTML = '<div class="loading">Reading the record...</div>';
    let p;
    try {
      p = JSON.parse(await this.tool('proofs', {}));
    } catch (e) {
      box.innerHTML = `<div class="card"><div class="eng-row eng-bad">
        The record could not be read: ${escHtml(e.message || 'refused')}
        <span class="brief-src">proofs</span></div></div>`;
      return;
    }

    const cards = [];
    // `delta` is OPTIONAL and is only ever passed where the record holds a
    // previous value to compare against. A card with nothing to compare shows
    // no delta rather than a zero -- "unchanged" and "never measured twice"
    // are different claims, and the second is the true one here.
    const card = (label, value, tone, note, src, delta) => cards.push(
      `<div class="stat">
         <div class="stat-head">
           <div class="stat-label">${escHtml(label)}</div>
           ${delta ? `<span class="stat-delta ${delta.dir}">${escHtml(delta.text)}</span>` : ''}
         </div>
         <div class="stat-value ${tone || ''}">${value}</div>
         ${note ? `<div class="stat-note">${note}</div>` : ''}
         <div class="brief-src">${escHtml(src)}</div></div>`);

    // ---- the suites, as they stamped themselves ----------------------
    const su = p.suites || {};
    for (const name of ['strokes', 'smoke']) {
      const r = su[name];
      if (!r) {
        card(name, '<span class="muted">never run</span>', '', p.suites_error || 'no stamp in this world', 'tests/last_run.json');
        continue;
      }
      card(name, `${r.passed}<span class="muted">/${r.total}</span>`,
           r.green ? 'green' : 'red',
           r.green ? 'green · ' + when(r.at) : 'RED · ' + ((r.failures || []).join(', ') || 'see the run'),
           'tests/last_run.json');
    }

    // ---- the live standups -------------------------------------------
    const runs = p.standups || [];
    if (!runs.length) {
      card('standup', '<span class="muted">never run live</span>', '',
           p.standups_error || 'a dry run does not count', 'tests/run_history.jsonl');
    } else {
      const last = runs[runs.length - 1];
      const greens = runs.filter(r => r.green).length;
      // THE ONE HONEST DELTA IN THIS CONSOLE. run_history.jsonl holds every
      // prior live run, so the move from the previous one is read, not
      // guessed. Nothing else here has a second measurement to compare
      // against, so nothing else gets a delta.
      let move = null;
      if (runs.length > 1) {
        const prev = runs[runs.length - 2];
        const d = (last.passed || 0) - (prev.passed || 0);
        if (d !== 0) move = { dir: d > 0 ? 'up' : 'down',
                              text: (d > 0 ? '+' : '') + d + ' vs last' };
      }
      card('standup', `${last.passed}<span class="muted">/${last.total}</span>`,
           last.green ? 'green' : 'red',
           (last.green ? 'green' : 'RED — ' + ((last.failed || []).join(', ') || '?')) +
           ' · ' + when(last.at), 'tests/run_history.jsonl', move);
      card('standups run', `${greens}<span class="muted">/${runs.length}</span>`,
           greens === runs.length ? 'green' : 'yellow',
           'green of all live runs on record', 'tests/run_history.jsonl');
    }

    // ---- parity -------------------------------------------------------
    const par = p.parity || [];
    if (!par.length) {
      card('parity', '<span class="muted">never run</span>', '',
           p.parity_error || 'chain vs bare calls, per case', 'sessions/parity_history.jsonl');
    } else {
      const lp = par[par.length - 1];
      card('parity', String(lp.mean ?? '—'), 'blue',
           `${lp.scored ?? '?'} of ${lp.cases ?? '?'} cases scored · ${when(lp.at)}`,
           'sessions/parity_history.jsonl');
    }

    // ---- the estate's own state, before its scores -------------------
    // The sittings ARE the prior record. Read exactly from sessions.jsonl,
    // where a closing line supersedes its opening one.
    const rc = p.record || {};
    let estate = '';
    if (rc.error) {
      estate = `<div class="card"><div class="eng-row eng-bad">The record could not be read:
        ${escHtml(rc.error)}<span class="brief-src">sessions/sessions.jsonl</span></div></div>`;
    } else if (rc.sittings != null) {
      const rows = (rc.recent || []).slice().reverse().map(r => `<tr>
        <td class="num">${escHtml(String(r.n))}</td>
        <td>${escHtml(String(r.started || '').replace('T', ' '))}</td>
        <td>${r.ended ? escHtml(String(r.ended).slice(11)) : '<span class="tool-bad">still open</span>'}</td>
        <td class="num">${escHtml(String(r.runs))}</td>
        <td>${r.toll_paid ? '<span class="badge badge-green">tolled</span>'
                          : '<span class="badge badge-yellow">no toll</span>'}</td></tr>`).join('');
      estate = `<div class="card">
        <div class="card-title">The estate <span class="muted">— read from the record, not counted here</span></div>
        <div class="stats">
          <div class="stat"><div class="stat-label">sittings</div>
            <div class="stat-value">${rc.sittings}</div>
            <div class="stat-note">${rc.still_open ? '<span class="tool-bad">' + rc.still_open + ' still open</span>' : 'all closed'}</div>
            <div class="brief-src">sessions/sessions.jsonl</div></div>
          <div class="stat"><div class="stat-label">tolled</div>
            <div class="stat-value ${rc.tolled === rc.sittings ? 'green' : 'yellow'}">${rc.tolled}<span class="muted">/${rc.sittings}</span></div>
            <div class="stat-note">${rc.seat_log_tolls != null ? rc.seat_log_tolls + ' written into SEAT_LOG' : 'SEAT_LOG unreadable'}</div>
            <div class="brief-src">sessions/sessions.jsonl · SEAT_LOG.md</div></div>
          <div class="stat"><div class="stat-label">runs recorded</div>
            <div class="stat-value blue">${rc.runs}</div>
            <div class="stat-note">objectives the council actually ran</div>
            <div class="brief-src">sessions/sessions.jsonl</div></div>
        </div>
        ${rows ? `<div class="table-wrap"><table><thead><tr><th class="num">sitting</th><th>opened</th><th>closed</th><th class="num">runs</th><th>toll</th></tr></thead><tbody>${rows}</tbody></table></div>` : ''}
        <div class="stat-note" style="margin-top:10px">
          ${escHtml((rc.counted_by_the_engine || []).join(' and '))} are counted by the core's own rules
          (memory.py's entry pattern; a SELECT against index/vectors.db) and are shown whole in the
          boot report on the Dashboard. They are not recounted here: a second definition of "an entry"
          would drift from the core's the first time it changed.
        </div></div>`;
    }

    // THE NEWEST FIVE, not all thirty-three. This ran every live standup ever
    // recorded, oldest first, so the run that matters — the last one — sat at
    // the bottom of a table that grew a row every morning. Five, newest first,
    // matching the sittings table above it.
    const RECENT = 5;
    const shown = runs.slice(-RECENT).reverse();
    const older = runs.length - shown.length;
    const standups = runs.length ? `<div class="card"><div class="card-title">Live standups
        <span class="muted">— the last ${shown.length} of ${runs.length}, newest first</span></div>
        <div class="table-wrap"><table><thead><tr><th>when</th><th>score</th><th>failed</th><th>report</th></tr></thead><tbody>` +
        shown.map(r => `<tr>
          <td>${escHtml(when(r.at))}</td>
          <td><span class="badge ${r.green ? 'badge-green' : 'badge-red'}">${r.passed}/${r.total}</span></td>
          <td>${(r.failed || []).length ? escHtml((r.failed || []).join(', ')) : '<span class="muted">—</span>'}</td>
          <td><code>${escHtml(r.report || '')}</code></td></tr>`).join('') +
        `</tbody></table>` +
        (older ? `<div class="stat-note" style="margin-top:10px">${older} earlier
           run${older === 1 ? '' : 's'} are in <code>tests/run_history.jsonl</code>.</div>` : '') +
        `</div>` : '';

    const scores = `<div class="stats">${cards.join('')}</div>`;
    box.innerHTML = only === 'deck' ? this.deck(p)
                  : only === 'scores' ? scores
                  : only === 'estate' ? estate + standups
                  : estate + scores + standups;
    // THE DECK CREATES THE HERO'S SLOTS, SO THE DECK FILLS THEM. This read is
    // async and lands after Home.read() has already painted the engine once,
    // into elements this line then replaced -- the hero came up with its
    // kicker and nothing under it. Calling from here rather than from each of
    // the three sites that ask for a deck makes the order right by
    // construction instead of by remembering.
    // `window.Home` is NOT how to ask. Home is declared `const` at the top of
    // home.js, and a top-level const in a classic script binds in the global
    // LEXICAL scope, never as a property of window -- so `window.Home` was
    // undefined and this line silently did nothing. The hero came up with its
    // kicker and an empty body, which looked exactly like a failed read.
    if (only === 'deck' && typeof Home !== 'undefined' && Home.paintEngine) Home.paintEngine();
  },

  // THE DECK -- the Dashboard's top third, and the page's answer to the only
  // two questions that gate the next move.
  //
  // WHAT THIS PAGE IS FOR, worked out from what he actually does on it. He
  // sits down and asks, in this order: can I work at all, what do I want
  // done, what is happening, is the ground sound, is anything waiting on me.
  // The page answered them in almost the reverse order -- the scores held the
  // top-left, and the ENGINE CARD, which gates every other thing on the page,
  // sat BELOW the box it gates. Nothing typed into that box runs without an
  // engine, and the card saying so was three scrolls down.
  //
  // SO THE HERO IS THE SITTING. Open or not, on which world, how long it has
  // stood, and the one button that changes it. The engine card is folded in
  // here and gone as a card -- its whole content was one sentence, which is
  // the complaint its own comment made about the card above it.
  //
  // WITH ONE OVERRIDE: A RED BUILD OUTRANKS AN UNOPENED ENGINE. Booting onto
  // a broken build without being told is worse than not knowing the engine is
  // shut, so red anywhere flips the hero to the verdict and NAMES what fell.
  // A measure that was never run is not green either: "nothing failed" and
  // "nothing was tried" are different claims and only the first is good news.
  //
  // THE PROOF DROPS TO THE LEDGER beside it -- rows, not cards. Five cards of
  // identical weight made the eye do the ranking; a ruled list puts the values
  // in one column where they can be compared in a single sweep, which is the
  // only reason to show them together at all.
  deck(p) {
    const su = p.suites || {};
    const runs = p.standups || [];
    const last = runs.length ? runs[runs.length - 1] : null;
    const par = p.parity || [];

    const red = [], absent = [];
    for (const name of ['strokes', 'smoke']) {
      const r = su[name];
      if (!r) { absent.push(name); continue; }
      if (!r.green) red.push(name);
    }
    if (!last) absent.push('the live standup');
    else if (!last.green) red.push('the live standup');

    // The alarm is rendered ONLY when the build is not wholly proven. A green
    // build says nothing here; the ledger beside it already carries the
    // numbers, and a banner that is always on is a banner nobody reads.
    let alarm = '';
    if (red.length) {
      const which = red.join(red.length === 2 ? ' and ' : ', ');
      const fell = (su.strokes && !su.strokes.green && (su.strokes.failures || [])[0])
                || (last && !last.green && (last.failed || [])[0]) || '';
      alarm = `<div class="hero-alarm red"><b>RED</b> ${escHtml(which)} did not pass`
            + (fell ? ` · first to fall: <code>${escHtml(fell)}</code>` : '') + `</div>`;
    } else if (absent.length) {
      alarm = `<div class="hero-alarm yellow"><b>PARTLY PROVEN</b> `
            + `${escHtml(absent.join(' and '))} `
            + `${absent.length === 1 ? 'has' : 'have'} never run here. `
            + `Not-tried is not the same as passed.</div>`;
    }

    const rows = [];
    const row = (k, note, v, tone, delta) => rows.push(
      `<div class="led-row">
         <div class="led-k">${escHtml(k)}<span class="led-note">${escHtml(note)}</span></div>
         <div class="led-v ${tone || ''}">${v}${delta
           ? `<span class="led-delta ${delta.dir}">${escHtml(delta.text)}</span>` : ''}</div>
       </div>`);
    const frac = (r) => `${r.passed}<span class="muted">/${r.total}</span>`;
    const none = '<span class="muted">—</span>';

    for (const name of ['strokes', 'smoke']) {
      const r = su[name];
      row(name, r ? when(r.at) : (p.suites_error || 'never run'),
          r ? frac(r) : none, r ? (r.green ? 'green' : 'red') : '');
    }

    if (last) {
      // THE ONE HONEST DELTA. run_history.jsonl holds every prior live run, so
      // the move from the previous one is read, not guessed. Nothing else here
      // has a second measurement to compare against, so nothing else gets one.
      let move = null;
      if (runs.length > 1) {
        const d = (last.passed || 0) - (runs[runs.length - 2].passed || 0);
        if (d !== 0) move = { dir: d > 0 ? 'up' : 'down', text: (d > 0 ? '+' : '') + d };
      }
      row('live standup', when(last.at), frac(last), last.green ? 'green' : 'red', move);
      const greens = runs.filter(r => r.green).length;
      row('runs green', 'of every live run on record',
          `${greens}<span class="muted">/${runs.length}</span>`,
          greens === runs.length ? 'green' : 'yellow');
    } else {
      row('live standup', p.standups_error || 'a dry run does not count', none, '');
    }

    if (par.length) {
      const lp = par[par.length - 1];
      row('parity', `${lp.scored ?? '?'} of ${lp.cases ?? '?'} cases · ${when(lp.at)}`,
          String(lp.mean ?? '—'), 'blue');
    } else {
      row('parity', p.parity_error || 'chain against bare calls', none, '');
    }

    // THE IDS INSIDE THE HERO ARE THE ENGINE CARD'S OWN. Home.paintEngine
    // writes into #home-engine and #home-engine-controls and is driven by a
    // run-state event, not by this read -- so the sitting repaints on every
    // boot, turn and close without re-reading `proofs` each time.
    return `<div class="deck">
      <div class="hero">
        <div class="hero-kicker">The sitting</div>
        <div id="home-engine" class="hero-body"></div>
        <div id="home-engine-controls" class="hero-acts"></div>
        ${alarm}
      </div>
      <div class="ledger">
        <div class="led-head">What this build has proved</div>
        ${rows.join('')}
        <div class="led-foot"><span class="brief-src">proofs · read, never counted here</span></div>
      </div>
    </div>`;
  },

  // === RECORDS ===
  // The estate's own memory: what was proven, what sat, and every document it
  // carries, sorted by what the document IS.
  async renderRecords(el) {
    el.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">Records</div>
          <div class="page-subtitle">What was proven, what sat, and what this ground carries — read from the record, never counted here</div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">The documents</div>
        <!-- The kinds get their own line and WRAP. In the header they were one
             unwrapping flex row 621px wide inside a narrower card, so "skills"
             and "logs" were clipped off the right edge -- two whole kinds
             invisible on a page whose job is to show what the ground carries. -->
        <div class="flex" id="rec-kinds" style="flex-wrap:wrap;gap:6px;margin:8px 0 12px"></div>
        <div id="rec-list"><div class="skel skel-60"></div><div class="skel skel-80"></div><div class="skel skel-40"></div></div>
      </div>
      <div id="rec-doc"></div>
      <div id="rec-proof" class="mt-16"></div>`;
    // THE DOCUMENTS OPEN THE PAGE (the operator, 2026-09-10). What this ground
    // CARRIES is the question Records is opened to answer; the sittings and the
    // standups are the history behind it, and they read better after. The
    // SCORES that used to head this page moved to the Dashboard entirely.
    this.paintDocs();
    this.paintProof('rec-proof', 'estate');
  },

  // The docs, by kind. `records` sorts them; this page only draws the sections
  // it is handed, so a kind added to the tool appears here without an edit.
  async paintDocs() {
    const bar = document.getElementById('rec-kinds');
    const list = document.getElementById('rec-list');
    if (!bar || !list) return;
    let r;
    try {
      r = JSON.parse(await this.tool('records', {}));
    } catch (e) {
      list.innerHTML = `<div class="eng-row eng-bad">The documents could not be read:
        ${escHtml(e.message || 'refused')}<span class="brief-src">records</span></div>`;
      return;
    }
    this._recs = r;
    const kinds = r.kinds || [];
    if (!kinds.length) { list.innerHTML = '<div class="empty-text">This ground carries no documents.</div>'; return; }
    this._recKind = this._recKind && kinds.some(k => k.kind === this._recKind)
      ? this._recKind : kinds[0].kind;

    bar.innerHTML = kinds.map(k =>
      `<button class="btn btn-sm ${k.kind === this._recKind ? 'btn-primary' : ''}" data-kind="${escHtml(k.kind)}">
         ${escHtml(k.kind)} <span class="muted">${k.count}</span></button>`).join('') +
      `<span class="brief-src">records · ${r.count} documents</span>`;
    bar.querySelectorAll('[data-kind]').forEach(btn => {
      btn.onclick = () => { this._recKind = btn.dataset.kind; this.paintDocs(); };
    });

    const kind = kinds.find(k => k.kind === this._recKind) || kinds[0];
    // Every kind is sorted by name by the tool, except logs, which come back
    // newest first and capped -- so the note says so rather than letting the
    // page look like the whole of logs/.
    list.innerHTML =
      (kind.kind === 'logs'
        ? '<div class="stat-note" style="margin-bottom:10px">The newest 60 transcripts, most recent first. The rest are on disk in <code>logs/</code>.</div>'
        : '') +
      '<div class="table-wrap"><table><thead><tr><th>document</th><th>kind</th><th class="num">size</th><th>changed</th></tr></thead><tbody>' +
      kind.documents.map(d => `<tr class="rec-row" data-name="${escHtml(d.name)}" style="cursor:pointer">
        <td><code>${escHtml(d.name)}</code>${d.sealed ? ' <span class="badge badge-yellow">sealed</span>' : ''}</td>
        <td><span class="muted">${escHtml(d.kind)}</span></td>
        <td class="num">${(d.bytes / 1024).toFixed(1)} KB</td>
        <td>${escHtml(when(Date.parse(d.modified) || 0))}</td></tr>`).join('') +
      '</tbody></table></div>';
    list.querySelectorAll('.rec-row').forEach(tr => {
      tr.onclick = () => this.openDoc(tr.dataset.name);
    });
  },

  // One document whole, with the sha256 of the bytes that were served. The
  // receipt is the point: a page showing a document can be checked against the
  // disk without trusting the page.
  async openDoc(name) {
    const box = document.getElementById('rec-doc');
    if (!box) return;
    box.innerHTML = `<div class="card mt-16"><div class="loading">Reading ${escHtml(name)}...</div></div>`;
    let d;
    try {
      d = JSON.parse(await this.tool('records', { name: name }));
    } catch (e) {
      box.innerHTML = `<div class="card mt-16"><div class="eng-row eng-bad">
        ${escHtml(e.message || 'refused')}<span class="brief-src">records</span></div></div>`;
      return;
    }
    box.innerHTML = `<div class="card mt-16">
      <div class="card-header">
        <span class="card-title">${escHtml(d.name)}
          ${d.sealed ? '<span class="badge badge-yellow">sealed — read, never edited</span>' : ''}</span>
        <span class="flex"><button class="btn btn-sm" id="rec-close">Close</button></span>
      </div>
      <div class="stat-note">${escHtml(d.kind)} · ${(d.bytes / 1024).toFixed(1)} KB ·
        changed ${escHtml(when(Date.parse(d.modified) || 0))}
        <br><span class="hash">sha256 ${escHtml(d.sha256)}</span></div>
      <pre class="home-boot" style="max-height:60vh;overflow:auto">${escHtml(d.text || '')}</pre>
    </div>`;
    const c = document.getElementById('rec-close');
    if (c) c.onclick = () => { box.innerHTML = ''; };
    box.scrollIntoView({ behavior: 'smooth', block: 'start' });
  },

  // === MESSAGES (team bridge) ===
  parseTeamHistory(text) {
    const rows = [];
    let cur = null;
    for (const line of (text || '').split('\n')) {
      let m = /^(inbound|outbound) (\S+)\/(\S+) · (\S+) · receipt ([0-9a-f]+)/.exec(line);
      if (m) { cur = { dir: m[1], platform: m[2], channel: m[3], ts: m[4], receipt: m[5], content: '' }; rows.push(cur); continue; }
      if (cur && line.startsWith('  ')) cur.content += (cur.content ? '\n' : '') + line.slice(2);
    }
    return rows;
  },

  async renderMessages(el) {
    el.innerHTML = '<div class="loading">Loading messages...</div>';
    try {
      const [hist, presence] = await Promise.all([
        API.teamHistory('', '', 100).catch(() => ({ history: '' })),
        API.teamStatus().catch(() => ({ status: '' }))
      ]);
      const rows = this.parseTeamHistory(hist.history);
      el.innerHTML = `
        <div class="page-header">
          <div>
            <div class="page-title">Messages</div>
            <div class="page-subtitle">${rows.length} crossings · receipts on every row</div>
          </div>
        </div>
        <div class="card"><div class="card-title">Bridge</div><pre id="team-presence">${escHtml(presence.status || 'bridge silent')}</pre></div>
        <div class="card mt-16"><div class="card-title">Send (guarded, receipted)</div>
          <div class="flex">
            <select id="team-platform"><option value="discord">discord</option><option value="slack">slack</option><option value="whatsapp">whatsapp</option></select>
            <input id="team-channel" type="text" placeholder="channel" value="general" />
            <input id="team-content" type="text" placeholder="Message..." style="flex:1" />
            <button class="btn btn-primary" id="team-send">Send</button>
          </div>
          <div id="team-send-status" class="muted"></div>
        </div>
        <div class="card mt-16">
          ${rows.length === 0
            ? '<div class="empty"><div class="empty-icon">&#9993;</div><div class="empty-text">The bridge holds nothing yet. Sends and deliveries appear here with receipts.</div></div>'
            : '<div class="table-wrap"><table><thead><tr><th>Dir</th><th>Platform</th><th>Channel</th><th>Content</th><th>Receipt</th><th>Time</th></tr></thead><tbody>' +
              rows.map(m => `
                <tr>
                  <td><span class="badge ${m.dir === 'outbound' ? 'badge-blue' : 'badge-muted'}">${escHtml(m.dir)}</span></td>
                  <td><span class="badge badge-${m.platform === 'discord' ? 'purple' : m.platform === 'slack' ? 'blue' : 'green'}">${escHtml(m.platform)}</span></td>
                  <td><code>${escHtml(m.channel)}</code></td>
                  <td>${escHtml((m.content || '').slice(0, 80))}${(m.content || '').length > 80 ? '...' : ''}</td>
                  <td><span class="hash">${escHtml(m.receipt.slice(0, 16))}</span></td>
                  <td>${timeAgo(m.ts)}</td>
                </tr>
              `).join('') + '</tbody></table></div>'}
        </div>
      `;
      document.getElementById('team-send').onclick = () => this.teamSend();
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>`;
    }
  },

  async teamSend() {
    const platform = document.getElementById('team-platform').value;
    const channel = document.getElementById('team-channel').value.trim();
    const content = document.getElementById('team-content').value.trim();
    if (!content) return;
    try {
      const r = await API.teamSend(platform, channel, content);
      document.getElementById('team-send-status').textContent = r.text;
      document.getElementById('team-content').value = '';
      this.router();
    } catch (e) { document.getElementById('team-send-status').textContent = 'Refused: ' + e.message; }
  },

  // === SETTINGS ===
  async renderSettings(el) {
    el.innerHTML = '<div class="loading">Loading settings...</div>';
    try {
      const [mcp, evals] = await Promise.all([
        API.getSetting('mcp_url').catch(() => ({ value: '' })),
        API.getSetting('eval_threshold').catch(() => ({ value: '0.5' }))
      ]);
      el.innerHTML = `
        <div class="page-header">
          <div>
            <div class="page-title">Settings</div>
            <div class="page-subtitle">System configuration</div>
          </div>
        </div>
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><span class="card-title">MCP Connection</span></div>
            <div class="form-group">
              <div class="form-label">MCP Server URL</div>
              <input class="input" id="mcp-url" value="${escHtml(mcp.value || 'http://localhost:8090')}" placeholder="http://localhost:8090">
            </div>
            <button class="btn btn-primary" onclick="App.saveSetting('mcp_url', document.getElementById('mcp-url').value)">Save</button>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Evals</span></div>
            <div class="form-group">
              <div class="form-label">Pass Threshold (0-1)</div>
              <input class="input" id="eval-threshold" value="${escHtml(evals.value || '0.5')}" type="number" min="0" max="1" step="0.1">
            </div>
            <button class="btn btn-primary" onclick="App.saveSetting('eval_threshold', document.getElementById('eval-threshold').value)">Save</button>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Messaging Platforms</span></div>
            <div id="msg-presence"><div class="loading">Checking bridge...</div></div>
            <p style="font-size:11px;color:var(--text-3);margin-top:12px">Connect: place webhook URLs + hook secret in the tenant's <code>state/chat_secrets.json</code> (0600). Secrets never surface here — presence only. Inbound door: <code>POST /hooks/:platform</code> with <code>X-Atlas-Signature</code>.</p>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Provenance</span></div>
            <table>
              <tr><td>Chain Integrity</td><td><span class="badge badge-green">SHA-256</span></td></tr>
              <tr><td>Append-Only</td><td><span class="badge badge-green">enabled</span></td></tr>
              <tr><td>Structural Enforcement</td><td><span class="badge badge-green">can_approve:false</span></td></tr>
            </table>
          </div>
        </div>
      `;
      API.teamStatus().then(r => {
        document.getElementById('msg-presence').innerHTML = `<pre>${escHtml(r.status || 'bridge silent')}</pre>`;
      }).catch(() => {
        document.getElementById('msg-presence').innerHTML = '<div class="empty-text">Bridge unreachable.</div>';
      });
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>`;
    }
  },

  async saveSetting(key, value) {
    try {
      await API.setSetting(key, value);
      toast('Setting saved');
    } catch (e) { toast(e.message, 'error'); }
  },

  async runProve() {
    toast('Running prove...');
    try {
      const result = await API.callTool('verify_chain', { path: '.', project: 'atlas' });
      toast('Prove complete: ' + (result.output || '').slice(0, 80));
    } catch (e) { toast('Prove failed: ' + e.message, 'error'); }
  }
};

document.addEventListener('DOMContentLoaded', () => App.init());
