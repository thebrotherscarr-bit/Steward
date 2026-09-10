// Package engine is THE LINE's supervisor for Manjuel: one long-lived engine
// process per open world, spoken to over its pipes.
//
// WHY THIS EXISTS (the operator, 2026-09-09: "manjuel.py is the core, atlas is
// the control layer"). Before this package the glass could reach a MODEL --
// chat_send routes straight to rack.Ask -- but not the COUNCIL. Everything
// that makes the estate trustworthy lives in the engine: the sealed law gate
// before any model reads a word, the one Router that executes tools, the dedup
// that refuses an identical call (REFUSALS 9), the claim check, the recompose
// that puts every failure in the delivery. A control layer does not
// reimplement those; it routes THROUGH the core so they apply for free.
//
// The wire is manjuel/serve.py, PROTOCOL 1: four commands in (objective,
// answer, cancel, close) and seventeen events out. `manjuel.py --ground` sits
// that door inside a world. This is an ADAPTER, not new semantics.
//
// SIX FAULTS WERE FOUND IN REVIEW ON 2026-09-09 AND ARE FIXED HERE, each named
// at its fix site as C1..C6. Every one of them could damage sessions.jsonl,
// which is append-only and is the estate's truth.
package engine

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// Event is one line off the engine's stdout.
type Event map[string]any

func (e Event) Kind() string { s, _ := e["event"].(string); return s }

func (e Event) Str(k string) string {
	switch v := e[k].(type) {
	case string:
		return v
	case nil:
		return ""
	default:
		return fmt.Sprint(v)
	}
}

// terminal events end a turn; the engine emits exactly one of them. `error` is
// NOT here: serve.py's inbox thread emits it non-terminally for a malformed
// command, and treating it as an ending would desynchronise the wire.
var terminal = map[string]bool{
	"delivery": true, "refused": true, "aborted": true, "cancelled": true,
	"unreachable": true,
	// `command` ends a turn that ran no pipeline -- a /command, @seat, the
	// toll, a remember cue. Before it existed those turns emitted nothing
	// terminal and this pump waited for the life of the process: /warm over
	// the wire was measured at 25s with one event and no ending.
	"command": true,
}

const (
	// KeptEvents bounds what a run remembers. Tokens are counted, never kept.
	KeptEvents = 400
	// OpenTimeout covers boot: declarations, the rack check, a cold model warm.
	OpenTimeout = 300 * time.Second
	// ShutdownGrace is how long `close` gets to write `ended` and pay the toll
	// before the process is killed.
	ShutdownGrace = 60 * time.Second
)

// Engine is one Manjuel process, sitting inside one world.
type Engine struct {
	Ground string
	Name   string
	// Started is when this process was spawned. The code it runs is whatever
	// manjuel/*.py said at that instant -- Python does not reload a module
	// under a live process -- so this is what makes "the engine is older than
	// the code" answerable instead of something a human has to remember.
	Started time.Time
	// CoreCmd is the command that spawned it, kept so the door can find the
	// code this engine is actually running rather than a tree someone
	// configured separately and hoped was the same one.
	CoreCmd string

	runMu   sync.Mutex // one run at a time per world
	sendMu  sync.Mutex // C3/I3: writes to stdin serialised on their own lock
	stateMu sync.Mutex // guards pending

	cmd     *exec.Cmd
	in      io.WriteCloser
	out     *bufio.Scanner
	errBuf  *ringBuffer
	opened  Event
	pending Event
	closed  atomic.Bool
	reaped  atomic.Bool

	// WHAT THIS ENGINE HAS ACTUALLY DONE. `Started` alone cannot tell an
	// engine hard at work from one standing open doing nothing, and the
	// difference is the most expensive fact in the record: measured across
	// every sitting the core has logged, a standup gets 69 seconds of engine
	// time per run while sittings of two runs or fewer get 208 -- 63 of them,
	// 5.3 engine-hours, 91 runs between them. One held an engine sixteen
	// minutes for ZERO runs. Nothing on the wire could say so.
	//
	// Counted where every turn converges (pump), so Run and Answer both land
	// here and neither has to remember to. Atomics because /run/state is
	// served on another goroutine while a turn is mid-flight.
	runs    atomic.Int64
	lastRun atomic.Int64 // unix seconds; 0 until the first turn finishes
}

