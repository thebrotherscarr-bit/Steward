// ATLAS Workflows — the builder, given its face back.
//
// WHY THIS FILE EXISTS. The DAG builder came off the panel 2026-09-10 ("not
// used, wipe it") and /flows became Version control. What was wiped was the
// PAGE. The engine was never touched: line/internal/flow is 1,140 lines with
// 455 lines of strokes behind it, the door carries ten flow_* tools, the
// webapp has nine handlers, all nine routes are wired, and api.js still
// carries a method for every one of them. Proven live 2026-09-11 before a
// line of this was written: save -> list -> get -> run -> status, a real
// llama3.2 call, receipts, budget bar, verdict COMPLETE.
//
// So nothing here invents a workflow system. It draws the one that is
// already there, and every button is a call the LINE already answers.
//
// THE PATTERNS THIS BUILDS, and what each one is in this engine's own terms
// (the operator's reference, workflowbuilder.io/blog/agentic-workflow-patterns):
//
//   Prompt chaining     nodes joined by `always` edges; topo order is the chain
//   Routing             an `eval` node, then `pass` / `fail` edges off it
//   Parallelization     branches declared; they run sequentially on one rack
//                       queue, because there is one card and interleaved model
//                       output cannot be read
//   Reflection          unrolled into fixed passes -- the engine REFUSES cycles
//                       (Validate: "no cycles"), which is what that article
//                       recommends doing anyway
//   Human-in-the-loop   a `gate` node: the run stops at PAUSED and waits for a
//                       hand to say continue or stop. Nothing resumes itself.
//
// WHAT THIS PAGE WILL NOT DO. It does not finish a task, land a memory, or
// close a gate for anyone. Gate nodes pause and wait; evals only steer edges;
// a verdict is a verdict, never an approval. That is the flow package's own
// rule, written at the top of flow.go, and the page keeps it.

