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
// RULE 7: one key is looked up and a boolean comes back. No value is returned,
// logged, or put anywhere it could be printed.
func dial(home, name string) bool {
	for _, name := range []string{"MANJUEL_" + name, "CHAINKIT_" + name} {
		if truthy(os.Getenv(name)) {
			return true
		}
	}
	b, err := os.ReadFile(filepath.Join(home, ".env"))
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