// ---------------------------------------------------------------------
// C5: the sitting line, and what "unknown" must mean
// ---------------------------------------------------------------------

// SittingOpen reads the world's own ledger. An unreadable or corrupt ledger
// reports OPEN, not closed.
//
// C5, found in review: both unknowns used to return "no open sitting", so a
// half-written last line -- exactly what a killed engine leaves -- invited a
// second engine into a world whose record was already damaged. The refusal
// exists for that case. Unknown refuses.
func SittingOpen(ground string) (n float64, started string, open bool) {
	p := filepath.Join(ground, "sessions", "sessions.jsonl")
	b, err := os.ReadFile(p)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return 0, "", false // a world with no ledger has no sitting
		}
		return 0, "unreadable ledger: " + err.Error(), true
	}
	lines := strings.Split(strings.TrimRight(string(b), "\r\n"), "\n")
	for i := len(lines) - 1; i >= 0; i-- {
		line := strings.TrimSpace(lines[i])
		if line == "" {
			continue
		}
		var row map[string]any
		if json.Unmarshal([]byte(line), &row) != nil {
			return 0, "the last ledger line is not readable JSON", true
		}
		if ended, _ := row["ended"].(string); strings.TrimSpace(ended) != "" {
			return 0, "", false
		}
		num, _ := row["n"].(float64)
		st, _ := row["started"].(string)
		return num, st, true
	}
	return 0, "", false
}

// ---------------------------------------------------------------------
// is the engine older than the code it is running
// ---------------------------------------------------------------------

// CodeRoot is the directory holding the manjuel package this engine runs,
// derived from the command that spawned it -- never guessed, never configured
// separately, so it cannot point at a different tree than the one executing.
func CodeRoot(coreCmd string) string {
	for _, f := range splitCommand(coreCmd) {
		if strings.HasSuffix(strings.ToLower(f), ".py") {
			if d := filepath.Dir(f); d != "" && d != "." {
				return d
			}
		}
	}
	return ""
}

