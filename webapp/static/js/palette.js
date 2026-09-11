// ATLAS palette — every page and the engine's two verbs, one keystroke away.
//
// A console lived in all day is navigated by hand far more than it is read, and
// this one had no keyboard path at all: eight pages, all of them a mouse trip
// to the sidebar, and the two things done most often (boot an engine, close the
// sitting) buried on a card. Ctrl+K / Cmd+K, type three letters, Enter.
//
// IT NAVIGATES AND IT BOOTS. Nothing else. A palette that can run anything is a
// second command surface to learn and a second place for a destructive verb to
// hide; the box on the Dashboard is where objectives go, and it already takes
// words. Close is here because it PAYS THE TOLL, which is the one routine act
// the record depends on and the easiest to forget.
//
// IT OPENS WHERE THE HAND IS. The estate's own rule about gates: nothing fires
// on its own. Enter runs the highlighted row and nothing else does; Escape
// leaves without a trace; clicking away is the same as Escape.
const Palette = {
  open: false,
  items: [],
  hit: 0,

  bind() {
    if (this._bound) return;
    this._bound = true;
    document.addEventListener('keydown', (e) => {
      // The one global binding in this console. Checked on the event rather
      // than the platform: a Mac keyboard on a Windows box, and the reverse,
      // both happen and neither should have to learn the other's key.
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        this.toggle();
        return;
      }
      if (!this.open) return;
      if (e.key === 'Escape') { e.preventDefault(); this.close(); return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); this.move(1); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); this.move(-1); return; }
      if (e.key === 'Enter') { e.preventDefault(); this.run(); return; }
    });
  },

  // WHAT IS OFFERED IS WHAT IS TRUE RIGHT NOW. The engine rows read Run's live
  // state rather than a remembered one, so a palette opened after a crash does
  // not offer to close a sitting that is already closed.
  build() {
    const go = (path) => () => { history.pushState(null, '', path); App.router(); };
    const pages = [...document.querySelectorAll('.nav-link')].map(a => ({
      label: a.textContent.trim(),
      note: 'page',
      run: go(a.getAttribute('href')),
    }));
    const engine = [];
    if (Run.engineOpen) {
      engine.push({
        label: 'Close the sitting',
        note: 'pays its toll and reaps the engine · sitting ' + (Run.sitting || '?'),
        run: () => { go('/')(); setTimeout(() => Home.closeSitting(), 60); },
      });
      engine.push({
        label: 'Reboot the engine',
        note: 'closes this sitting and opens a fresh one',
        run: () => { go('/')(); setTimeout(() => Home.boot(), 60); },
      });
    } else {
      engine.push({
        label: 'Boot an engine',
        note: 'opens a sitting on ' + (Run.world || 'this world'),
        run: () => { go('/')(); setTimeout(() => Home.boot(), 60); },
      });
    }
    return engine.concat(pages);
  },

  toggle() { this.open ? this.close() : this.show(); },

  show() {
    this.all = this.build();
    this.items = this.all;
    this.hit = 0;
    this.open = true;
    let box = document.getElementById('palette');
    if (!box) {
      box = document.createElement('div');
      box.id = 'palette';
      document.body.appendChild(box);
    }
    box.innerHTML = `
      <div class="pal-backdrop" id="pal-backdrop"></div>
      <div class="pal-box" role="dialog" aria-label="Command palette">
        <input id="pal-input" class="pal-input" type="text" autocomplete="off"
               placeholder="Go to a page, or boot the engine" aria-label="Search commands" />
        <div id="pal-list" class="pal-list"></div>
        <div class="pal-foot">
          <span><kbd>&uarr;</kbd><kbd>&darr;</kbd> move</span>
          <span><kbd>enter</kbd> go</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>`;
    box.hidden = false;
    document.getElementById('pal-backdrop').onclick = () => this.close();
    const input = document.getElementById('pal-input');
    input.oninput = () => this.filter(input.value);
    input.focus();
    this.paint();
  },

  close() {
    this.open = false;
    const box = document.getElementById('palette');
    if (box) { box.hidden = true; box.innerHTML = ''; }
  },

  // Substring over the label and its note, in order. Not fuzzy: a fuzzy match
  // on a list this short mostly buys surprising ranking, and the labels are
  // words he already knows because they are the nav.
  filter(q) {
    const s = (q || '').trim().toLowerCase();
    this.items = !s ? this.all
      : this.all.filter(i => (i.label + ' ' + i.note).toLowerCase().includes(s));
    this.hit = 0;
    this.paint();
  },

  move(d) {
    if (!this.items.length) return;
    this.hit = (this.hit + d + this.items.length) % this.items.length;
    this.paint();
  },

  run() {
    const item = this.items[this.hit];
    if (!item) return;
    this.close();
    item.run();
  },

  paint() {
    const list = document.getElementById('pal-list');
    if (!list) return;
    if (!this.items.length) {
      list.innerHTML = '<div class="pal-none">Nothing here matches that. '
        + 'The box on the Dashboard takes anything else.</div>';
      return;
    }
    list.innerHTML = this.items.map((i, n) => `
      <div class="pal-row${n === this.hit ? ' on' : ''}" data-n="${n}">
        <span class="pal-label">${escHtml(i.label)}</span>
        <span class="pal-note">${escHtml(i.note)}</span>
      </div>`).join('');
    list.querySelectorAll('[data-n]').forEach(r => {
      r.onmousemove = () => { const n = +r.dataset.n; if (n !== this.hit) { this.hit = n; this.paint(); } };
      r.onclick = () => { this.hit = +r.dataset.n; this.run(); };
    });
    const on = list.querySelector('.pal-row.on');
    if (on) on.scrollIntoView({ block: 'nearest' });
  },
};
