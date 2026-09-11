package tools

import (
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"atlas/line/internal/tenant"
)

// git reads the world's repository as it stands RIGHT NOW.
//
// Why a door tool and not the engine: "is my tree dirty" is the question he
// asks BEFORE deciding to boot anything, and a panel that needs an engine to
// tell him is a panel that cannot answer it. The engine's own `/git` stays the
// richer view; this is the glance.
//
// EVERY git CALL CLOSES ITS OWN STDIN. Learned the hard way in the core this
// morning: subprocess with no stdin hands the child the PARENT's, and in a
// headless door that is a pipe another thread is already blocked reading --
// 0.12s with no such thread, 5.02s (timeout) with one. Go's exec inherits the
// same way. os.DevNull, every call, no exceptions.
//
// REMOTE OPERATIONS ARE REPORTED, NEVER PERFORMED. The core walls push and
// pull behind MANJUEL_GIT_REMOTE (gitstate.py: "REMOTE writes cross the wall
// to somewhere the operator did not fetch it"). This reads that wall and says
// which side it is on; it does not open it, and it runs nothing that writes.
func toolGit(t tenant.Tenant, _ map[string]any) (string, error) {
	out := map[string]any{"world": t.Name}

	run := func(args ...string) (string, bool) {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, "git", args...)
		cmd.Dir = t.Home
		devnull, err := os.Open(os.DevNull)
		if err == nil {
			cmd.Stdin = devnull
			defer devnull.Close()
		}
		b, err := cmd.Output()
		if err != nil {
			return "", false
		}
		return strings.TrimSpace(string(b)), true
	}

	if _, ok := run("rev-parse", "--is-inside-work-tree"); !ok {
		out["is_repo"] = false
		out["note"] = "not a repository -- nothing to commit, and nothing to lose"
		b, _ := json.MarshalIndent(out, "", " ")
		return string(b), nil
	}
	out["is_repo"] = true

	if v, ok := run("rev-parse", "--abbrev-ref", "HEAD"); ok {
		out["branch"] = v
	}
	if v, ok := run("rev-parse", "--short", "HEAD"); ok {
		out["head"] = v
	}
	if v, ok := run("log", "-1", "--format=%s"); ok {
		out["subject"] = v
	}
	if v, ok := run("log", "-1", "--format=%cr"); ok {
		out["when"] = v
	}

	// --porcelain is git's own contract, not a rule of this estate: one line
	// per changed path, XY status in the first two columns.
	changed, untracked, files := 0, 0, []string{}
	if v, ok := run("status", "--porcelain"); ok {
		for _, line := range strings.Split(v, "\n") {
			if strings.TrimSpace(line) == "" {
				continue
			}
			if strings.HasPrefix(line, "??") {
				untracked++
			} else {
				changed++
			}
			if len(files) < 40 {
				files = append(files, line)
			}
		}
	}
	out["changed"] = changed
	out["untracked"] = untracked
	out["dirty"] = changed+untracked > 0
	out["files"] = files

	// Ahead/behind is only meaningful with an upstream, and a world without
	// one is not behind anything.
	if up, ok := run("rev-parse", "--abbrev-ref", "@{upstream}"); ok && up != "" {
		out["upstream"] = up
		if v, ok := run("rev-list", "--left-right", "--count", "HEAD..."+up); ok {
			parts := strings.Fields(v)
			if len(parts) == 2 {
				out["ahead"], _ = strconv.Atoi(parts[0])
				out["behind"], _ = strconv.Atoi(parts[1])
			}
		}
	}
	if v, ok := run("remote"); ok && v != "" {
		out["remotes"] = strings.Fields(v)
	}

	// The core's wall, read WHERE THE ENGINE READS IT. gitstate.py: REMOTE_ENV,
	// on for "1", "true", "yes", "on".
	//
	// This door is a separate process from the engine, and the flag normally
	// lives in the GROUND's .env -- which the engine loads at startup and this
	// process never sees. Reading only its own environment made the panel say
	// the wall was shut while the council could push straight through it.
	on := dial(t.Home, "GIT_REMOTE")
	out["remote_allowed"] = on
	if !on {
		out["remote_note"] = "remote git operations are OFF (MANJUEL_GIT_REMOTE unset). " +
			"push and pull refuse by name until the operator opens that wall."
	}

	b, err := json.MarshalIndent(out, "", " ")
	if err != nil {
		return "", err
	}
	return string(b), nil
}