// CodeChanged reports the newest .py under the core, and when it changed.
//
// ONLY .py IS COUNTED, and that is the whole point. CLAUDE.md's rule: agents/,
// skills/, pipelines.md and commands.md are HOT-RELOADED into a running engine
// at the next turn, so editing a skill needs no restart and must not raise an
// alarm. manjuel/*.py is NOT reloaded -- a code edit sits on disk while the old
// code keeps running -- so that, and only that, makes an engine stale.
//
// A corner it cannot read reports no change rather than a false alarm. A
// dashboard that cried "restart" over an unreadable directory would train him
// to ignore the one row that matters.
func CodeChanged(coreCmd string) (when time.Time, what string) {
	root := CodeRoot(coreCmd)
	if root == "" {
		return time.Time{}, ""
	}
	_ = filepath.WalkDir(root, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if d.IsDir() {
			switch d.Name() {
			case "__pycache__", ".git", "logs", "index", "sessions", "worlds",
				"agent_workspace", "node_modules", "tests":
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(strings.ToLower(d.Name()), ".py") {
			return nil
		}
		st, err := d.Info()
		if err != nil {
			return nil
		}
		if st.ModTime().After(when) {
			when, what = st.ModTime(), p
		}
		return nil
	})
	return when, what
}

// Stale answers the question the operator used to carry in his head across a
// day of edits: is this engine running code that has since changed on disk?
func (e *Engine) Stale() (stale bool, changed time.Time, what string) {
	changed, what = CodeChanged(e.CoreCmd)
	if changed.IsZero() || e.Started.IsZero() {
		return false, changed, what
	}
	return changed.After(e.Started), changed, what
}

// ---------------------------------------------------------------------
// opening
// ---------------------------------------------------------------------

// Open spawns the engine inside `ground`. `coreCmd` runs Manjuel, e.g.
// `python C:\...\manjuel.py`; --headless --ground are appended here so no
// caller can point the door at a world it was not given.
func Open(name, ground, coreCmd string) (*Engine, error) {
	if strings.TrimSpace(coreCmd) == "" {
		return nil, fmt.Errorf("no engine wired: atlas-mcp was started without " +
			"--manjuel and the command that runs manjuel.py, so THE LINE has no " +
			"engine to open. The glass can read the record; it cannot run a turn")
	}
	if st, err := os.Stat(ground); err != nil || !st.IsDir() {
		return nil, fmt.Errorf("refused: %q is not a directory; a world is never created here", ground)
	}
	if n, started, open := SittingOpen(ground); open {
		if n == 0 && started != "" { // the C5 unknown path
			return nil, fmt.Errorf("refused: %s -- %s. THE LINE will not open a "+
				"second engine on a world whose record it cannot read", name, started)
		}
		return nil, fmt.Errorf("refused: %s has an open sitting (%d, opened %s). "+
			"One engine per world -- a second would fork the ledger. Close it "+
			"where it is being sat in, or open a different world", name, int(n), started)
	}

	fields := splitCommand(coreCmd)
	if len(fields) == 0 {
		return nil, fmt.Errorf("refused: --manjuel is empty")
	}
	args := append(append([]string{}, fields[1:]...), "--headless", "--ground", ground)
	cmd := exec.Command(fields[0], args...)
	// The script is the token ending in .py, not blindly the last one:
	// `python x.py --verbose` used to make cmd.Dir filepath.Dir("--verbose")
	// and silently run in atlas-mcp's own working directory.
	cmd.Dir = ground
	for _, f := range fields[1:] {
		if strings.HasSuffix(strings.ToLower(f), ".py") {
			if d := filepath.Dir(f); d != "" && d != "." {
				if st, err := os.Stat(d); err == nil && st.IsDir() {
					cmd.Dir = d
				}
			}
			break
		}
	}

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	// I1: stderr used to be discarded, so a Python import error produced
	// nothing on the wire and nothing anywhere else. Keep the tail; on a
	// failed boot it is the only diagnosis there is.
	errBuf := newRing(8 << 10)
	cmd.Stderr = errBuf
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("the engine did not start: %w", err)
	}

	sc := bufio.NewScanner(stdout)
	sc.Buffer(make([]byte, 0, 1<<20), 64<<20)
	e := &Engine{Ground: ground, Name: name, cmd: cmd, in: stdin, out: sc, errBuf: errBuf,
		// The instant the process was spawned, and the command that spawned
		// it: together they answer whether this engine is older than the code
		// it is running, which used to be a thing the operator had to hold in
		// his head across a day of edits.
		Started: time.Now(), CoreCmd: coreCmd}

	done := make(chan Event, 1)
	go func() {
		for e.out.Scan() {
			var ev Event
			if json.Unmarshal(e.out.Bytes(), &ev) != nil {
				continue
			}
			switch ev.Kind() {
			case "opened", "closed", "error":
				done <- ev
				return
			}
		}
		done <- nil
	}()

	select {
	case ev := <-done:
		if ev == nil || ev.Kind() != "opened" {
			why := "the engine closed before it opened"
			if ev != nil && ev.Str("text") != "" {
				why = ev.Str("text")
			}
			e.shutdown() // C6: never Kill without Wait
			return nil, fmt.Errorf("the engine did not open: %s%s", why, e.stderrTail())
		}
		e.opened = ev
	case <-time.After(OpenTimeout):
		// C1: THE WORLD-BRICKING PATH. serve.py writes its sitting line BEFORE
		// it emits `opened`, so killing here left a line with no `ended`, and
		// every later env_open refused that world forever -- repairable only by
		// hand-editing an append-only ledger, which LAW 8 forbids. A boot that
		// overran is now CLOSED, not killed: the toll is paid and `ended` is
		// written, exactly as on exit, and the world stays openable.
		e.shutdown()
		return nil, fmt.Errorf("the engine did not open inside %ds; it was closed "+
			"cleanly so its world stays openable%s",
			int(OpenTimeout.Seconds()), e.stderrTail())
	}
	return e, nil
}

