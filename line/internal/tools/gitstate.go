package tools

import (
	"context"
	"encoding/json"
	"os"
	"os/exec"
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

	// The core's wall, read and reported. gitstate.py: REMOTE_ENV, on for
	// "1", "true", "yes", "on".
	env := strings.TrimSpace(os.Getenv("MANJUEL_GIT_REMOTE"))
	on := env == "1" || env == "true" || env == "yes" || env == "on"
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
