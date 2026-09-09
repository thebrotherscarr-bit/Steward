// ATLAS Playground — prompts, @seat, A/B, evals. Forms only, no prompt().
// Runs measure through the LINE's play package; versions fold whole;
// evals score exact-match; the model is always a measurement.
const Play = {
  current: null,

  async render(el) {
    el.innerHTML = `
      <div class="page-header"><div><div class="page-title">Playground</div>
      <div class="page-subtitle">Versioned prompts, single-seat asks, honest compares</div></div></div>
      <div class="grid-2">
        <div class="card"><div class="card-title">Registry</div>
          <div id="play-list"><div class="loading">Loading...</div></div>
          <div class="card-title mt-16">Editor</div>
          <input id="play-name" type="text" placeholder="prompt name (lowercase, - _)" />
          <input id="play-desc" type="text" placeholder="description" />
          <textarea id="play-body" rows="8" placeholder="Body with {{vars}}..."></textarea>
          <button class="btn btn-sm" id="play-save">Save new version</button>
          <div id="play-save-status" class="muted"></div>
        </div>
        <div class="card"><div class="card-title">Run</div>
          <input id="play-vars" type="text" placeholder='vars JSON, e.g. {"word":"hello"}' value="{}" />
          <div class="flex"><input id="play-voice" type="text" placeholder="voice (empty = default route)" />
          <input id="play-version" type="number" min="0" placeholder="version (0 = latest)" value="0" /></div>
          <button class="btn btn-sm" id="play-run">Run</button>
          <div id="play-out"></div>
          <div class="card-title mt-16">A/B compare</div>
          <div class="flex"><input id="play-vera" type="number" min="1" value="1" />
          <input id="play-verb" type="number" min="1" value="2" />
          <button class="btn btn-sm" id="play-compare">Compare</button></div>
          <div id="play-cmp"></div>
        </div>
      </div>
      <div class="grid-2 mt-16">
        <div class="card"><div class="card-title">@seat — one seat, once</div>
          <input id="seat-q" type="text" placeholder="@manjuel what holds" />
          <div class="flex"><input id="seat-voice" type="text" placeholder="model override (measurement)" />
          <input id="seat-method" type="text" placeholder="method (one run, then spent)" /></div>
          <button class="btn btn-sm" id="seat-ask">Ask the seat</button>
          <div id="seat-out"></div>
        </div>
        <div class="card"><div class="card-title">Eval — score over a dataset</div>
          <div class="flex"><input id="eval-dataset" type="text" placeholder="dataset (evals/name.json)" />
          <button class="btn btn-sm" id="eval-run">Run eval</button></div>
          <div id="eval-out"></div>
        </div>
      </div>`;
    document.getElementById('play-save').onclick = () => this.save();
    document.getElementById('play-run').onclick = () => this.run();
    document.getElementById('play-compare').onclick = () => this.compare();
    document.getElementById('seat-ask').onclick = () => this.seat();
    document.getElementById('eval-run').onclick = () => this.eval();
    await this.refresh();
  },

  async refresh() {
    const box = document.getElementById('play-list');
    try {
      const r = await API.listPrompts();
      const names = [];
      for (const line of (r.prompts || '').split('\n')) {
        const m = /^\s*-\s(\S+)\s+v(\d+)\s+\(kept:\s*(\[[^\]]*\])\)\s*(?:—\s*(.*))?/.exec(line);
        if (m) names.push({ name: m[1], ver: +m[2], kept: m[3], desc: m[4] || '' });
      }
      box.innerHTML = names.length ? names.map(p =>
        `<div class="chat-session" data-n="${escHtml(p.name)}"><b>${escHtml(p.name)}</b> v${p.ver} <span class="muted">${escHtml(p.desc)}</span></div>`
      ).join('') : '<div class="empty-text">No prompts yet. Save the first below.</div>';
      box.querySelectorAll('.chat-session').forEach(d => {
        d.onclick = () => this.open(d.dataset.n);
      });
    } catch { box.innerHTML = '<div class="empty-text">MCP unreachable.</div>'; }
  },

  async open(name) {
    this.current = name;
    document.getElementById('play-name').value = name;
    try {
      const r = await API.getPrompt(name, 0);
      const body = (r.prompt || '').split('\n\n').slice(1).join('\n\n');
      document.getElementById('play-body').value = body;
    } catch { toast('Could not open prompt', 'error'); }
  },

  async save() {
    const name = document.getElementById('play-name').value.trim();
    const body = document.getElementById('play-body').value;
    const desc = document.getElementById('play-desc').value;
    try {
      const r = await API.savePrompt(name, body, desc);
      document.getElementById('play-save-status').textContent = r.text;
      this.current = name;
      await this.refresh();
    } catch (e) { document.getElementById('play-save-status').textContent = 'Refused: ' + e.message; }
  },

  name() { return this.current || document.getElementById('play-name').value.trim(); },

  async run() {
    const out = document.getElementById('play-out');
    out.innerHTML = '<div class="loading">Measuring...</div>';
    try {
      const r = await API.runPrompt(this.name(),
        document.getElementById('play-vars').value,
        +document.getElementById('play-version').value || 0,
        document.getElementById('play-voice').value);
      out.innerHTML = `<pre>${escHtml(r.text)}</pre>`;
    } catch (e) { out.innerHTML = `<div class="empty-text">Refused: ${escHtml(e.message)}</div>`; }
  },

  async compare() {
    const box = document.getElementById('play-cmp');
    box.innerHTML = '<div class="loading">Running both versions...</div>';
    try {
      const r = await API.comparePrompts(this.name(),
        +document.getElementById('play-vera').value || 1,
        +document.getElementById('play-verb').value || 2,
        document.getElementById('play-vars').value,
        document.getElementById('play-voice').value);
      box.innerHTML = `<pre>${escHtml(r.text)}</pre>`;
    } catch (e) { box.innerHTML = `<div class="empty-text">Refused: ${escHtml(e.message)}</div>`; }
  },

  async seat() {
    const out = document.getElementById('seat-out');
    out.innerHTML = '<div class="loading">Asking...</div>';
    try {
      const r = await API.seatAsk(
        document.getElementById('seat-q').value,
        '', document.getElementById('seat-voice').value,
        document.getElementById('seat-method').value);
      out.innerHTML = `<pre>${escHtml(r.text)}</pre>`;
    } catch (e) { out.innerHTML = `<div class="empty-text">Refused: ${escHtml(e.message)}</div>`; }
  },

  async eval() {
    const out = document.getElementById('eval-out');
    out.innerHTML = '<div class="loading">Scoring...</div>';
    try {
      const r = await API.evalPrompt(this.name(),
        document.getElementById('eval-dataset').value,
        0, document.getElementById('play-voice').value);
      const m = /(\d+)\/(\d+) pass/.exec(r.text || '');
      const rate = m ? (+m[1] / +m[2]) : 0;
      out.innerHTML = `<pre>${escHtml(r.text)}</pre>
        <button class="btn btn-sm" id="eval-record">Record score as eval</button>`;
      document.getElementById('eval-record').onclick = async () => {
        try {
          await API.addEval({ name: 'prompt-eval:' + Play.name(), score: rate, passed: rate === 1, detail: r.text });
          toast('Score recorded');
        } catch { toast('Could not record', 'error'); }
      };
    } catch (e) { out.innerHTML = `<div class="empty-text">Refused: ${escHtml(e.message)}</div>`; }
  }
};
