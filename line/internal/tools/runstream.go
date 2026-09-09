package tools

import (
	"fmt"
	"strings"

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

// EngineOpen reports whether a world has an engine standing, and what it is
// waiting on. The glass asks this before it offers a send box, so the refusal
// is a disabled button with a reason rather than a failed turn.
func EngineOpen(t tenant.Tenant) (open bool, sitting string, pending string) {
	e, ok := engines.Get(t.Home)
	if !ok {
		return false, "", ""
	}
	if p := e.Pending(); p != nil {
		pending = p.Str("prompt")
	}
	return true, e.Opened().Str("sitting"), pending
}
