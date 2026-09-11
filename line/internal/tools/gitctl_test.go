// The first strokes this package has ever had.
//
// internal/tools carries every MCP tool handler in THE LINE and carried zero
// provers until 2026-09-10 -- named as the estate's biggest hole in
// tests/PROVING.md the same day, and then immediately made bigger by the git
// verbs. These cover the verbs that CHANGE a repository and the dial that
// decides whether any of them may reach a remote.
//
// HERMETIC BY LAW 5: every stroke builds its own repository in t.TempDir()
// and nothing here touches the estate's record. No test in this file reaches
// a network; the two that concern sending prove the REFUSAL, which is the
// only half that can be proven without one.
package tools

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"atlas/line/internal/tenant"
)

// --- ground ----------------------------------------------------------------

// tempWorld builds a real repository with one save in it and hands back a
// tenant standing on it.
func tempWorld(t *testing.T) tenant.Tenant {
	t.Helper()
	home := t.TempDir()
	tn := tenant.Tenant{Name: "probe", Home: home, Manifest: tenant.DefaultManifest()}
	git := func(args ...string) {
		t.Helper()
		cmd := exec.Command("git", args...)
		cmd.Dir = home
		cmd.Env = append(os.Environ(), "GIT_TERMINAL_PROMPT=0")
		if out, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("git %s: %v\n%s", strings.Join(args, " "), err, out)
		}
	}
	git("init", "-b", "main")
	git("config", "user.name", "prove")
	git("config", "user.email", "prove@localhost")
	write(t, home, "first.txt", "the ground is here\n")
	git("add", "-A")
	git("commit", "-m", "the first save")
	return tn
}

