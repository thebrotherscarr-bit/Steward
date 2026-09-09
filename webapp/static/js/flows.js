// ATLAS Flows — the DAG builder. Forms and tables only, no canvas lib:
// nodes and edges edit as rows, the graph previews as SVG, runs render
// as waterfalls. Gates pause for the hand — continue|stop, never more.
const Flows = {
  current: null,

  async render(el) {
    el.innerHTML = `
      <div class="page-header"><div><div class="page-title">Flows</div>
      <div class="page-subtitle">DAGs with gates — branches declare, the queue runs one by one</div></div></div>
      <div class="grid-2">
        <div class="card"><div class="card-title">Registry</div>
          <div id="flow-list"><div class="loading">Loading...</div></div>
          <div class="card-title mt-16">Editor</div>
          <input id="flow-name" type="text" placeholder="flow name" />
          <textarea id="flow-spec" rows="12" placeholder='{"nodes":[...],"edges":[...],"budget_s":600}'></textarea>
          <div class="flex"><button class="btn btn-sm" id="flow-save">Save</button>
          <button class="btn btn-sm" id="flow-template">Template</button></div>
          <div id="flow-save-status" class="muted"></div>
          <div class="card-title mt-16">Graph</div>
          <div id="flow-graph"></div>
        </div>
        <div class="card"><div class="card-title">Run</div>
          <input id="flow-inputs" type="text" placeholder='inputs JSON, e.g. {"who":"Ada"}' value="{}" />
          <button class="btn btn-sm" id="flow-run">Fire</button>
          <div id="flow-out"></div>
          <div class="flex mt-16"><button class="btn btn-sm" id="flow-cont">Resume continue</button>
          <button class="btn btn-sm" id="flow-stop">Resume stop</button></div>
          <div class="card-title mt-16">Runs</div>
          <div id="flow-runs"><div class="loading">Loading...</div></div>
          <div class="flex"><input id="flow-cmp-b" type="text" placeholder="second run id" />
          <button class="btn btn-sm" id="flow-compare">Compare</button>
          <button class="btn btn-sm" id="flow-replay">Replay last</button></div>
          <div id="flow-cmp"></div>
        </div>
      </div>
      <div class="card mt-16"><div class="card-title">Town board</div>
        <div class="flex"><button class="btn btn-sm" id="town-beat">Beat</button>
        <button class="btn btn-sm" id="town-status">Status</button></div>
        <div id="town-out"></div>
      </div>`;
    document.getElementById('flow-save').onclick = () => this.save();
    document.getElementById('flow-template').onclick = () => this.template();
    document.getElementById('flow-run').onclick = () => this.run();
    document.getElementById('flow-cont').onclick = () => this.resume('continue');
    document.getElementById('flow-stop').onclick = () => this.resume('stop');
    document.getElementById('flow-compare').onclick = () => this.compare();
    document.getElementById('flow-replay').onclick = () => this.replay();
    document.getElementById('flow-spec').oninput = () => this.graph();
    document.getElementById('town-beat').onclick = async () => {
      try { const r = await API.townBeat(); document.getElementById('town-out').innerHTML = `<pre>${escHtml(r.text)}</pre>`; }
      catch (e) { toast('Beat refused', 'error'); }
    };
    document.getElementById('town-status').onclick = async () => {
      try { const r = await API.townStatus(); document.getElementById('town-out').innerHTML = `<pre>${escHtml(r.text)}</pre>`; }
      catch { toast('MCP unreachable', 'error'); }
    };
    await this.refresh();
    await this.runs();
  },

  template() {
    document.getElementById('flow-spec').value = JSON.stringify({
      budget_s: 600,
      nodes: [
        { name: 'a', kind: 'ask', question: 'Q {{who}}' },
        { name: 'e', kind: 'eval', node: 'a', expected: 'yes' },
        { name: 'b', kind: 'ask', question: 'B {{out_a}}' },
        { name: 'g', kind: 'gate', title: 'human review' }
      ],
      edges: [
        { from: 'a', to: 'e', when: 'always' },
        { from: 'e', to: 'b', when: 'pass' },
        { from: 'e', to: 'g', when: 'fail' }
      ]
    }, null, 2);
    this.graph();
  },

  graph() {
    const box = document.getElementById('flow-graph');
    let spec;
    try { spec = JSON.parse(document.getElementById('flow-spec').value); }
    catch { box.innerHTML = '<div class="empty-text">Spec is not JSON yet.</div>'; return; }
    const names = (spec.nodes || []).map(n => n.name);
    const depth = {};
    names.forEach(n => depth[n] = 0);
    for (let i = 0; i < names.length + 1; i++)
      for (const e of (spec.edges || []))
        if (depth[e.from] !== undefined && depth[e.to] !== undefined)
          depth[e.to] = Math.max(depth[e.to], depth[e.from] + 1);
    const cols = {};
    names.forEach(n => { (cols[depth[n]] = cols[depth[n]] || []).push(n); });
    const kinds = {};
    (spec.nodes || []).forEach(n => kinds[n.name] = n.kind);
    const W = 150, H = 46;
    let maxCol = 0;
    Object.keys(cols).forEach(k => maxCol = Math.max(maxCol, cols[k].length));
    const svgW = (Object.keys(cols).length) * (W + 40) + 20;
    const svgH = Math.max(1, maxCol) * (H + 14) + 20;
    let s = `<svg width="${svgW}" height="${svgH}" style="max-width:100%">`;
    const pos = {};
    Object.keys(cols).sort((a, b) => a - b).forEach(d => {
      cols[d].forEach((n, i) => { pos[n] = { x: 10 + d * (W + 40), y: 10 + i * (H + 14) }; });
    });
    for (const e of (spec.edges || [])) {
      if (!pos[e.from] || !pos[e.to]) continue;
      const a = pos[e.from], b = pos[e.to];
      const col = e.when === 'fail' ? 'var(--red)' : e.when === 'pass' ? 'var(--green)' : 'var(--text-3)';
      s += `<line x1="${a.x + W}" y1="${a.y + H / 2}" x2="${b.x}" y2="${b.y + H / 2}" stroke="${col}" stroke-width="2"/>`;
    }
    for (const n of names) {
      const p = pos[n];
      const k = kinds[n] || '?';
      const fill = k === 'gate' ? 'var(--yellow)' : k === 'eval' ? 'var(--blue)' : 'var(--surface)';
      s += `<rect x="${p.x}" y="${p.y}" width="${W}" height="${H}" rx="8" fill="${fill}" fill-opacity="0.15" stroke="var(--border)"/>`;
      s += `<text x="${p.x + 8}" y="${p.y + 20}" fill="var(--text)" font-size="12">${escHtml(n)}</text>`;
      s += `<text x="${p.x + 8}" y="${p.y + 36}" fill="var(--text-3)" font-size="11">${escHtml(k)}</text>`;
    }
    box.innerHTML = s + '</svg>';
  },

  async refresh() {
    const box = document.getElementById('flow-list');
    try {
      const r = await API.listFlows();
      const names = [];
      for (const line of (r.flows || '').split('\n')) {
        const m = /^\s*-\s(\S+)\s+v(\d+)/.exec(line);
        if (m) names.push({ name: m[1], ver: +m[2], line: line.trim() });
      }
      box.innerHTML = names.length ? names.map(f =>
        `<div class="chat-session" data-n="${escHtml(f.name)}">${escHtml(f.line)}</div>`
      ).join('') : '<div class="empty-text">No flows yet. Template one, then save.</div>';
      box.querySelectorAll('.chat-session').forEach(d => {
        d.onclick = () => this.open(d.dataset.n);
      });
    } catch { box.innerHTML = '<div class="empty-text">MCP unreachable.</div>'; }
  },

  async open(name) {
    this.current = name;
    document.getElementById('flow-name').value = name;
    try {
      const r = await API.getFlow(name, 0);
      const spec = JSON.parse(r.spec);
      delete spec.name; delete spec.version;
      document.getElementById('flow-spec').value = JSON.stringify(spec, null, 2);
      this.graph();
    } catch { toast('Could not open flow', 'error'); }
  },

  async save() {
    const name = document.getElementById('flow-name').value.trim();
    const spec = document.getElementById('flow-spec').value;
    try { JSON.parse(spec); } catch { document.getElementById('flow-save-status').textContent = 'Refused: spec is not JSON'; return; }
    try {
      const r = await API.saveFlow(name, spec);
      document.getElementById('flow-save-status').textContent = r.text;
      this.current = name;
      await this.refresh();
    } catch (e) { document.getElementById('flow-save-status').textContent = 'Refused: ' + e.message; }
  },

  lastRun() {
    const m = /RUN (f-\d{8}-\d{6}-[0-9a-f]{8})/.exec(document.getElementById('flow-out').textContent || '');
    return m ? m[1] : null;
  },

  async run() {
    const out = document.getElementById('flow-out');
    out.innerHTML = '<div class="loading">Firing...</div>';
    try {
      const r = await API.fireFlow(
        this.current || document.getElementById('flow-name').value.trim(),
        document.getElementById('flow-inputs').value);
      out.innerHTML = `<pre>${escHtml(r.text)}</pre>`;
      await this.runs();
    } catch (e) { out.innerHTML = `<div class="empty-text">Refused: ${escHtml(e.message)}</div>`; }
  },

  async resume(decision) {
    const run = this.lastRun();
    if (!run) { toast('No run to resume', 'error'); return; }
    try {
      const r = await API.resumeFlow(run, decision);
      document.getElementById('flow-out').innerHTML = `<pre>${escHtml(r.text)}</pre>`;
      await this.runs();
    } catch (e) { toast('Resume refused: ' + e.message, 'error'); }
  },

  async runs() {
    const box = document.getElementById('flow-runs');
    try {
      const r = await API.listRuns('');
      box.innerHTML = `<pre>${escHtml(r.runs)}</pre>`;
    } catch { box.innerHTML = '<div class="empty-text">MCP unreachable.</div>'; }
  },

  async compare() {
    const a = this.lastRun();
    const b = document.getElementById('flow-cmp-b').value.trim();
    if (!a || !b) { toast('Need two run ids', 'error'); return; }
    try {
      const r = await API.compareFlows(a, b);
      document.getElementById('flow-cmp').innerHTML = `<pre>${escHtml(r.text)}</pre>`;
    } catch (e) { toast('Compare refused', 'error'); }
  },

  async replay() {
    const run = this.lastRun() || document.getElementById('flow-cmp-b').value.trim();
    if (!run) { toast('No run to replay', 'error'); return; }
    try {
      const r = await API.replayFlow(run);
      document.getElementById('flow-out').innerHTML = `<pre>${escHtml(r.text)}</pre>`;
      await this.runs();
    } catch (e) { toast('Replay refused', 'error'); }
  }
};