// tick records that a turn finished. Both terminal paths in pump call it, so
// no caller has to remember.
func (e *Engine) tick() {
	e.runs.Add(1)
	e.lastRun.Store(time.Now().Unix())
}

// Runs is how many turns this engine has finished, and when the last one did.
// A zero time means none has.
func (e *Engine) Runs() (int, time.Time) {
	n := int(e.runs.Load())
	if sec := e.lastRun.Load(); sec > 0 {
		return n, time.Unix(sec, 0)
	}
	return n, time.Time{}
}

func (e *Engine) Opened() Event { return e.opened }

// Pending is the needs_answer a run stopped on, or nil.
func (e *Engine) Pending() Event {
	e.stateMu.Lock()
	defer e.stateMu.Unlock()
	return e.pending
}

func (e *Engine) setPending(ev Event) {
	e.stateMu.Lock()
	e.pending = ev
	e.stateMu.Unlock()
}

// send serialises every write to the child's stdin. Run, Answer, Cancel and
// Close all reach it from different goroutines; I3 was a genuine data race on
// both the pipe and the closed flag.
func (e *Engine) send(row map[string]any) error {
	if e.closed.Load() {
		return fmt.Errorf("this engine is closed")
	}
	b, err := json.Marshal(row)
	if err != nil {
		return err
	}
	e.sendMu.Lock()
	defer e.sendMu.Unlock()
	_, err = e.in.Write(append(b, '\n'))
	return err
}

func (e *Engine) stderrTail() string {
	if t := e.errBuf.String(); t != "" {
		return "\n-- the engine's own stderr --\n" + t
	}
	return ""
}

// ---------------------------------------------------------------------
// running
// ---------------------------------------------------------------------

// Result is what one turn produced, read off the engine's OWN events.
type Result struct {
	Final   Event
	Events  []Event
	Tokens  int
	Dropped int // I6: events past KeptEvents, counted rather than silently lost
	Waiting bool
}

// pump reads the turn. `sink`, if given, receives EVERY event the instant
// it is read -- tokens, seat wakes, tool calls, tool results, guard
// verdicts, notes -- so a glass can show the council working rather than a
// spinner and then an answer. It is deliberately NOT bounded by KeptEvents:
// that bound is on what a run REMEMBERS (Result.Events), and a stream that
// silently stopped at event 400 would be a lie about what ran.
//
// A sink that panics or blocks is the caller's problem, not the wire's: it
// runs on the pump goroutine, so a slow consumer slows the read. Every sink
// in this build writes to an already-flushed SSE socket or a channel.
func (e *Engine) pump(sink func(Event)) (Result, error) {
	var r Result
	for e.out.Scan() {
		var ev Event
		if json.Unmarshal(e.out.Bytes(), &ev) != nil {
			continue
		}
		if sink != nil {
			sink(ev)
		}
		switch ev.Kind() {
		case "token":
			r.Tokens++
			continue
		case "text":
			continue
		}
		if len(r.Events) < KeptEvents {
			r.Events = append(r.Events, ev)
		} else {
			r.Dropped++
		}
		if ev.Kind() == "needs_answer" {
			r.Final, r.Waiting = ev, true
			e.setPending(ev)
			return r, nil
		}
		if terminal[ev.Kind()] {
			r.Final = ev
			e.setPending(nil)
			return r, nil
		}
	}
	e.setPending(nil)
	if err := e.out.Err(); err != nil {
		return r, fmt.Errorf("the engine's pipe broke: %w%s", err, e.stderrTail())
	}
	return r, fmt.Errorf("the engine stopped speaking without finishing the turn%s", e.stderrTail())
}

