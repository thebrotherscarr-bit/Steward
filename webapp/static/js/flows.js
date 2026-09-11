// ATLAS Flows — the DAG builder. Forms and tables only, no canvas lib:
// nodes and edges edit as rows, the graph previews as SVG, runs render
// as waterfalls. Gates pause for the hand — continue|stop, never more.
const Flows = {
  current: null,
  // Which worlds have their lines-of-work panel open. Kept here and not in
  // the DOM: repos() rebuilds every node in that card.
  open: {},

  async render(el) {
    el.innerHTML = `
      <div class="page-header"><div><div class="page-title">Flows</div>
      <div class="page-subtitle">DAGs with gates — branches declare, the queue runs one by one</div></div></div>
      <div class="card"><div class="card-title">The repositories — what is saved, what is not, and what you can do about it</div>
        <div id="repo-watch"><div class="loading">Reading both grounds...</div></div>
        <div class="muted mt-16">Every button here is your hand, not the machine's.
        Nothing fires on its own, nothing sends while the wall is shut, and
        nothing is thrown away without saying so first.</div>
      </div>
      <div class="grid-2 mt-16">
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
    await this.repos();
  },

  // THE OVERWATCH, IN PLAIN LANGUAGE (the operator, 2026-09-10: "all the
  // other stupid fucking jargon from github and turn it into plain language
  // for me, so it isnt stupid").
  //
  // Every fact below is read off the `git` tool, one call per carried world,
  // and RE-WORDED -- never re-judged. "ahead 2" is not wrong, it is just not
  // English; a person wants to know whether the work he did is safe. ESTATE
  // LAW 10 is the rule this satisfies: plain English, honest logs.
  //
  // NOTHING HERE ACTS. No commit, no push, no fetch -- a read that cannot
  // change the ground can be looked at without care, and the acting path
  // stays where the gate already is (git_cycle, through the council).
  plain(g) {
    const L = [];
    L.push(['You are on', g.branch ? `the ${escHtml(g.branch)} line of work` : 'no branch']);

    const subj = g.subject ? `“${escHtml(g.subject)}”` : '(no message)';
    L.push(['Last save', `${subj} — ${escHtml(g.head || '?')}, ${escHtml(g.when || 'unknown')}`]);

    // WHAT IS NOT SAVED. `changed` is work git already knows about;
    // `untracked` is a file it has never seen, which is the one people lose.
    if (!g.dirty && !g.untracked) {
      L.push(['Unsaved work', 'none — everything here is saved']);
    } else {
      const bits = [];
      if (g.changed) bits.push(`${g.changed} file${g.changed === 1 ? '' : 's'} changed since the last save`);
      if (g.untracked) bits.push(`${g.untracked} file${g.untracked === 1 ? '' : 's'} git has never seen before`);
      L.push(['Unsaved work', bits.join(', ')]);
    }

    // AHEAD / BEHIND, which is the pair nobody can ever remember.
    let gh;
    if (!g.upstream) gh = 'this line of work is not linked to GitHub at all';
    else if (!g.ahead && !g.behind) gh = 'in step — GitHub has exactly what you have';
    else {
      const bits = [];
      if (g.ahead) bits.push(`${g.ahead} save${g.ahead === 1 ? '' : 's'} here that GitHub does not have yet`);
      if (g.behind) bits.push(`${g.behind} save${g.behind === 1 ? '' : 's'} on GitHub that you do not have`);
      gh = bits.join(' · ');
    }
    L.push(['GitHub', gh]);

    L.push(['Sending', g.remote_allowed
      ? 'allowed'
      : 'OFF — sending and fetching refuse by name until you open that wall']);
    return L;
  },

  async repos() {
    const box = document.getElementById('repo-watch');
    if (!box) return;
    let worlds = [];
    try {
      const m = await App.tool('muster', {});
      worlds = (m || '').split(String.fromCharCode(10)).map(s => s.trim())
        .filter(s => s && !s.endsWith(':'));
    } catch { box.innerHTML = '<div class="empty-text">MCP unreachable.</div>'; return; }
    if (!worlds.length) { box.innerHTML = '<div class="empty-text">No worlds are carried.</div>'; return; }

    const cards = [];
    for (const w of worlds) {
      let g;
      try { g = JSON.parse(await App.tool('git', { project: w })); }
      catch { cards.push(`<div class="mt-16"><b>${escHtml(w)}</b><div class="muted">could not be read</div></div>`); continue; }
      if (!g.is_repo) { cards.push(`<div class="mt-16"><b>${escHtml(w)}</b><div class="muted">not a repository</div></div>`); continue; }
      const rows = this.plain(g).map(([k, v]) =>
        `<tr><td class="muted" style="padding-right:16px;white-space:nowrap">${escHtml(k)}</td><td>${v}</td></tr>`
      ).join('');
      // The files themselves, named AND OPENABLE. A count tells you something
      // is unsaved; the list tells you what; only opening it tells you whether
      // you meant to. Same shape Records uses for a document -- click the row,
      // get the thing whole -- because it is the same question.
      //
      // The two-letter code is git's porcelain contract, and it is the last
      // jargon on this page, so it is translated here and nowhere shown raw.
      const files = (g.files || []).map(f => {
        const code = f.slice(0, 2).trim();
        const path = f.slice(2).trim();
        const what = code === '??' ? 'never saved before'
          : code === 'M' ? 'changed'
          : code === 'A' ? 'newly added'
          : code === 'D' ? 'deleted'
          : code === 'R' ? 'renamed'
          : code;
        return `<div class="chat-session repo-file" data-w="${escHtml(w)}" data-f="${escHtml(path)}">`
          + `<span class="muted" style="display:inline-block;min-width:150px">${escHtml(what)}</span>`
          + escHtml(path) + `</div>`;
      }).join('');
      cards.push(`<div class="mt-16"><b>${escHtml(w)}</b>`
        + `<table style="margin-top:6px">${rows}</table>`
        + this.controls(w, g)
        + (files ? `<div class="mt-16">${files}</div>` : '')
        + `<div id="lines-${escHtml(w)}"></div>`
        + `</div>`);
    }
    box.innerHTML = cards.join('') + '<div id="repo-diff"></div>';
    box.querySelectorAll('.repo-file').forEach(d => {
      d.onclick = () => this.diff(d.dataset.w, d.dataset.f);
    });
    box.querySelectorAll('[data-act]').forEach(b => {
      b.onclick = () => this.act(b.dataset.act, b.dataset.w);
    });
    for (const w of worlds) this.lines(w);
  },

  // THE BUTTONS. Each one is a door tool, and each tool refuses in words the
  // moment it should -- a save with no message, a send through a shut wall, a
  // switch over unsaved work. The glass does not re-judge any of that; it
  // shows the refusal. The one thing it DOES decide is what to grey out, so a
  // button that cannot work says why before it is pressed rather than after.
  controls(w, g) {
    const q = escHtml(w);
    const walled = !g.remote_allowed;
    const nothingToSend = !g.ahead;

    const sendWhy = walled
      ? 'Sending is OFF — the estate wall (MANJUEL_GIT_REMOTE) is shut'
      : nothingToSend ? 'Nothing to send — GitHub already has every save here'
        : `Send ${g.ahead} save${g.ahead === 1 ? '' : 's'} to GitHub`;
    const fetchWhy = walled
      ? 'Fetching is OFF — the estate wall (MANJUEL_GIT_REMOTE) is shut'
      : g.dirty ? 'There is unsaved work here — save it first'
        : !g.behind ? 'Nothing to fetch — you already have every save on GitHub'
          : `Take the ${g.behind} save${g.behind === 1 ? '' : 's'} GitHub has`;

    return `<div class="mt-16">
      <input type="text" id="msg-${q}" placeholder="say what this save is, in your own words" />
      <div class="flex">
        <button class="btn btn-sm" data-act="save" data-w="${q}"
          title="Save every change in this world under the message above">Save the work</button>
        <button class="btn btn-sm" data-act="send" data-w="${q}"
          ${walled || nothingToSend ? 'disabled' : ''} title="${escHtml(sendWhy)}">Send to GitHub</button>
        <button class="btn btn-sm" data-act="fetch" data-w="${q}"
          ${walled || g.dirty || !g.behind ? 'disabled' : ''} title="${escHtml(fetchWhy)}">Take from GitHub</button>
        <button class="btn btn-sm" data-act="lines" data-w="${q}"
          title="The lines of work in this world">Lines of work</button>
      </div>
      <div id="out-${q}" class="muted"></div>
    </div>`;
  },

  // ACTING. One place, so every button reports the same way: the tool's own
  // words, verbatim, and then a re-read of the world so the panel never shows
  // a state the ground has already left.
  //
  // THE ANSWER OUTLIVES THE REFRESH. repos() rebuilds this whole card, which
  // destroys the element the answer was just written into -- so the text is
  // held, the card is rebuilt, and only then is it put back. A first cut said
  // it and then wiped it half a second later, which reads exactly like the
  // button doing nothing.
  async act(what, w) {
    const say = t => {
      const out = document.getElementById('out-' + w);
      if (out) out.innerHTML = `<pre>${escHtml(t)}</pre>`;
    };
    let answer;
    try {
      if (what === 'save') {
        const box = document.getElementById('msg-' + w);
        const msg = (box && box.value || '').trim();
        if (!msg) { say('Say what the save is first — the message is the record of why.'); return; }
        say('Saving...');
        answer = await App.tool('git_commit', { project: w, message: msg });
      } else if (what === 'send') {
        say('Sending...');
        answer = await App.tool('git_push', { project: w });
      } else if (what === 'fetch') {
        say('Fetching...');
        answer = await App.tool('git_pull', { project: w });
      } else if (what === 'lines') {
        this.open[w] = !this.open[w];
        await this.lines(w);
        return;
      }
    } catch (e) { say('Refused: ' + e.message); return; }
    await this.repos();
    say(answer);
  },

  // THE LINES OF WORK. A branch is a line of work, main is the main line,
  // opening one is starting it and closing one is finishing with it. The
  // words are the operator's; the jargon stays on the far side of the wire.
  //
  // WHICH WORLDS ARE OPEN IS REMEMBERED ON THE OBJECT, not on the element.
  // repos() replaces every node in this card, so a flag stored in the DOM is
  // erased by the very refresh that follows each action -- the panel would
  // slam shut every time you used it.
  async lines(w) {
    const box = document.getElementById('lines-' + w);
    if (!box) return;
    if (!this.open[w]) { box.innerHTML = ''; return; }
    box.innerHTML = '<div class="loading">Reading the lines...</div>';
    let d;
    try { d = JSON.parse(await App.tool('git_branch', { project: w, action: 'list' })); }
    catch (e) { box.innerHTML = `<div class="empty-text">Could not read them: ${escHtml(e.message)}</div>`; return; }

    const rows = (d.branches || []).map(b => {
      const tags = [];
      if (b.current) tags.push('you are here');
      if (b.main) tags.push('the main line');
      tags.push(b.sent ? 'on GitHub' : 'only on this machine');
      const act = b.current ? ''
        : `<button class="btn btn-sm" data-line="switch" data-w="${escHtml(w)}" data-n="${escHtml(b.name)}">Move here</button>`
        + `<button class="btn btn-sm" data-line="close" data-w="${escHtml(w)}" data-n="${escHtml(b.name)}">Finish with it</button>`;
      return `<tr><td style="padding-right:12px;white-space:nowrap"><b>${escHtml(b.name)}</b></td>`
        + `<td class="muted" style="padding-right:12px">${escHtml(tags.join(' · '))}</td>`
        + `<td class="muted" style="padding-right:12px">${escHtml(b.when || '')}</td>`
        + `<td>${act}</td></tr>`;
    }).join('');

    box.innerHTML = `<div class="card-title mt-16">Lines of work</div>`
      + `<table>${rows}</table>`
      + `<div class="flex mt-16">`
      + `<input type="text" id="newline-${escHtml(w)}" placeholder="name a new line, e.g. fix/the-door" />`
      + `<button class="btn btn-sm" data-line="new" data-w="${escHtml(w)}">Start a new line</button></div>`
      + `<div id="lineout-${escHtml(w)}" class="muted"></div>`;

    box.querySelectorAll('[data-line]').forEach(b => {
      b.onclick = () => this.line(b.dataset.line, b.dataset.w, b.dataset.n);
    });
  },

  async line(action, w, name) {
    const say = t => {
      const out = document.getElementById('lineout-' + w);
      if (out) out.innerHTML = `<pre>${escHtml(t)}</pre>`;
    };
    if (action === 'new') {
      const box = document.getElementById('newline-' + w);
      name = (box && box.value || '').trim();
      if (!name) { say('Name the line first.'); return; }
    }
    let answer;
    try {
      answer = await App.tool('git_branch', { project: w, action: action, name: name });
    } catch (e) { say('Refused: ' + e.message); return; }
    // The card first (the branch may have moved, which changes every row
    // above), then the lines, then the answer into the element both rebuilt.
    await this.repos();
    say(answer);
  },

  // ONE CHANGE, SERVED WHOLE. Read-only: git_diff is declared Writes:false at
  // the door and runs nothing that stages, commits or reaches a remote.
  async diff(world, file) {
    const box = document.getElementById('repo-diff');
    if (!box) return;
    box.innerHTML = `<div class="card-title mt-16">${escHtml(world)} · ${escHtml(file)}</div>`
      + '<div class="loading">Reading...</div>';
    try {
      const text = await App.tool('git_diff', { project: world, file: file });
      box.innerHTML = `<div class="card-title mt-16">${escHtml(world)} · ${escHtml(file)}</div>`
        + `<pre>${escHtml(text || '(no change recorded)')}</pre>`;
    } catch (e) {
      box.innerHTML = `<div class="card-title mt-16">${escHtml(world)} · ${escHtml(file)}</div>`
        + `<div class="empty-text">Could not read it: ${escHtml(e.message)}</div>`;
    }
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
