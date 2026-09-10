package tools

import (
	"fmt"
	"path/filepath"
	"strings"
	"time"

	"atlas/line/internal/engine"
	"atlas/line/internal/tenant"
)

// RunStream and AnswerStream are the streaming face of run_start and
// run_answer: the same call, through the same engine, with every event handed
// to `sink` the instant the engine speaks it.
//
// WHY A SECOND ENTRY POINT AND NOT A FLAG. A tool returns one string when it is
// finished; that is the MCP contract and it is right for a tool. A glass that
// shows the council working needs the events WHILE they happen. Rather than
// bend the tool contract, THE LINE exposes the stream beside it -- the same
// shape `ChatSendStream` already uses for chat_send. Both reach the identical
// engine call, so nothing is reimplemented and nothing can drift.
//
// NOT under askLock. That mutex is global across every tenant, and a turn can
// run for ten minutes; holding it would freeze every tool on every world for
// the length of a chat message (SPEC_CONTROL_CENTER 4.6). The engine's own
// runMu already enforces one run at a time per world, which is the real
// invariant.

// RunStream fires one objective on the world's open engine.
func RunStream(t tenant.Tenant, objective, feed, method string, sink func(engine.Event)) (engine.Result, error) {
	objective = strings.TrimSpace(objective)
	if objective == "" {
		return engine.Result{}, fmt.Errorf("a turn needs an objective")
	}
	e, ok := engines.Get(t.Home)
	if !ok {
		return engine.Result{}, fmt.Errorf(
			"no engine is open on %q -- open one first. The glass does not start "+
				"an engine on your behalf: that would open a sitting you never "+
				"opened, and the sitting line is the lock", t.Name)
	}
	return e.Run(objective, feed, method, sink)
}

// AnswerStream is the gate crossing the wire. Nothing here supplies a default:
// if the council asked, the answer is the operator's (RULE 6).
func AnswerStream(t tenant.Tenant, text string, sink func(engine.Event)) (engine.Result, error) {
	e, ok := engines.Get(t.Home)
	if !ok {
		return engine.Result{}, fmt.Errorf("no engine is open on %q", t.Name)
	}
	return e.Answer(text, sink)
}

// ListenStream captures one spoken turn through the core's voice.py. The
// text is RETURNED, never run: the operator reads it, edits it if whisper
// misheard, and sends it himself (RULE 6).
func ListenStream(t tenant.Tenant, seconds int, sink func(engine.Event)) (string, error) {
	e, ok := engines.Get(t.Home)
	if !ok {
		return "", fmt.Errorf("no engine is open on %q -- open one before speaking", t.Name)
	}
	return e.Listen(seconds, sink)
}

// EngineFacts is what the dashboard needs to show the engine and offer the
// right control: whether one is standing, what it is waiting on, and whether
// it is running code that has since changed on disk.
type EngineFacts struct {
	Open    bool   `json:"open"`
	World   string `json:"world"`
	Sitting string `json:"sitting"`
	Session string `json:"session"`
	Pending string `json:"pending"`
	Started string `json:"started,omitempty"`
	// Stale means manjuel/*.py changed after this process was spawned, so it
	// is running code the disk no longer holds. NOT set for a changed skill or
	// pipeline: those hot-reload at the next turn (CLAUDE.md), and an alarm
	// that cried over a doc edit would teach him to ignore the one row that
	// matters.
	Stale       bool   `json:"stale"`
	StaleFile   string `json:"stale_file,omitempty"`
	CodeChanged string `json:"code_changed,omitempty"`
	// Runs is how many turns this engine has finished, LastRun when the last
	// one did. Started alone cannot tell an engine at work from one standing
	// open doing nothing, and that difference is the most expensive fact in
	// the record: sittings of two runs or fewer have cost 5.3 engine-hours for
	// 91 runs, against a standup's 69 seconds per run. LastRun is empty until
	// the first turn finishes, which is exactly the case worth shouting about.
	Runs    int    `json:"runs"`
	LastRun string `json:"last_run,omitempty"`
}

// EngineOpen reports whether a world has an engine standing, and what it is
// waiting on. The glass asks this before it offers a send box, so the refusal
// is a disabled button with a reason rather than a failed turn.
func EngineOpen(t tenant.Tenant) (open bool, sitting string, pending string) {
	f := Facts(t)
	return f.Open, f.Sitting, f.Pending
}

// Facts reads the engine's own state. Nothing here is remembered between
// calls: a dashboard that cached "open" would keep saying so after a crash.
func Facts(t tenant.Tenant) EngineFacts {
	f := EngineFacts{World: t.Name}
	e, ok := engines.Get(t.Home)
	if !ok {
		return f
	}
	f.Open = true
	o := e.Opened()
	f.Sitting, f.Session = o.Str("sitting"), o.Str("session")
	if p := e.Pending(); p != nil {
		f.Pending = p.Str("prompt")
	}
	if !e.Started.IsZero() {
		f.Started = e.Started.Format(time.RFC3339)
	}
	if n, last := e.Runs(); true {
		f.Runs = n
		if !last.IsZero() {
			f.LastRun = last.Format(time.RFC3339)
		}
	}
	stale, changed, what := e.Stale()
	f.Stale = stale
	if !changed.IsZero() {
		f.CodeChanged = changed.Format(time.RFC3339)
		f.StaleFile = filepath.Base(what)
	}
	return f
}