// Run sends one objective and reads until the turn ends or the engine asks a
// question. One run at a time per world.
func (e *Engine) Run(objective, feed, method string, sink func(Event)) (Result, error) {
	e.runMu.Lock()
	defer e.runMu.Unlock()
	if e.closed.Load() {
		return Result{}, fmt.Errorf("this engine is closed")
	}
	if p := e.Pending(); p != nil {
		return Result{}, fmt.Errorf("refused: the engine is waiting on an answer "+
			"(%q). Answer it with run_answer before starting another turn -- the "+
			"gate is yours, not the door's", p.Str("prompt"))
	}
	row := map[string]any{"cmd": "objective", "text": objective}
	if feed != "" {
		row["feed"] = feed
	}
	if method != "" {
		row["method"] = method
	}
	if err := e.send(row); err != nil {
		return Result{}, err
	}
	res, err := e.pump(sink)
	// A SLASH COMMAND IS THE DOOR'S OWN HOUSEKEEPING, NOT WORK. Booting runs
	// `/warm` and `/status` through this same path, so counting them meant a
	// freshly opened engine reported "2 runs" before anyone had asked it
	// anything -- and "0 runs", the state most worth shouting about, became
	// unreachable. Counted after pump rather than inside it, because pump
	// cannot see the objective and only the caller knows what it was.
	if err == nil && !strings.HasPrefix(strings.TrimSpace(objective), "/") {
		e.tick()
	}
	return res, err
}

// Answer resumes a run stopped at a needs_answer. This is the operator's hand
// crossing the wire; nothing here supplies a default.
func (e *Engine) Answer(text string, sink func(Event)) (Result, error) {
	e.runMu.Lock()
	defer e.runMu.Unlock()
	if e.Pending() == nil {
		return Result{}, fmt.Errorf("refused: nothing is being asked, so there is nothing to answer")
	}
	if err := e.send(map[string]any{"cmd": "answer", "text": text}); err != nil {
		return Result{}, err
	}
	e.setPending(nil)
	// An answer is always his hand crossing the wire; it is never housekeeping.
	res, err := e.pump(sink)
	if err == nil {
		e.tick()
	}
	return res, err
}

// Listen captures one spoken turn through the core's own voice.py -- the
// compiled whisper.cpp, the room calibration, the estate vocabulary bias, and
// the same call the REPL's /chat makes. Nothing about hearing is implemented
// on this side of the wire.
//
// IT DOES NOT RUN WHAT IT HEARD. The text is returned for the operator to read,
// edit and send himself. A microphone that fired objectives at the council on
// its own would be a gate nobody holds (RULE 6), and a misheard word would run
// before he ever saw it.
//
// runMu is held for the capture: one microphone, one input device, and a
// capture racing a run would interleave two conversations in one ledger.
func (e *Engine) Listen(seconds int, sink func(Event)) (string, error) {
	e.runMu.Lock()
	defer e.runMu.Unlock()
	if e.closed.Load() {
		return "", fmt.Errorf("this engine is closed")
	}
	if p := e.Pending(); p != nil {
		return "", fmt.Errorf("refused: the engine is waiting on an answer (%q); "+
			"answer it before speaking a new one", p.Str("prompt"))
	}
	row := map[string]any{"cmd": "listen"}
	if seconds > 0 {
		row["seconds"] = seconds
	}
	if err := e.send(row); err != nil {
		return "", err
	}
	// A capture ends in `heard` or `error` and in nothing else. It is not a
	// turn: no delivery is coming, so pump()'s terminal set would wait forever.
	for e.out.Scan() {
		var ev Event
		if json.Unmarshal(e.out.Bytes(), &ev) != nil {
			continue
		}
		if sink != nil {
			sink(ev)
		}
		switch ev.Kind() {
		case "heard":
			return ev.Str("text"), nil
		case "error":
			return "", fmt.Errorf("%s", ev.Str("text"))
		}
	}
	if err := e.out.Err(); err != nil {
		return "", fmt.Errorf("the engine's pipe broke: %w%s", err, e.stderrTail())
	}
	return "", fmt.Errorf("the engine stopped speaking mid-capture%s", e.stderrTail())
}

