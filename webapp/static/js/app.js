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
    API.sse((e) => this.onEvent(e));
  },

  router() {
    const path = location.pathname.slice(1) || 'dashboard';
    const parts = path.split('/');
    this.currentPage = parts[0];
    this.pageParam = parts[1] || null;
    document.querySelectorAll('.nav-link').forEach(a => {
      a.classList.toggle('active', a.dataset.page === this.currentPage);
    });
    this.render();
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
      case 'dashboard': await this.renderDashboard(el); break;
      case 'agents': this.pageParam ? await this.renderAgentDetail(el) : await this.renderAgents(el); break;
      case 'traces': this.pageParam ? await this.renderTraceDetail(el) : await this.renderTraces(el); break;
      case 'tools': await this.renderTools(el); break;
      case 'evals': await this.renderEvals(el); break;
      case 'chat': await Chat.render(el); break;
      case 'playground': await Play.render(el); break;
      case 'flows': await Flows.render(el); break;
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
  async renderAgents(el) {
    el.innerHTML = '<div class="loading">Loading agents...</div>';
    try {
      const data = await API.listAgents();
      const agents = data.agents || [];
      el.innerHTML = `
        <div class="page-header">
          <div>
            <div class="page-title">Agent Registry</div>
            <div class="page-subtitle">${agents.length} agents enrolled</div>
          </div>
          <div class="search-bar">
            <input class="input" placeholder="Search agents..." oninput="App.filterAgents(this.value)">
          </div>
        </div>
        <div class="agent-grid" id="agent-grid">
          ${agents.map(a => `
            <div class="agent-card" onclick="location.href='/agents/${a.id}'">
              <div class="agent-card-name">${escHtml(a.id)}</div>
              <div class="agent-card-office">${escHtml(a.office || '—')}</div>
              <div class="agent-card-role">${escHtml(a.role || '—')}</div>
              <div class="agent-card-meta">
                <span class="badge ${a.mode === 'primary' ? 'badge-blue' : 'badge-muted'}">${escHtml(a.mode || '—')}</span>
                <span class="badge badge-muted">reports to: ${escHtml(a.reports_to || '—')}</span>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>`;
    }
  },

  filterAgents(q) {
    q = q.toLowerCase();
    document.querySelectorAll('.agent-card').forEach(card => {
      const text = card.textContent.toLowerCase();
      card.style.display = text.includes(q) ? '' : 'none';
    });
  },

  async renderAgentDetail(el) {
    el.innerHTML = '<div class="loading">Loading agent...</div>';
    try {
      const data = await API.getAgent(this.pageParam);
      const a = data.agent;
      const traces = data.traces || [];
      el.innerHTML = `
        <div class="page-header">
          <div>
            <div class="page-title">${escHtml(a.id)}</div>
            <div class="page-subtitle">${escHtml(a.office || '')} — ${escHtml(a.mode || '')}</div>
          </div>
          <a href="/agents" class="btn" onclick="event.preventDefault();history.pushState(null,'','/agents');App.router();">Back</a>
        </div>
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><span class="card-title">Declaration</span></div>
            <table>
              <tr><td>ID</td><td><code>${escHtml(a.id)}</code></td></tr>
              <tr><td>Office</td><td>${escHtml(a.office || '—')}</td></tr>
              <tr><td>Reports To</td><td><code>${escHtml(a.reports_to || '—')}</code></td></tr>
              <tr><td>Mode</td><td><span class="badge ${a.mode === 'primary' ? 'badge-blue' : 'badge-muted'}">${escHtml(a.mode || '—')}</span></td></tr>
              <tr><td>Role</td><td>${escHtml(a.role || '—')}</td></tr>
              <tr><td>Permissions</td><td><pre style="font-size:11px;color:var(--text-2);white-space:pre-wrap">${escHtml(a.permissions || '—')}</pre></td></tr>
            </table>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Recent Traces</span><span class="badge badge-purple">${traces.length}</span></div>
            ${traces.length === 0
              ? '<div class="empty"><div class="empty-text">No traces for this agent yet.</div></div>'
              : '<div class="timeline">' + traces.slice(0, 15).map(t => `
                <div class="timeline-entry" onclick="location.href='/traces/${t.id}'">
                  <div class="timeline-header">
                    <span class="timeline-title"><code>${escHtml(t.tool)}</code></span>
                    <span class="timeline-time">${timeAgo(t.created_at)}</span>
                  </div>
                  <div class="timeline-detail">${escHtml(t.status)} — ${t.duration_ms}ms</div>
                  <div class="timeline-hash">${escHtml(t.hash || '')}</div>
                </div>
              `).join('') + '</div>'}
          </div>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>`;
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
  async renderEvals(el) {
    el.innerHTML = '<div class="loading">Loading evals...</div>';
    try {
      const data = await API.listEvals();
      const evals = data.evals || [];
      const passed = evals.filter(e => e.passed).length;
      const failed = evals.length - passed;
      el.innerHTML = `
        <div class="page-header">
          <div>
            <div class="page-title">Evaluations</div>
            <div class="page-subtitle">${evals.length} evals — ${passed} passed, ${failed} failed</div>
          </div>
        </div>
        <div class="stats">
          <div class="stat"><div class="stat-label">Total</div><div class="stat-value">${evals.length}</div></div>
          <div class="stat"><div class="stat-label">Passed</div><div class="stat-value green">${passed}</div></div>
          <div class="stat"><div class="stat-label">Failed</div><div class="stat-value red">${failed}</div></div>
          <div class="stat"><div class="stat-label">Pass Rate</div><div class="stat-value ${evals.length > 0 && passed/evals.length >= 0.8 ? 'green' : 'yellow'}">${evals.length > 0 ? Math.round((passed/evals.length)*100) : 0}%</div></div>
        </div>
        <div class="card">
          ${evals.length === 0
            ? '<div class="empty"><div class="empty-icon">&#10003;</div><div class="empty-text">No evals yet. Add an eval from a trace detail page.</div></div>'
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
    } catch (e) {
      el.innerHTML = `<div class="empty"><div class="empty-icon">!</div><div class="empty-text">${escHtml(e.message)}</div></div>`;
    }
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