func write(t *testing.T, home, rel, body string) {
	t.Helper()
	p := filepath.Join(home, rel)
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

// call runs a tool and fails the stroke on a hard error (a refusal is a
// STRING, not an error -- that distinction is the estate's whole style).
func call(t *testing.T, fn func(tenant.Tenant, map[string]any) (string, error),
	tn tenant.Tenant, args map[string]any) string {
	t.Helper()
	out, err := fn(tn, args)
	if err != nil {
		t.Fatalf("tool errored instead of refusing: %v", err)
	}
	return out
}

func mustContain(t *testing.T, got, want, why string) {
	t.Helper()
	if !strings.Contains(got, want) {
		t.Fatalf("%s\n  wanted %q in:\n%s", why, want, got)
	}
}

func mustNotContain(t *testing.T, got, want, why string) {
	t.Helper()
	if strings.Contains(got, want) {
		t.Fatalf("%s\n  did NOT want %q in:\n%s", why, want, got)
	}
}

// --- the dial: the bug this file was born from ------------------------------

// The panel told the operator two different stories about one ruling --
// research "Sending allowed", atlas "Sending OFF" -- because dial read only
// <Home>/.env and a carried tenant has no .env of its own.
func TestDialReadsTheGroundOneLevelUp(t *testing.T) {
	ground := t.TempDir()
	world := filepath.Join(ground, "carried")
	if err := os.MkdirAll(world, 0o755); err != nil {
		t.Fatal(err)
	}
	if dial(world, "GIT_REMOTE") {
		t.Fatal("a wall with no .env anywhere reported OPEN")
	}
	write(t, ground, ".env", "# the estate's dials\nMANJUEL_GIT_REMOTE=1\n")
	if !dial(world, "GIT_REMOTE") {
		t.Fatal("the ground's .env was not seen from a carried world -- the exact bug")
	}
}

// ONE LEVEL UP, AND NO FURTHER. Walking to the filesystem root would leave
// the ground (RULE 1), and a stray .env two levels out must never open this
// estate's wall.
func TestDialStopsAtOneLevel(t *testing.T) {
	outside := t.TempDir()
	ground := filepath.Join(outside, "ground")
	world := filepath.Join(ground, "carried")
	if err := os.MkdirAll(world, 0o755); err != nil {
		t.Fatal(err)
	}
	write(t, outside, ".env", "MANJUEL_GIT_REMOTE=1\n")
	if dial(world, "GIT_REMOTE") {
		t.Fatal("a .env TWO levels up opened the wall -- the bound is gone")
	}
}

func TestDialHonoursTheOlderSpellingAndRefusesJunk(t *testing.T) {
	home := t.TempDir()
	write(t, home, ".env", "CHAINKIT_GIT_REMOTE=yes\n")
	if !dial(home, "GIT_REMOTE") {
		t.Fatal("the CHAINKIT_ twin was not honoured")
	}
	other := t.TempDir()
	write(t, other, ".env", "MANJUEL_GIT_REMOTE=0\n#MANJUEL_GIT_REMOTE=1\n")
	if dial(other, "GIT_REMOTE") {
		t.Fatal("a shut dial (and a commented one) reported OPEN")
	}
}

// --- naming and jailing -----------------------------------------------------

func TestBranchNamesThatWouldBecomeFlagsAreRefused(t *testing.T) {
	for _, bad := range []string{"", "-rf", "two words", "a..b", "a~1", "a^", "a:b",
		"a?", "a*", "a[b", "a\\b", "a@{0}", "a/", "a.lock"} {
		if badBranchName(bad) == "" {
			t.Fatalf("%q was admitted as a branch name", bad)
		}
	}
	for _, ok := range []string{"main", "fix/the-door", "v0.1.2", "a_b-c.d"} {
		if r := badBranchName(ok); r != "" {
			t.Fatalf("%q was refused: %s", ok, r)
		}
	}
}

func TestAPathIsJailedToItsOwnWorld(t *testing.T) {
	tn := tenant.Tenant{Name: "probe", Home: t.TempDir()}
	for _, bad := range []string{"/etc/passwd", "\\\\server\\share", "C:\\keys.txt",
		"../outside.txt", "sub/../../outside.txt"} {
		if jailed(tn, bad) == "" {
			t.Fatalf("%q escaped the world", bad)
		}
	}
	for _, ok := range []string{"a.txt", "sub/b.txt", "sub/../a.txt"} {
		if r := jailed(tn, ok); r != "" {
			t.Fatalf("%q was refused: %s", ok, r)
		}
	}
}

// RULE 7-adjacent: a remote URL can carry a token in its userinfo, so only
// the host is ever lifted out of one.
func TestHostOfNeverCarriesCredentials(t *testing.T) {
	cases := map[string]string{
		"https://github.com/owner/repo.git":                    "github.com",
		"https://x-access-token:ghp_SECRET@github.com/o/r.git": "github.com",
		"git@github.com:owner/repo.git":                        "github.com",
		"ssh://git@example.org:22/o/r.git":                     "example.org",
	}
	for url, want := range cases {
		got := hostOf(url)
		if got != want {
			t.Fatalf("hostOf(%q) = %q, want %q", url, got, want)
		}
		if strings.Contains(got, "SECRET") || strings.Contains(got, "ghp_") {
			t.Fatalf("hostOf leaked a credential: %q", got)
		}
	}
}

// --- saving -----------------------------------------------------------------

func TestASaveWithoutAMessageIsRefusedAndStagesNothing(t *testing.T) {
	tn := tempWorld(t)
	write(t, tn.Home, "new.txt", "unsaved\n")
	out := call(t, toolGitCommit, tn, map[string]any{"message": "   "})
	mustContain(t, out, "Refused", "an empty message must be refused")
	mustContain(t, out, "Nothing was staged", "the refusal must say nothing was staged")

	staged, _ := gitRun(tn, 10e9, "diff", "--cached", "--name-only")
	if strings.TrimSpace(staged) != "" {
		t.Fatalf("the refused save staged something anyway: %q", staged)
	}
}

func TestACleanTreeSavesNothing(t *testing.T) {
	tn := tempWorld(t)
	out := call(t, toolGitCommit, tn, map[string]any{"message": "nothing changed"})
	mustContain(t, out, "Nothing to save", "a clean tree must say so plainly")
}

func TestASaveLandsAndNamesWhatItSaved(t *testing.T) {
	tn := tempWorld(t)
	write(t, tn.Home, "second.txt", "more\n")
	write(t, tn.Home, "third.txt", "and more\n")
	out := call(t, toolGitCommit, tn, map[string]any{"message": "two more files"})
	mustContain(t, out, "Saved 2 files", "the save must count what it saved")
	mustContain(t, out, "two more files", "the save must echo the message")

	subj, _ := gitRun(tn, 10e9, "log", "-1", "--format=%s")
	if strings.TrimSpace(subj) != "two more files" {
		t.Fatalf("the message did not reach the record: %q", subj)
	}
}

func TestNamedFilesNarrowTheSaveAndAnEscapingPathRefusesIt(t *testing.T) {
	tn := tempWorld(t)
	write(t, tn.Home, "wanted.txt", "a\n")
	write(t, tn.Home, "left.txt", "b\n")
	out := call(t, toolGitCommit, tn, map[string]any{
		"message": "only the one", "files": "wanted.txt"})
	mustContain(t, out, "Saved 1 file", "naming one file must save exactly one")

	if !dirty(tn) {
		t.Fatal("the unnamed file was swept in anyway")
	}
	out = call(t, toolGitCommit, tn, map[string]any{
		"message": "escape", "files": "../outside.txt"})
	mustContain(t, out, "outside this world", "an escaping path must refuse the save")
}

// --- the wall ---------------------------------------------------------------

// Sending and fetching REFUSE BY NAME while the dial is shut. Neither test
// reaches a network: that is the point -- a shut wall is proven by the fact
// that nothing was attempted.
func TestSendingAndFetchingRefuseByNameWhileTheWallIsShut(t *testing.T) {
	tn := tempWorld(t)
	t.Setenv("MANJUEL_GIT_REMOTE", "")
	t.Setenv("CHAINKIT_GIT_REMOTE", "")

	push := call(t, toolGitPush, tn, nil)
	mustContain(t, push, "Refused", "a shut wall must refuse the send")
	mustContain(t, push, "MANJUEL_GIT_REMOTE", "the refusal must name the dial")
	mustContain(t, push, "operator's alone", "the refusal must say whose the dial is")

	pull := call(t, toolGitPull, tn, nil)
	mustContain(t, pull, "Refused", "a shut wall must refuse the fetch")
	mustContain(t, pull, "MANJUEL_GIT_REMOTE", "the refusal must name the dial")
}

// With the wall OPEN, a fetch over unsaved work still refuses -- the wall is
// not the only guard, and this is the one that keeps work from going missing.
func TestFetchingRefusesOverUnsavedWorkEvenWithTheWallOpen(t *testing.T) {
	tn := tempWorld(t)
	t.Setenv("MANJUEL_GIT_REMOTE", "1")
	write(t, tn.Home, "unsaved.txt", "work in hand\n")
	out := call(t, toolGitPull, tn, nil)
	mustContain(t, out, "unsaved work", "a dirty tree must refuse the fetch")
	mustNotContain(t, out, "MANJUEL_GIT_REMOTE", "this refusal is not the wall's")
}

// --- lines of work -----------------------------------------------------------

func TestTheBranchListNamesWhereYouStandAndWhichIsTheMainLine(t *testing.T) {
	tn := tempWorld(t)
	out := call(t, toolGitBranch, tn, map[string]any{"action": "list"})
	mustContain(t, out, `"on": "main"`, "the list must say which line you are on")
	mustContain(t, out, `"main": true`, "the list must mark the main line")
	mustContain(t, out, `"sent": false`, "a line never pushed must not claim it was")
}

func TestALineOpensSwitchesAndCloses(t *testing.T) {
	tn := tempWorld(t)
	out := call(t, toolGitBranch, tn, map[string]any{"action": "new", "name": "fix/the-door"})
	mustContain(t, out, "Opened", "opening a line must say so")
	if b, _ := currentBranch(tn); b != "fix/the-door" {
		t.Fatalf("opening a line did not move onto it: %q", b)
	}

	out = call(t, toolGitBranch, tn, map[string]any{"action": "switch", "name": "main"})
	mustContain(t, out, "You are now on", "switching must say where you are")

	out = call(t, toolGitBranch, tn, map[string]any{"action": "close", "name": "fix/the-door"})
	mustContain(t, out, "Closed", "an empty line must close cleanly")
}

func TestYouCannotCloseTheLineYouAreStandingOn(t *testing.T) {
	tn := tempWorld(t)
	out := call(t, toolGitBranch, tn, map[string]any{"action": "close", "name": "main"})
	mustContain(t, out, "standing on that line", "closing your own line must refuse")
}

// UNMERGED WORK IS NOT DISCARDED ON A GUESS. -d refuses; that refusal is
// reported, never escalated to -D behind the operator's back.
func TestClosingALineHoldingWorkRefusesAndSaysHowToMeanIt(t *testing.T) {
	tn := tempWorld(t)
	call(t, toolGitBranch, tn, map[string]any{"action": "new", "name": "spur"})
	write(t, tn.Home, "only-here.txt", "work that exists nowhere else\n")
	call(t, toolGitCommit, tn, map[string]any{"message": "work on the spur"})
	call(t, toolGitBranch, tn, map[string]any{"action": "switch", "name": "main"})

	out := call(t, toolGitBranch, tn, map[string]any{"action": "close", "name": "spur"})
	mustContain(t, out, "not on any other", "the refusal must say the work is unique")
	mustContain(t, out, "git branch -D spur", "the refusal must name how to mean it")

	if _, err := gitRun(tn, 10e9, "rev-parse", "--verify", "spur"); err != nil {
		t.Fatal("the line was deleted despite the refusal")
	}
}

func TestSwitchingRefusesOverUnsavedWork(t *testing.T) {
	tn := tempWorld(t)
	call(t, toolGitBranch, tn, map[string]any{"action": "new", "name": "other"})
	call(t, toolGitBranch, tn, map[string]any{"action": "switch", "name": "main"})
	write(t, tn.Home, "in-hand.txt", "unsaved\n")
	out := call(t, toolGitBranch, tn, map[string]any{"action": "switch", "name": "other"})
	mustContain(t, out, "unsaved work", "switching over a dirty tree must refuse")
	if b, _ := currentBranch(tn); b != "main" {
		t.Fatalf("the refused switch moved anyway: %q", b)
	}
}

func TestAnUnknownBranchActionIsRefusedByName(t *testing.T) {
	tn := tempWorld(t)
	out := call(t, toolGitBranch, tn, map[string]any{"action": "rebase", "name": "main"})
	mustContain(t, out, `"rebase" is not something this does`, "an unknown verb must be named")
}

// --- absence ----------------------------------------------------------------

// A world that is not a repository is denied honestly by every verb, and
// nothing is created to make the answer nicer.
func TestNotARepositoryIsDeniedByEveryVerb(t *testing.T) {
	tn := tenant.Tenant{Name: "bare", Home: t.TempDir(), Manifest: tenant.DefaultManifest()}
	t.Setenv("MANJUEL_GIT_REMOTE", "1")
	for name, fn := range map[string]func(tenant.Tenant, map[string]any) (string, error){
		"git_commit": toolGitCommit,
		"git_push":   toolGitPush,
		"git_pull":   toolGitPull,
		"git_branch": toolGitBranch,
		"git_remote": toolGitRemote,
	} {
		out := call(t, fn, tn, map[string]any{"message": "m", "name": "b"})
		if !strings.Contains(out, "not a repository") {
			t.Fatalf("%s did not deny a bare directory honestly: %s", name, out)
		}
	}
	if _, err := os.Stat(filepath.Join(tn.Home, ".git")); err == nil {
		t.Fatal("a verb created a repository to answer with")
	}
}