// Cancel is Ctrl-C. It must NOT take runMu -- the whole point is to reach a
// turn that is holding it.
//
// C4: cancelling AT a question used to leave `pending` set with nobody
// pumping, so run_start refused forever and the next run_answer returned the
// stale `cancelled` as though it were that turn's result -- a false statement
// about what ran. The pending question is now cleared and its abandoned
// terminal event drained, so the wire comes back in step.
func (e *Engine) Cancel() error {
	if e.closed.Load() {
		return fmt.Errorf("this engine is closed")
	}
	wasWaiting := e.Pending() != nil
	if err := e.send(map[string]any{"cmd": "cancel"}); err != nil {
		return err
	}
	if wasWaiting {
		e.setPending(nil)
		go func() {
			e.runMu.Lock()
			defer e.runMu.Unlock()
			_, _ = e.pump(nil) // drain the `cancelled` nobody is waiting for
		}()
	}
	return nil
}

// ---------------------------------------------------------------------
// closing
// ---------------------------------------------------------------------

// shutdown asks the engine to close, waits for the process, and kills only if
// it will not go. C6: Kill is always followed by Wait and the pipe is always
// closed, or the process handle and both descriptors leak for the life of
// atlas-mcp -- and env_open is client-callable with no rate limit.
func (e *Engine) shutdown() (tollPaid bool) {
	if !e.reaped.CompareAndSwap(false, true) {
		return false
	}
	e.closed.Store(true)
	e.sendMu.Lock()
	if b, err := json.Marshal(map[string]any{"cmd": "close"}); err == nil {
		_, _ = e.in.Write(append(b, '\n'))
	}
	e.sendMu.Unlock()

	done := make(chan struct{})
	go func() { _, _ = e.cmd.Process.Wait(); close(done) }()
	select {
	case <-done:
		tollPaid = true
	case <-time.After(ShutdownGrace):
		_ = e.cmd.Process.Kill()
		<-done
	}
	_ = e.in.Close()
	return tollPaid
}

// Close ends the sitting properly, then reaps. It reports whether the engine
// went quietly -- env_close must not claim a toll it cannot know was paid
// (I4).
//
// C3: Close used to take the same mutex Run holds for a whole turn, so
// shutdown blocked behind a 300-second court, CloseAll hung, and because
// signal.Notify was already installed the second Ctrl-C did nothing -- the
// operator's only exit was a hard kill that orphaned the engine with its
// sitting open. Close takes no run lock: it cancels first, then closes.
func (e *Engine) Close() (tollPaid bool, err error) {
	if e.reaped.Load() {
		return false, nil
	}
	if e.Pending() != nil || !e.runMu.TryLock() {
		_ = e.send(map[string]any{"cmd": "cancel"}) // free a turn in flight
	} else {
		e.runMu.Unlock()
	}
	return e.shutdown(), nil
}

// Alive reports whether the child is still running.
//
// I5: a dead engine used to stay in the registry and be handed back as
// "already open: idempotent", while env_list printed its stale sitting number
// as live and run_start advised "env_open first" -- the one thing that could
// not help.
func (e *Engine) Alive() bool {
	if e.closed.Load() || e.reaped.Load() {
		return false
	}
	return e.cmd.ProcessState == nil
}