// dial answers whether a wall is open, reading the same two places the engine
// does and in the same order. `name` is the bare dial -- "GIT_REMOTE",
// "RACK_PULL" -- and both the MANJUEL_ and the older CHAINKIT_ spelling answer.
//
// ONE READING, because two were measured disagreeing. The rack_pull wall was
// MANJUEL_RACK_PULL in ("1","true","yes","on") in the core and
// CHAINKIT_RACK_PULL == "1" in atlas: set the documented name and the core
// permitted a pull while atlas refused it. The git wall had the same shape --
// the door reported shut while the council pushed straight through.
//
// PRECEDENCE IS THE ENGINE'S, not invented here: dotenv.load skips a key that
// is already in the environment ("if key in os.environ: already"), so a shell
// variable always wins over a line in .env. The CHAINKIT_ twin is honoured the
// way manjuel/__init__.py carries it.
//
// THE WALL IS THE ESTATE'S, NOT ONE REPOSITORY'S. A carried tenant has its own
// Home but not its own .env: the flag lives once, in the ground the operator
// opened. Reading only <Home>/.env made the panel tell him two different
// stories about one ruling -- research "Sending allowed" and atlas "Sending
// OFF" side by side -- when the only difference between them was that
// Research\.env exists and Research\atlas\.env does not. He did not shut a
// wall for atlas; atlas was looking in the wrong place.
//
// ONE LEVEL UP, AND NO FURTHER. That bound is not invented here: it is the
// door's own ground law from main.go ("one level up, one level across; the
// attic is skipped"). A tenant sees its ground's .env and stops. Walking to
// the filesystem root would leave the ground, which RULE 1 forbids -- and a
// stray .env in Desktop\ must never be able to open this estate's wall.
//
// RULE 7: one key is looked up and a boolean comes back. No value is returned,
// logged, or put anywhere it could be printed.
func dial(home, name string) bool {
	for _, env := range []string{"MANJUEL_" + name, "CHAINKIT_" + name} {
		if truthy(os.Getenv(env)) {
			return true
		}
	}
	for _, dir := range []string{home, filepath.Dir(home)} {
		if envFileSays(filepath.Join(dir, ".env"), name) {
			return true
		}
	}
	return false
}

// envFileSays reads one dial out of one .env. Absent file, absent key and
// absent value all answer the same way: not open.
func envFileSays(path, name string) bool {
	b, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(b), "\n") {
		line = strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(line), "export "))
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, val, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		if key != "MANJUEL_"+name && key != "CHAINKIT_"+name {
			continue
		}
		if truthy(strings.Trim(strings.TrimSpace(val), `"'`)) {
			return true
		}
	}
	return false
}

func truthy(v string) bool {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}

// gitDiff shows WHAT CHANGED in one file, or across the tree. Read-only.
//
// The operator, 2026-09-10: an interactive repo review "kind of like the logs
// in the records section" -- Records serves one document whole and this serves
// one change whole, so a count on the panel ("3 files changed") becomes a
// thing he can actually look at before deciding anything.
//
// UNTRACKED IS NOT A DIFF, and pretending otherwise is the trap. `git diff`
// says NOTHING about a file git has never seen, so a panel that only ran diff
// would show an empty page for the one kind of file most likely to be lost.
// For those the file's own first bytes are the answer, and it says so.
//
// BOUNDED (LAW 7): one file, capped, with the cap named in the output rather
// than a silent stump. Nothing here writes, stages, or reaches a remote.
func toolGitDiff(t tenant.Tenant, args map[string]any) (string, error) {
	rel := strings.TrimSpace(str(args, "file"))

	run := func(a ...string) (string, bool) {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, "git", a...)
		cmd.Dir = t.Home
		// stdin closed, every call -- the rule this file already states.
		if devnull, err := os.Open(os.DevNull); err == nil {
			cmd.Stdin = devnull
			defer devnull.Close()
		}
		b, err := cmd.Output()
		if err != nil {
			return "", false
		}
		return string(b), true
	}

	if _, ok := run("rev-parse", "--is-inside-work-tree"); !ok {
		return "not a repository -- nothing to review", nil
	}

	const cap = 60000
	clip := func(s, what string) string {
		if len(s) <= cap {
			return s
		}
		return s[:cap] + `

... (` + what + " is " +
			strconv.Itoa(len(s)) + " bytes; this is the first " +
			strconv.Itoa(cap) + ")"
	}

	if rel == "" {
		v, _ := run("diff")
		staged, _ := run("diff", "--cached")
		if strings.TrimSpace(v+staged) == "" {
			return "Nothing has changed since the last save.", nil
		}
		return clip(staged+v, "the whole diff"), nil
	}

	// A PATH IS JAILED TO ITS OWN WORLD. Same rule the core's gate_paths
	// makes: resolve first, refuse what escapes, never judge the stated form.
	if strings.HasPrefix(rel, "/") || strings.HasPrefix(rel, "\\") || strings.Contains(rel, ":") {
		return "Refused: an absolute path is outside this world.", nil
	}
	home, err := filepath.Abs(t.Home)
	if err != nil {
		return "", err
	}
	full, err := filepath.Abs(filepath.Join(home, rel))
	if err != nil {
		return "", err
	}
	if full != home && !strings.HasPrefix(full, home+string(os.PathSeparator)) {
		return "Refused: that path resolves outside this world.", nil
	}

	if v, ok := run("diff", "--", rel); ok && strings.TrimSpace(v) != "" {
		return clip(v, "the change"), nil
	}
	if v, ok := run("diff", "--cached", "--", rel); ok && strings.TrimSpace(v) != "" {
		return clip(v, "the staged change"), nil
	}
	// Never seen by git: show the file, and say plainly that is what this is.
	b, err := os.ReadFile(full)
	if err != nil {
		return "That file has no recorded change, and could not be read: " + err.Error(), nil
	}
	return "This file is new -- git has never seen it, so there is nothing to " +
		"compare it against. Its contents:" + `

` + clip(string(b), "the file"), nil
}
