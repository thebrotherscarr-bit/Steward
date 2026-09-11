// ATLAS Flows — version control, and every way into it.
//
// This was the DAG builder. The builder came off 2026-09-10 ("not used, wipe
// it") and the page is now the one place git lives: the per-world overwatch in
// plain language, and the council path beneath it. Its routes and strokes all
// stand, so the builder is a render away if it is ever wanted.
const Flows = {
  current: null,
  // Which worlds have their lines-of-work panel open. Kept here and not in
  // the DOM: repos() rebuilds every node in that card.
  open: {},

  async render(el) {
    el.innerHTML = `
      <div class="page-header"><div><div class="page-title">Version control</div>
      <div class="page-subtitle">What is saved, what is not, and every way to move it</div></div></div>

      <div class="card"><div class="card-title">The repositories — what is saved, what is not, and what you can do about it</div>
        <div id="repo-watch"><div class="skel skel-60"></div><div class="skel skel-80"></div><div class="skel skel-40"></div></div>
        <div class="muted mt-16">Every button here is your hand, not the machine's.
        Nothing fires on its own, nothing sends while the wall is shut, and
        nothing is thrown away without saying so first.</div>
      </div>

      <!-- THE SAME REPOSITORY, THE OTHER WAY IN. The buttons above call the
           door directly and work with no engine standing. This card sends the
           objective through the COUNCIL instead: the law gate stamps it, the
           Router runs the skill, and the turn lands in the record like any
           other. Two paths on purpose — the operator, 2026-09-10: "there is
           a series of redundancies.. its called safety, bud."
           Moved here from the Dashboard the same day. -->
      <div class="card" id="flow-council-card" hidden>
        <div class="card-header">
          <span class="card-title">Through the council</span>
          <span class="flex" id="flow-council-controls"></span>
        </div>
        <div id="flow-council"></div>
      </div>

      <!-- Recent came with the repository card (2026-09-10). It reads Chat's
           own thread, so it cannot disagree with what he can scroll back and
           read for himself. -->
      <div class="card" id="flow-recent-card" hidden>
        <div class="card-title">Recent</div>
        <div id="flow-recent"></div>
      </div>`;
    await this.repos();
    await this.readGit();
    // THE THREAD IS RESTORED BEFORE IT IS READ. Chat.thread is per-tab and
    // empty on a fresh load; the Dashboard refills it from the settings store
    // on render, so Recent was full there and blank here for anyone who landed
    // on this page first. Home's own restore is reused rather than copied --
    // it is a no-op when the thread is already held, and its render guard
    // means the dashboard element it usually paints is simply not found.
    await Home.showKeptThread();
    this.paintRecent();
  },

  // The last few things he asked for, read off Chat's own thread.
  //
  // CLICKING ONE STILL FILLS THE BOX, and the box is on the Dashboard now.
  // It used to write straight into `home-input`, which does not exist on this
  // page -- so the objective is stashed on Home and the router is sent there,
  // and Home's render picks it up. Nothing is RUN by a click: it lands in the
  // box for him to read and press, exactly as it did before it moved.
  paintRecent() {
    const said = (Chat.thread || []).filter(m => m.who === 'him').slice(-5).reverse();
    const card = document.getElementById('flow-recent-card');
    const box = document.getElementById('flow-recent');
    if (!card || !box) return;
    card.hidden = !said.length;
    box.innerHTML = said.map(m => `
      <div class="home-recent-row" data-say="${escHtml(m.text)}">
        <span class="home-recent-text">${escHtml(m.text)}</span>
      </div>`).join('');
    box.querySelectorAll('[data-say]').forEach(r => {
      r.onclick = () => {
        Home.pending = r.dataset.say;
        history.pushState(null, '', '/');
        App.router();
      };
    });
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

  // THE LAST JARGON ON THE PAGE, and a first cut left half of it standing.
  //
  // git's porcelain code is TWO columns, not one: X is what is staged and Y
  // is what is changed since. Translating `code.trim()` against a map of
  // single letters worked for " M" and "?? " and then printed a raw **MM**
  // for a file that was both staged and changed again -- which is exactly the
  // kind of two-letter shrug this page exists to stop. Both columns are read
  // now, and anything genuinely unrecognised says so in words rather than
  // showing its code.
  said(xy) {
    const x = xy[0] || ' ', y = xy[1] || ' ';
    if (x === '?' ) return 'never saved before';
    if (x === '!' ) return 'deliberately ignored';
    if (x === 'U' || y === 'U') return 'two versions disagree — needs your decision';
    const word = { M: 'changed', A: 'newly added', D: 'deleted',
                   R: 'renamed', C: 'copied', T: 'type changed' };
    const staged = word[x], after = word[y];
    if (staged && after) return `${staged}, and ${after} again since`;
    if (staged) return `${staged}, ready to save`;
    if (after) return after;
    return 'changed somehow';
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
        const path = f.slice(2).trim();
        const what = this.said(f.slice(0, 2));
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
      <input type="text" class="input mb-16" id="msg-${q}" placeholder="say what this save is, in your own words" />
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
      + `<input type="text" class="input mb-16" id="newline-${escHtml(w)}" placeholder="name a new line, e.g. fix/the-door" />`
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


  // ---- THE COUNCIL PATH ---------------------------------------------------
  //
  // Lifted whole from the Dashboard, 2026-09-10 ("this needs to go with the
  // other github stuff"). The buttons in the overwatch above call the door
  // and need no engine; these send an objective through the COUNCIL, where the
  // law gate stamps it and the run lands in the record.
  //
  // THE ELEMENTS ARE FOUND AFTER THE AWAIT, NEVER BEFORE IT. Captured up top,
  // they point at DETACHED nodes if the page changes during the round trip --
  // and writing innerHTML into a detached node SUCCEEDS, so the throw lands a
  // line later on a null lookup. That cost a constant console error on the
  // Dashboard until it was found the same day.
  async readGit() {
    if (!document.getElementById('flow-council-card')) return;
    let g, err;
    try { g = JSON.parse(await App.tool('git', {})); }
    catch (e) { err = e; }

    const card = document.getElementById('flow-council-card');
    const box = document.getElementById('flow-council');
    const bar = document.getElementById('flow-council-controls');
    if (!card || !box || !bar) return;
    card.hidden = false;

    if (err) {
      box.innerHTML = `<div class="eng-row eng-bad">git could not be read:
        ${escHtml(err.message || 'refused')}<span class="brief-src">git</span></div>`;
      bar.innerHTML = '';
      return;
    }
    this._git = g;

    if (!g.is_repo) {
      box.innerHTML = `<div class="eng-row">${escHtml(g.note || 'not a repository')}
        <span class="brief-src">git</span></div>`;
      bar.innerHTML = '';
      return;
    }

    const where = Run.engineOpen
      ? `the council is standing · sitting ${escHtml(String(Run.sitting || '?'))}`
      : 'no engine is open, so this path cannot run · boot one on the Dashboard';
    box.innerHTML = `<div class="eng-row">
      Same repository, sent through the council instead of straight to the door:
      the law gate stamps the objective, the Router runs the skill, and the turn
      is written into the record like any other.
      <div class="muted" style="margin-top:6px">${where}</div>
      <span class="brief-src">git</span></div>`;

    bar.innerHTML = `<input id="git-msg" class="input git-msg" type="text"
        placeholder="what changed (optional — the council writes one if you don't)" />
      <button class="btn btn-sm ${g.dirty ? 'btn-primary' : ''}" id="git-commit"
        ${g.dirty && Run.engineOpen ? '' : 'disabled'}>Commit</button>
      <button class="btn btn-sm" id="git-push"
        ${g.remote_allowed && g.ahead && Run.engineOpen ? '' : 'disabled'}>Push</button>`;
    const commit = bar.querySelector('#git-commit');
    const push = bar.querySelector('#git-push');
    if (!commit || !push) return;
    commit.title = !Run.engineOpen ? 'no engine is open — boot one on the Dashboard'
      : g.dirty ? 'send the commit through the council' : 'nothing to commit';
    commit.onclick = () => this.commit();
    push.title = !g.remote_allowed
      ? 'sending is walled by MANJUEL_GIT_REMOTE (the estate, not your credentials)'
      : !Run.engineOpen ? 'no engine is open — boot one on the Dashboard'
      : (g.ahead ? 'send ' + g.ahead + ' save(s) to the remote' : 'nothing to send');
    push.onclick = () => this.push();
  },

  commit() {
    // HIS OWN PHRASING, from the record: a quoted message reads the way he
    // types one, and an empty field falls back to what already works. The
    // first wrapper read "Commit the working tree with this message: X" and
    // the Router passed that WHOLE SENTENCE as the message.
    const msg = (document.getElementById('git-msg') || {}).value || '';
    this.ask(msg.trim() ? `git commit: "${msg.trim()}"` : 'git commit');
  },

  push() {
    const g = this._git || {};
    if (!g.remote_allowed) {
      toast('Sending is walled by MANJUEL_GIT_REMOTE', 'error');
      return;
    }
    this.ask('Push the committed work to the remote.');
  },

  // One objective, into the same loop as anything he types. The thread is
  // Chat's, shared: the Dashboard and Chat both render it, so the turn is
  // watchable from either even though it was started here.
  ask(objective) {
    if (!Run.engineOpen) { toast('No engine is open — boot one on the Dashboard', 'error'); return; }
    if (Run.running) { toast('A turn is already running', 'error'); return; }
    Chat.thread.push({ who: 'him', text: objective });
    Chat.thread.push({ who: 'council', text: '', live: true });
    Run.start({ objective });
    toast('Sent to the council — the run is on the Dashboard');
  },

  // THE FLOW BUILDER CAME OFF, 2026-09-10 ("not used, wipe it"). The
  // registry, editor, SVG graph, fire/resume, the runs table, compare and
  // replay, and the town board — all rendered and none were ever used;
  // this page is version control now. NOTHING WAS DELETED BEHIND THEM: the
  // /api/flows routes, flow.go, run.go and their 2 packages of strokes all
  // stand, so a builder is a render away if it is ever wanted.
};