const Workflows = {
  // The spec being edited. null until a flow is opened or started.
  spec: null,
  // The run the waterfall is showing, and its verdict, so a PAUSED run can
  // offer the only two moves a hand is allowed.
  run: null,
  verdict: '',
  busy: false,

  // The closed node set, from flow.go's Kinds map. Anything else is refused
  // by name at save, so the picker offers exactly these and no more.
  KINDS: {
    ask:    { label: 'ask',    blurb: 'one voice, straight to a model',          fields: ['voice', 'question'] },
    run:    { label: 'run',    blurb: 'the whole council — law gate, Router, tools', fields: ['question'] },
    seat:   { label: 'seat',   blurb: 'one named seat, its own prompt',          fields: ['seat', 'question', 'voice', 'method'] },
    prompt: { label: 'prompt', blurb: 'a saved prompt, by name and version',     fields: ['prompt', 'version', 'voice'] },
    memory: { label: 'memory', blurb: 'recall with citations',                   fields: ['voice', 'question'] },
    eval:   { label: 'eval',   blurb: 'check another node — this is what steers', fields: ['node', 'match', 'expected'] },
    gate:   { label: 'gate',   blurb: 'stop and wait for a hand',                fields: ['title'] },
  },

  // Which fields carry long text, so they get a textarea instead of an input.
  LONG: { question: true, expected: true },

  // Fields whose value is a closed set. A select instead of a box, because the
  // engine refuses an unknown one at save and a free-text field invites it.
  // The first entry is the default the engine takes for an empty value.
  CHOICES: { match: ['equals', 'contains'] },

  async render(el) {
    el.innerHTML = `
      <div class="page-header"><div>
        <div class="page-title">Workflows</div>
        <div class="page-subtitle">Build a run, fire it, and watch every step land</div>
      </div></div>

      <div class="card">
        <div class="card-title">The flows — what is folded here</div>
        <div id="wf-list"><div class="skel skel-60"></div><div class="skel skel-80"></div></div>
        <div class="flex mt-16" style="gap:8px">
          <input class="input" id="wf-new" placeholder="a name for a new flow (lowercase, digits, - and _)" style="max-width:380px">
          <button class="btn" id="wf-start">Start one</button>
        </div>
      </div>

      <div id="wf-build"></div>
      <div id="wf-run"></div>
      <div id="wf-runs"></div>`;

    el.querySelector('#wf-start').onclick = () => this.start();
    el.querySelector('#wf-new').onkeydown = (e) => { if (e.key === 'Enter') this.start(); };
    await this.list();
  },

  // ---- the flows ---------------------------------------------------------

  // flow_list answers in prose, not JSON ("FLOWS — 1:" then one line each), so
  // this reads the line shape rather than pretending there is a schema. A line
  // it cannot read is still SHOWN, never dropped: a flow the page cannot parse
  // is exactly the one its owner needs to see.
  async list() {
    const box = document.getElementById('wf-list');
    if (!box) return;
    try {
      const r = await API.listFlows();
      const text = (r.flows || '').trim();
      if (!text || /no flows yet/i.test(text)) {
        box.innerHTML = `<div class="muted">No flows folded yet. Name one below and it opens empty.</div>`;
        return;
      }
      const rows = text.split('\n')
        .map(l => l.trim())
        .filter(l => l.startsWith('-'))
        .map(l => l.replace(/^-\s*/, ''));
      if (!rows.length) { box.innerHTML = `<pre class="wf-pre">${esc(text)}</pre>`; return; }
      box.innerHTML = rows.map(l => {
        const m = l.match(/^(\S+)\s+v(\d+)/);
        const name = m ? m[1] : l;
        const ver = m ? m[2] : '';
        return `<div class="wf-row">
          <div class="wf-row-main"><span class="wf-name">${esc(name)}</span>
            ${ver ? `<span class="badge badge-muted">v${esc(ver)}</span>` : ''}
            <span class="muted">${esc(l.replace(/^\S+\s+v\d+\s*·?\s*/, ''))}</span></div>
          <button class="btn btn-sm" data-open="${esc(name)}">Open</button>
        </div>`;
      }).join('');
      box.querySelectorAll('[data-open]').forEach(b => {
        b.onclick = () => this.open(b.getAttribute('data-open'));
      });
    } catch (e) {
      box.innerHTML = `<div class="wf-bad">The flows could not be read: ${esc(e.message)}</div>`;
    }
  },

  async open(name) {
    try {
      const r = await API.getFlow(name, 0);
      this.spec = JSON.parse(r.spec);
      if (!Array.isArray(this.spec.nodes)) this.spec.nodes = [];
      if (!Array.isArray(this.spec.edges)) this.spec.edges = [];
      this.run = null; this.verdict = '';
      this.build();
      this.runs();
      document.getElementById('wf-run').innerHTML = '';
    } catch (e) { toast('Could not open ' + name + ': ' + e.message); }
  },

  // A new flow opens EMPTY, with no node invented for it. A builder that
  // seeds a step is a builder that gets a step nobody meant.
  start() {
    const el = document.getElementById('wf-new');
    const name = (el.value || '').trim();
    if (!name) { toast('Give it a name first'); return; }
    if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(name)) {
      toast('The name law: lowercase, digits, - and _, starting with a letter or digit');
      return;
    }
    this.spec = { name: name, version: 0, budget_s: 300, nodes: [], edges: [] };
    this.run = null; this.verdict = '';
    el.value = '';
    this.build();
    document.getElementById('wf-run').innerHTML = '';
    document.getElementById('wf-runs').innerHTML = '';
  },

  // ---- the build ---------------------------------------------------------

  build() {
    const box = document.getElementById('wf-build');
    if (!box || !this.spec) return;
    const s = this.spec;
    const names = s.nodes.map(n => n.name).filter(Boolean);

    box.innerHTML = `
      <div class="card">
        <div class="card-title">The build — ${esc(s.name)}${s.version ? ' · v' + s.version : ' · not yet folded'}</div>

        <div class="flex mb-16" style="gap:16px;flex-wrap:wrap">
          <div class="form-group" style="margin:0">
            <div class="form-label">Budget (seconds)</div>
            <input class="input" id="wf-budget" type="number" min="1" value="${esc(String(s.budget_s || 300))}" style="width:140px">
          </div>
          <div class="muted" style="align-self:end;max-width:460px">
            The budget binds the whole run. Past it the verdict is OUT_OF_TIME
            and the nodes that did fire still stand — nothing is thrown away.
          </div>
        </div>

        <div class="wf-head">The steps</div>
        <div id="wf-nodes">${s.nodes.map((n, i) => this.nodeRow(n, i)).join('') ||
          '<div class="muted">No steps yet. Add one — it runs in the order the edges decide, not the order you typed.</div>'}</div>
        <div class="flex mt-16" style="gap:8px;flex-wrap:wrap">
          ${Object.keys(this.KINDS).map(k =>
            `<button class="btn btn-sm" data-add="${k}" title="${esc(this.KINDS[k].blurb)}">+ ${k}</button>`).join('')}
        </div>

        <div class="wf-head mt-16">How it steers</div>
        <div id="wf-edges">${s.edges.map((e, i) => this.edgeRow(e, i, names)).join('') ||
          '<div class="muted">No edges. With one step that is fine; with more, an unreached step is refused at save.</div>'}</div>
        <button class="btn btn-sm mt-16" id="wf-addedge" ${names.length < 2 ? 'disabled' : ''}>+ edge</button>

        ${this.varsBlock(s)}

        <div class="flex flex-between mt-16" style="gap:8px">
          <div class="muted">Saving folds a new version. The old one is kept whole, never rewritten.</div>
          <div class="flex" style="gap:8px">
            <button class="btn" id="wf-save">Save</button>
            <button class="btn btn-primary" id="wf-fire" ${s.version ? '' : 'disabled'}>Fire it</button>
          </div>
        </div>
        <div id="wf-msg"></div>
      </div>`;

    box.querySelectorAll('[data-add]').forEach(b => {
      b.onclick = () => this.addNode(b.getAttribute('data-add'));
    });
    box.querySelector('#wf-addedge').onclick = () => this.addEdge();
    box.querySelector('#wf-save').onclick = () => this.save();
    box.querySelector('#wf-fire').onclick = () => this.fire();
    box.querySelector('#wf-budget').onchange = (e) => {
      this.spec.budget_s = parseInt(e.target.value, 10) || 300;
    };
    this.wireRows(box);
  },

  nodeRow(n, i) {
    const k = this.KINDS[n.kind] || { fields: [], blurb: '' };
    return `<div class="wf-node">
      <div class="wf-node-head">
        <span class="badge badge-blue">${esc(n.kind)}</span>
        <input class="input wf-inline" data-n="${i}" data-f="name" value="${esc(n.name || '')}" placeholder="step name">
        <span class="muted wf-blurb">${esc(k.blurb)}</span>
        <button class="btn btn-sm btn-danger" data-del-n="${i}">remove</button>
      </div>
      ${k.fields.map(f => `
        <div class="wf-field">
          <div class="form-label">${esc(f)}</div>
          ${this.CHOICES[f]
            ? `<select class="select" data-n="${i}" data-f="${f}">${this.CHOICES[f].map(c =>
                `<option value="${esc(c)}"${(n[f] || this.CHOICES[f][0]) === c ? ' selected' : ''}>${esc(c)}</option>`).join('')}</select>`
            : this.LONG[f]
            ? `<textarea class="textarea" data-n="${i}" data-f="${f}" rows="2" placeholder="${esc(this.hint(n.kind, f))}">${esc(n[f] || '')}</textarea>`
            : `<input class="input" data-n="${i}" data-f="${f}" value="${esc(n[f] == null ? '' : String(n[f]))}" placeholder="${esc(this.hint(n.kind, f))}">`}
          ${f === 'match' ? `<div class="muted">${n[f] === 'contains'
            ? 'the answer passes if it CARRIES the text below — exact case, because a marker in machine output is uppercase and the same letters in prose are not (look for <code>RAN:</code>, not <code>ran</code>)'
            : 'the answer passes only if it IS the text below, whitespace and case aside'}</div>` : ''}
        </div>`).join('')}
    </div>`;
  },

  // The placeholder is where a reader learns what a field is FOR. These are
  // the flow package's own rules, not invented advice: a run node with no
  // objective and an eval node naming no node are both refused at save.
  hint(kind, f) {
    if (f === 'question' && kind === 'run') return 'the objective — this goes through the whole council';
    if (f === 'question') return 'what to ask';
    if (f === 'voice') return 'a model tag, e.g. llama3.2:latest (blank = the default)';
    if (f === 'node') return 'the step this checks — it must exist';
    // THIS LABEL USED TO SAY "what the answer should carry", which is
    // `contains` in words, while the engine only ever did `equals`. The coder
    // flow believed the label and its pass branch was unreachable for as long
    // as it existed. The field now says which test is being made, and `match`
    // beside it is how you choose.
    if (f === 'expected') return 'the marker the check looks for, e.g. RAN: — `match` above decides equals or contains';
    if (f === 'match') return 'equals';
    if (f === 'title') return 'what the hand is being asked to decide';
    if (f === 'seat') return 'a seat name from agents/';
    if (f === 'prompt') return 'a saved prompt name';
    if (f === 'version') return '0 = latest';
    if (f === 'method') return 'optional';
    return '';
  },

  edgeRow(e, i, names) {
    const opt = (sel) => names.map(n =>
      `<option value="${esc(n)}"${n === sel ? ' selected' : ''}>${esc(n)}</option>`).join('');
    const when = ['always', 'pass', 'fail'].map(w =>
      `<option value="${w}"${e.when === w ? ' selected' : ''}>${w}</option>`).join('');
    return `<div class="wf-edge">
      <select class="select" data-e="${i}" data-f="from">${opt(e.from)}</select>
      <span class="wf-arrow">→</span>
      <select class="select" data-e="${i}" data-f="to">${opt(e.to)}</select>
      <select class="select" data-e="${i}" data-f="when">${when}</select>
      <span class="muted wf-blurb">${e.when === 'always'
        ? 'fires whenever the step before it fired'
        : 'follows the check — ' + esc(e.when || '')}</span>
      <button class="btn btn-sm btn-danger" data-del-e="${i}">remove</button>
    </div>`;
  },

  wireRows(box) {
    box.querySelectorAll('[data-n]').forEach(inp => {
      inp.onchange = () => {
        const n = this.spec.nodes[parseInt(inp.getAttribute('data-n'), 10)];
        const f = inp.getAttribute('data-f');
        if (!n) return;
        n[f] = f === 'version' ? (parseInt(inp.value, 10) || 0) : inp.value;
        if (f === 'name') this.build();
      };
    });
    box.querySelectorAll('[data-e]').forEach(sel => {
      sel.onchange = () => {
        const e = this.spec.edges[parseInt(sel.getAttribute('data-e'), 10)];
        if (e) { e[sel.getAttribute('data-f')] = sel.value; this.build(); }
      };
    });
    box.querySelectorAll('[data-del-n]').forEach(b => {
      b.onclick = () => {
        const i = parseInt(b.getAttribute('data-del-n'), 10);
        const gone = this.spec.nodes[i].name;
        this.spec.nodes.splice(i, 1);
        // An edge to a step that no longer exists is refused at save, so it
        // goes with it rather than waiting to become a refusal nobody expects.
        this.spec.edges = this.spec.edges.filter(e => e.from !== gone && e.to !== gone);
        this.build();
      };
    });
    box.querySelectorAll('[data-del-e]').forEach(b => {
      b.onclick = () => {
        this.spec.edges.splice(parseInt(b.getAttribute('data-del-e'), 10), 1);
        this.build();
      };
    });
  },

  addNode(kind) {
    const base = { name: this.freshName(kind), kind: kind };
    if (kind === 'eval' && this.spec.nodes.length) {
      base.node = this.spec.nodes[this.spec.nodes.length - 1].name;
    }
    this.spec.nodes.push(base);
    // A second step with no edge would be unreachable and refused at save, so
    // the obvious edge is offered rather than left as a trap.
    if (this.spec.nodes.length > 1) {
      const prev = this.spec.nodes[this.spec.nodes.length - 2].name;
      this.spec.edges.push({ from: prev, to: base.name, when: 'always' });
    }
    this.build();
  },

  freshName(kind) {
    let i = 1, n = kind;
    const taken = new Set(this.spec.nodes.map(x => x.name));
    while (taken.has(n)) { i += 1; n = kind + '_' + i; }
    return n;
  },

  addEdge() {
    const names = this.spec.nodes.map(n => n.name);
    if (names.length < 2) return;
    this.spec.edges.push({ from: names[0], to: names[1], when: 'always' });
    this.build();
  },

  // ---- saving and firing -------------------------------------------------

  // The page does NOT pre-judge a spec. Validate lives in the LINE and its
  // refusals name the node and the reason; echoing a second opinion here is
  // how two validators drift apart. Whatever it says is what is shown.
  async save() {
    if (!this.spec) return;
    const msg = document.getElementById('wf-msg');
    msg.innerHTML = `<div class="muted mt-16">Folding…</div>`;
    try {
      const r = await API.saveFlow(this.spec.name, JSON.stringify(this.spec));
      msg.innerHTML = `<div class="wf-ok mt-16">${esc(r.text || 'saved')}</div>`;
      const m = (r.text || '').match(/v(\d+)/);
      if (m) this.spec.version = parseInt(m[1], 10);
      this.build();
      await this.list();
    } catch (e) {
      msg.innerHTML = `<div class="wf-bad mt-16">${esc(e.message)}</div>`;
    }
  },

  // WHAT THE FLOW ASKS OF THE HAND FIRING IT. Every {{var}} the steps render
  // that no step supplies from its own output, which is the only kind that has
  // to come from outside. ONLY the two fields the engine actually renders --
  // a node's question, and a prompt node's vars. A box for `expected` or a
  // gate's title would be offering to fill something nothing substitutes.
  openVars(s) {
    const own = new Set((s.nodes || []).map(n => 'out_' + n.name));
    const found = new Set();
    (s.nodes || []).forEach(n => {
      [n.question].concat(Object.values(n.vars || {})).forEach(v =>
        String(v || '').replace(/\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g, (_, k) => {
          if (!own.has(k)) found.add(k);
          return '';
        }));
    });
    return [...found].sort();
  },

  varsBlock(s) {
    const vars = this.openVars(s);
    if (!vars.length) return '';
    return `<div class="wf-head mt-16">What it needs from you</div>
      <div class="muted mb-16">The steps below use these and no step supplies
        them. A missing one is refused rather than guessed, so the run stops
        before it spends anything.</div>
      ${vars.map(v => `<div class="form-group">
        <div class="form-label">${esc(v)}</div>
        <input class="input" data-var="${esc(v)}" placeholder="what ${esc(v)} is, for this run">
      </div>`).join('')}`;
  },

  async fire() {
    if (!this.spec || this.busy) return;
    this.busy = true;
    // Read BEFORE the run panel is painted: these live in #wf-build, which
    // the paint below does not touch, and reading them first keeps it that way.
    const inputs = {};
    document.querySelectorAll('#wf-build [data-var]').forEach(i => {
      inputs[i.getAttribute('data-var')] = i.value;
    });
    const box = document.getElementById('wf-run');
    box.innerHTML = `<div class="card"><div class="card-title">The run, step by step</div>
      <div class="muted">Firing ${esc(this.spec.name)}… every step is a real call; this takes as long as it takes.</div></div>`;
    try {
      const r = await API.fireFlow(this.spec.name, JSON.stringify(inputs));
      const text = r.text || '';
      const id = (text.match(/f-\d{8}-\d{6}-[0-9a-f]{8}/) || [])[0] || '';
      const v = (text.match(/verdict:\s*([A-Z_]+)/) || [])[1]
             || (text.match(/:\s*([A-Z_]+)\s*·/) || [])[1] || '';
      this.run = id; this.verdict = v;
      this.paint(text);
      await this.runs();
    } catch (e) {
      box.innerHTML = `<div class="card"><div class="card-title">The run, step by step</div>
        <div class="wf-bad">${esc(e.message)}</div></div>`;
    } finally { this.busy = false; }
  },

  // A PAUSED run is the only place this page offers a decision, and it offers
  // exactly the two the engine accepts. There is no third button, and neither
  // of them is the default.
  paint(text) {
    const box = document.getElementById('wf-run');
    const paused = /PAUSED/.test(this.verdict || text);
    const bad = /FAIL|OUT_OF_TIME|STOPPED/.test(this.verdict || '');
    box.innerHTML = `
      <div class="card">
        <div class="card-title">The run, step by step
          ${this.verdict ? `<span class="badge ${paused ? 'badge-yellow' : bad ? 'badge-red' : 'badge-green'}">${esc(this.verdict)}</span>` : ''}
        </div>
        <pre class="wf-pre">${esc(text)}</pre>
        ${paused ? `
          <div class="wf-gate mt-16">
            <div class="wf-gate-title">This run stopped at a gate and is waiting on you.</div>
            <div class="muted">Nothing moves until you say so, and nothing here decides for you.</div>
            <div class="flex mt-16" style="gap:8px">
              <button class="btn btn-primary" id="wf-cont">Carry it on</button>
              <button class="btn btn-danger" id="wf-stop">Stop it here</button>
            </div>
          </div>` : ''}
        ${this.run ? `<div class="muted mt-16">run <span class="hash">${esc(this.run)}</span></div>` : ''}
      </div>`;
    if (paused) {
      box.querySelector('#wf-cont').onclick = () => this.resume('continue');
      box.querySelector('#wf-stop').onclick = () => this.resume('stop');
    }
  },

  async resume(decision) {
    if (!this.run) return;
    try {
      const r = await API.resumeFlow(this.run, decision);
      const text = r.text || '';
      this.verdict = (text.match(/verdict:\s*([A-Z_]+)/) || [])[1] || this.verdict;
      this.paint(text);
      await this.runs();
    } catch (e) { toast('The run could not be moved: ' + e.message); }
  },

  // ---- what already ran --------------------------------------------------

  async runs() {
    const box = document.getElementById('wf-runs');
    if (!box || !this.spec) return;
    try {
      const r = await API.listRuns(this.spec.name);
      const text = (r.runs || '').trim();
      box.innerHTML = text
        ? `<div class="card card-quiet"><div class="card-title">Earlier runs</div>
             <pre class="wf-pre">${esc(text)}</pre></div>`
        : '';
    } catch (e) { box.innerHTML = ''; }
  },
};

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
