// Run — the client for one council turn, shared by the pages that show it.
//
// A turn goes into the world's own Manjuel process, so the sealed law gate
// stamps it before any model reads a word, the one Router executes the tools,
// the dedup refuses a repeat, and the recompose puts every failure into the
// delivery. This file owns the wire and the state; it draws nothing.
//
// TWO SURFACES READ IT, and the operator drew the line between them
// (2026-09-09): "this looks like the evals loops. lets put it there, rebuild
// the chat page clean."
//
//   Chat  (chat.js)  the conversation — his message, the answer, and one
//                    honest line of what is happening while it streams.
//   Evals (app.js)   the run itself — every seat, every tool, every result,
//                    the per-seat table, the transcript. The inspection.
//
// Both read THIS object, so the two pages can never disagree about what ran.
//
// PROTOCOL 1's seventeen, verbatim from manjuel/serve.py:
//   opened text run report seat token tool tool_result needs_answer
//   delivery refused aborted cancelled unreachable error note closed
//
// They all arrive on ONE SSE frame (`event: engine`) with the kind inside, so
// an event this file has never heard of still lands and is kept. EventSource
// has no wildcard listener; naming frames per-kind would mean the glass
// silently loses anything the core adds later, and on a surface whose whole
// claim is "this is what actually ran", a dropped event looks exactly like
// nothing having happened.
const Run = {
  es: null,
  running: false,
  listening: false,
  mic: null,
  engineOpen: false,
  world: '',
  sitting: '',
  pending: '',
  unreachable: false,

  // The current (or most recent) turn. Evals reads this AFTER the fact, which
  // is why it is never cleared when the stream closes.
  turn: null,
  subs: [],

  // ---- who is watching ----------------------------------------------------

  on(fn) { if (this.subs.indexOf(fn) < 0) this.subs.push(fn); },
  off(fn) { this.subs = this.subs.filter(f => f !== fn); },
  emit(what) { for (const f of this.subs.slice()) { try { f(what, this); } catch {} } },

  // ---- is there an engine standing ----------------------------------------

  // Asked before a send box is offered, so a closed world is a disabled
  // control with a reason rather than a turn that fails.
  async check() {
    this.restore();
    try {
      const r = await fetch(API.base + '/council/state').then(x => x.json());
      this.engineOpen = !!r.open;
      this.world = r.world || '';
      this.sitting = r.sitting || '';
      this.pending = r.pending || '';
      this.unreachable = false;
    } catch {
      this.engineOpen = false;
      this.world = '';
      this.sitting = '';
      this.pending = '';
      this.unreachable = true;
    }
    this.emit('state');
    return this.engineOpen;
  },

  // ---- the wire -----------------------------------------------------------

  start(params) {
    if (this.running) return;
    // A new turn starts a new record. The old one is replaced, never merged:
    // two turns in one trace would misreport what either run did.
    this.turn = {
      objective: params.objective || params.answer || '',
      answering: !!params.answer,
      events: [], seats: [], tools: [], notes: [],
      answer: '', delivery: null, waiting: null,
      started: Date.now(), ended: null, verdict: '', dropped: 0, refusal: '',
      pipeline: '', transcript: ''
    };
    this.running = true;
    this.emit('start');

    const es = new EventSource(API.base + '/council/stream?' + new URLSearchParams(params));
    es.addEventListener('engine', (e) => {
      let d; try { d = JSON.parse(e.data); } catch { return; }
      this.absorb(d.event || 'unnamed', d);
    });
    es.addEventListener('stream_end', (e) => {
      let d = {}; try { d = JSON.parse(e.data); } catch {}
      if (this.turn) this.turn.dropped = d.dropped || 0;
      this.finish(d.waiting ? 'waiting' : 'done');
    });
    es.addEventListener('stream_error', (e) => {
      let d = {}; try { d = JSON.parse(e.data); } catch {}
      if (this.turn) this.turn.refusal = d.error || 'refused';
      this.finish('refused');
    });
    es.onerror = () => {
      if (!this.running) return;
      if (this.turn) {
        this.turn.refusal = 'the stream broke — the turn may still be running inside the engine';
      }
      this.finish('broke');
    };
    this.es = es;
  },

  finish(verdict) {
    this.running = false;
    try { if (this.es) this.es.close(); } catch {}
    this.es = null;
    if (this.turn) {
      this.turn.ended = Date.now();
      if (!this.turn.verdict) this.turn.verdict = verdict;
    }
    this.keep();
    this.emit('end');
  },

  // THE TURN OUTLIVES THE PAGE. Chat delivers, the operator walks to Evals
  // to inspect, and the evidence has to still be there. Kept per tab, in
  // this viewer's own browser, and sent nowhere.
  KEY: 'atlas.run.last',

  keep() {
    if (!this.turn) return;
    try {
      sessionStorage.setItem(this.KEY, JSON.stringify(this.turn));
    } catch {
      // Over quota (a long run carries hundreds of events). Keep the turn
      // WITHOUT its events and say so on its face -- a trace that quietly
      // lost its record would read as a run that did almost nothing.
      try {
        const thin = Object.assign({}, this.turn, { events: [], thinned: true });
        sessionStorage.setItem(this.KEY, JSON.stringify(thin));
      } catch {}
    }
  },

  restore() {
    if (this.turn) return;
    try {
      const raw = sessionStorage.getItem(this.KEY);
      if (raw) this.turn = JSON.parse(raw);
    } catch {}
  },

  // Drops the READER, not the run. A closed glass does not cancel the
  // council's work; only run_cancel does that.
  drop() {
    try { if (this.es) this.es.close(); } catch {}
    this.es = null;
    this.running = false;
  },

  // hear() captures one spoken turn through the core's voice.py -- the same
  // compiled whisper the REPL's /chat uses, on this machine, holding this
  // machine's microphone. No audio reaches the browser or the network.
  //
  // The words come back to the CALLER, not to the council. Whoever asked puts
  // them in a box for him to read and send: a microphone that fired objectives
  // on its own would be a gate nobody holds (RULE 6).
  hear(onNote, onHeard, onFail) {
    if (this.listening || this.running) return;
    this.listening = true;
    this.emit('state');
    const es = new EventSource(API.base + '/council/listen');
    es.addEventListener('engine', (e) => {
      let d; try { d = JSON.parse(e.data); } catch { return; }
      // voice.py's own words -- "listening — speak; the turn ends when you go
      // quiet", then "2.3s heard — transcribing…". Shown verbatim; this layer
      // has nothing truer to say about a microphone than voice.py does.
      if (d.event === 'note') onNote(d.text || '');
      if (d.event === 'error') { es.close(); this.listening = false; this.emit('state'); onFail(d.text || 'the microphone failed'); }
      if (d.event === 'heard') { es.close(); this.listening = false; this.emit('state'); onHeard(d.text || ''); }
    });
    es.addEventListener('stream_error', (e) => {
      let d = {}; try { d = JSON.parse(e.data); } catch {}
      es.close(); this.listening = false; this.emit('state');
      onFail(d.error || 'the capture was refused');
    });
    es.addEventListener('stream_end', () => {
      es.close();
      if (this.listening) { this.listening = false; this.emit('state'); }
    });
    es.onerror = () => {
      if (!this.listening) return;
      es.close(); this.listening = false; this.emit('state');
      onFail('the capture stream broke');
    };
    this.mic = es;
  },

  stopHearing() {
    try { if (this.mic) this.mic.close(); } catch {}
    this.mic = null;
    this.listening = false;
    this.emit('state');
  },

  async cancel() {
    if (!this.running) return;
    try { await API.callTool('run_cancel', {}); } catch {}
    if (this.turn) this.turn.verdict = 'cancelled';
    this.finish('cancelled');
  },

  // ---- reducing the wire into a turn --------------------------------------

  // EVERY event is kept, whether or not this build knows what to do with it.
  // The record of a run is the events; the fields below are a reading of them,
  // never a replacement for them.
  absorb(kind, d) {
    const t = this.turn;
    if (!t) return;
    // `text` is the console copy of everything else — keeping it would double
    // every line of the run.
    if (kind !== 'text') t.events.push(Object.assign({ _kind: kind }, d));

    switch (kind) {
      case 'run':
        t.pipeline = d.pipeline || '';
        t.transcript = d.transcript || '';
        break;

      case 'seat':
        t.seats.push({ seat: d.seat || 'seat', model: d.model || '',
                       timeout: d.timeout, text: '', at: Date.now() });
        break;

      case 'token': {
        // Tokens belong to the seat that is speaking, so it stays visible WHICH
        // seat produced which words.
        let s = t.seats.length ? t.seats[t.seats.length - 1] : null;
        if (d.seat) {
          for (let i = t.seats.length - 1; i >= 0; i--) {
            if (t.seats[i].seat === d.seat) { s = t.seats[i]; break; }
          }
        }
        if (s) s.text += (d.text || '');
        t.answer += (d.text || '');
        break;
      }

      case 'report':
        t.notes.push((d.text || '').trim());
        break;

      case 'tool':
        t.tools.push({ name: d.action || d.tool || d.name || '?', args: d.args, done: false });
        break;

      case 'tool_result': {
        const name = d.action || d.tool || d.name || '?';
        // `failed` is the ENGINE's own field — the pipeline's test, not a
        // reading of the words that came back.
        let hit = null;
        for (let i = t.tools.length - 1; i >= 0; i--) {
          if (t.tools[i].name === name && !t.tools[i].done) { hit = t.tools[i]; break; }
        }
        if (!hit) { hit = { name, done: false }; t.tools.push(hit); }
        hit.done = true;
        hit.failed = !!d.failed;
        hit.error = d.error || (d.failed ? String(d.text || '').slice(0, 300) : '');
        break;
      }

      case 'needs_answer':
        t.waiting = d.prompt || '';
        t.verdict = 'waiting';
        break;

      case 'delivery':
        t.delivery = d;
        // The delivery's text is the recompose's, and it is what the operator
        // is answered with — not the running token buffer above it.
        t.answer = d.text || t.answer;
        t.pipeline = d.pipeline || t.pipeline;
        t.transcript = d.transcript || t.transcript;
        t.verdict = 'delivered';
        break;

      case 'refused': case 'aborted': case 'cancelled': case 'unreachable':
        t.refusal = d.text || d.error || kind;
        t.verdict = kind;
        break;

      case 'error':
        // NOT terminal on this wire: serve.py emits it for a malformed command
        // and keeps going. It is recorded, and it does not end the turn.
        break;
    }
    this.emit('event');
  },

  // ---- the facts no surface may hide --------------------------------------

  // Read off the delivery's OWN machine-emitted field, with the failed
  // tool_results as the fallback. A page that shows an answer without showing
  // these is lying by omission (LAW 5).
  failures(t) {
    t = t || this.turn;
    if (!t) return [];
    const d = t.delivery || {};
    const out = (d.failures || []).map(f => typeof f === 'string' ? f : JSON.stringify(f));
    if (out.length) return out;
    return t.tools.filter(x => x.failed).map(x => x.name + (x.error ? ': ' + x.error : ''));
  },

  outOfTime(t) {
    t = t || this.turn;
    const d = (t && t.delivery) || {};
    return (d.out_of_time || []).map(f => typeof f === 'string' ? f : JSON.stringify(f));
  },

  steps(t) {
    t = t || this.turn;
    return ((t && t.delivery && t.delivery.steps) || []);
  },

  // What is happening RIGHT NOW, in one line. Chat shows this; the whole
  // waterfall lives on Evals.
  nowLine(t) {
    t = t || this.turn;
    if (!t) return '';
    const pend = t.tools.filter(x => !x.done);
    if (pend.length) return 'tool · ' + pend[pend.length - 1].name;
    if (t.seats.length) {
      const s = t.seats[t.seats.length - 1];
      return s.seat + (s.model ? ' · ' + s.model : '');
    }
    // No seat and no tool yet means the door has the request and the
    // engine has not begun: either a cold start, or this turn is QUEUED
    // behind another on the same world (one run at a time, by design).
    return 'waiting for the engine';
  },

  elapsed(t) {
    t = t || this.turn;
    if (!t) return '';
    const d = t.delivery || {};
    if (d.elapsed != null) return d.elapsed + 's';
    return (((t.ended || Date.now()) - t.started) / 1000).toFixed(1) + 's';
  }
};