// ---------------------------------------------------------------------
// the registry: one engine per world, and no orphans
// ---------------------------------------------------------------------

type Registry struct {
	mu   sync.Mutex
	open map[string]*Engine
}

func NewRegistry() *Registry { return &Registry{open: map[string]*Engine{}} }

func (r *Registry) Get(ground string) (*Engine, bool) {
	r.mu.Lock()
	defer r.mu.Unlock()
	e, ok := r.open[ground]
	if ok && !e.Alive() { // I5: never hand back a corpse
		delete(r.open, ground)
		return nil, false
	}
	return e, ok
}

// Open holds the registry lock across the spawn.
//
// C2: it used to release the lock while the child booted, so two concurrent
// env_open calls both found the map empty, both passed the sitting check
// (neither child had written its line yet) and both started. seatlog's
// numbering is read-then-append, so both wrote the SAME sitting number into
// one append-only ledger. Serialising opens costs a queued caller a few
// seconds; the alternative is a forked record.
func (r *Registry) Open(name, ground, coreCmd string) (*Engine, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if e, ok := r.open[ground]; ok {
		if e.Alive() {
			return e, nil
		}
		delete(r.open, ground)
	}
	e, err := Open(name, ground, coreCmd)
	if err != nil {
		return nil, err
	}
	r.open[ground] = e
	return e, nil
}

func (r *Registry) CloseOne(ground string) (bool, error) {
	r.mu.Lock()
	e, ok := r.open[ground]
	delete(r.open, ground)
	r.mu.Unlock() // I2: never close while holding the registry lock
	if !ok {
		return false, fmt.Errorf("no engine is open on that world")
	}
	return e.Close()
}

// CloseAll reaps every engine, in parallel. An orphan holds its world's
// sitting open, and an open sitting is what RULE 9 forbids editing under and
// what the release gate refuses a tag over.
func (r *Registry) CloseAll() {
	r.mu.Lock()
	all := make([]*Engine, 0, len(r.open))
	for g, e := range r.open {
		all = append(all, e)
		delete(r.open, g)
	}
	r.mu.Unlock()
	var wg sync.WaitGroup
	for _, e := range all {
		wg.Add(1)
		go func(e *Engine) { defer wg.Done(); _, _ = e.Close() }(e)
	}
	wg.Wait()
}

func (r *Registry) List() []*Engine {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make([]*Engine, 0, len(r.open))
	for _, e := range r.open {
		out = append(out, e)
	}
	return out
}

// ---------------------------------------------------------------------
// small parts
// ---------------------------------------------------------------------

// ringBuffer keeps the last n bytes of the child's stderr.
type ringBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
	max int
}

func newRing(max int) *ringBuffer { return &ringBuffer{max: max} }

func (r *ringBuffer) Write(p []byte) (int, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.buf.Write(p)
	if r.buf.Len() > r.max {
		b := r.buf.Bytes()
		keep := append([]byte{}, b[r.buf.Len()-r.max:]...)
		r.buf.Reset()
		r.buf.Write(keep)
	}
	return len(p), nil
}

func (r *ringBuffer) String() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return strings.TrimSpace(r.buf.String())
}

// splitCommand honours quotes so a path with spaces survives.
func splitCommand(s string) []string {
	var out []string
	var cur []rune
	inQuote := false
	var q rune
	for _, c := range s {
		switch {
		case inQuote:
			if c == q {
				inQuote = false
			} else {
				cur = append(cur, c)
			}
		case c == '"' || c == '\'':
			inQuote, q = true, c
		case c == ' ' || c == '\t':
			if len(cur) > 0 {
				out = append(out, string(cur))
				cur = nil
			}
		default:
			cur = append(cur, c)
		}
	}
	if len(cur) > 0 {
		out = append(out, string(cur))
	}
	return out
}
