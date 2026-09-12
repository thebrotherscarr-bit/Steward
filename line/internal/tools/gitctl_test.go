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
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

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

// --- the marks a version is cut at ------------------------------------------
//
// A tag is the one artifact a stranger takes on faith, and unlike a branch it
// is not expected to move under him. Every stroke here proves one refusal that
// keeps that true, and each proves it BOTH WAYS -- a guard shown only on what
// it refuses might be refusing everything.

// versionWorld builds a repository that DECLARES a version, which is the only
// kind of world this verb will mark.
func versionWorld(t *testing.T, declared string) tenant.Tenant {
	t.Helper()
	tn := tempWorld(t)
	saveVersion(t, tn, declared)
	return tn
}

func saveVersion(t *testing.T, tn tenant.Tenant, declared string) {
	t.Helper()
	write(t, tn.Home, "VERSION", declared+"\n")
	if out, err := gitRun(tn, 30*time.Second, "add", "-A"); err != nil {
		t.Fatalf("add: %v\n%s", err, out)
	}
	if out, err := gitRun(tn, 30*time.Second, "commit", "-m", "the version, declared"); err != nil {
		t.Fatalf("commit: %v\n%s", err, out)
	}
}

func headOf(t *testing.T, tn tenant.Tenant) string {
	t.Helper()
	out, err := gitRun(tn, 10*time.Second, "rev-parse", "--verify", "HEAD^{commit}")
	if err != nil {
		t.Fatalf("rev-parse: %v\n%s", err, out)
	}
	return strings.TrimSpace(out)
}

// THE MONIKER FAULT, 2026-09-12. release.ps1 would have turned a plain 0.1.5
// into `v0.1.5+f1`. Anything that is not vMAJOR.MINOR.PATCH dies before the
// mark exists -- and the lawful name still lands, which is the other half.
func TestAVersionMarkMustBePlainSemver(t *testing.T) {
	tn := versionWorld(t, "0.1.5")
	for name, want := range map[string]string{
		"v0.1.5+f1":  "is not a number",
		"v0.1.5-rc1": "is not a number",
		"v0.1.5f":    "is not a number",
		"0.1.5":      "does not begin with 'v'",
		"v0.1":       "three numbers and two dots",
		"v0.1.5.2":   "three numbers and two dots",
		"":           "name the mark",
	} {
		out := call(t, toolGitTag, tn, map[string]any{
			"action": "cut", "name": name, "message": "the coding update"})
		mustContain(t, out, want, "a mark named "+name+" must be refused by name")
		mustNotContain(t, out, "Cut ", "nothing may be cut on a refusal")
	}
	// AND THE LAWFUL ONE LANDS.
	out := call(t, toolGitTag, tn, map[string]any{
		"action": "cut", "name": "v0.1.5", "message": "the flow confirmation"})
	mustContain(t, out, "Cut v0.1.5", "a lawful mark on an agreeing ground must land")
}

// The name, the file, and semver must all agree -- the same arithmetic
// release.yml runs on arrival, done here before the mark can be sent.
func TestAMarkMustEqualWhatTheGroundDeclaresAtThatCommit(t *testing.T) {
	tn := versionWorld(t, "0.1.5")
	out := call(t, toolGitTag, tn, map[string]any{
		"action": "cut", "name": "v0.2.0", "message": "a number nobody bumped"})
	mustContain(t, out, "the mark and the ground disagree", "a mismatch must be refused")
	mustContain(t, out, "says 0.1.5", "the refusal must quote what the ground actually says")
	mustContain(t, out, "v0.1.5", "the refusal must name the mark that WOULD be lawful")
	mustNotContain(t, out, "Cut v", "nothing may be cut on a disagreement")
}

// THE STROKE THE WHOLE DESIGN EXISTS FOR. The version is read AT THE COMMIT,
// out of git -- never off the disk. The disk is the tip, and a mark is often
// cut at an older commit: checking a tag against a VERSION that moved AFTER it
// is exactly how a green check passes a wrong tag.
func TestTheVersionIsReadAtTheCommitAndNotOffTheDisk(t *testing.T) {
	tn := versionWorld(t, "0.1.5")
	old := headOf(t, tn)
	saveVersion(t, tn, "0.2.0") // the ground moves on; the disk now says 0.2.0

	out := call(t, toolGitTag, tn, map[string]any{
		"action": "cut", "name": "v0.1.5", "message": "the flow confirmation", "at": old})
	mustContain(t, out, "Cut v0.1.5", "the version AT THE COMMIT is what a mark is judged against")
	mustContain(t, out, "saying 0.1.5", "the answer must cite the version it agreed with")

	// And the tip's own number is refused AT THAT OLDER COMMIT, which is the
	// same fault from the other side.
	out = call(t, toolGitTag, tn, map[string]any{
		"action": "cut", "name": "v0.2.0", "message": "the tip's number, at the wrong commit", "at": old})
	mustContain(t, out, "says 0.1.5", "the older commit's own declaration is what governs there")
}

// Re-pointing a mark that has been fetched is a force-push whose victim never
// finds out: his clone keeps the old object and agrees with nobody.
func TestAMarkIsNeverMoved(t *testing.T) {
	tn := versionWorld(t, "0.1.5")
	first := call(t, toolGitTag, tn, map[string]any{
		"action": "cut", "name": "v0.1.5", "message": "the flow confirmation"})
	mustContain(t, first, "Cut v0.1.5", "the first cut must land")

	write(t, tn.Home, "after.txt", "later work\n")
	if out, err := gitRun(tn, 30*time.Second, "add", "-A"); err != nil {
		t.Fatalf("add: %v\n%s", err, out)
	}
	if out, err := gitRun(tn, 30*time.Second, "commit", "-m", "later"); err != nil {
		t.Fatalf("commit: %v\n%s", err, out)
	}
	again := call(t, toolGitTag, tn, map[string]any{
		"action": "cut", "name": "v0.1.5", "message": "the same name, a new commit"})
	mustContain(t, again, "already exists here", "a second cut of the same name must refuse")
	mustContain(t, again, "never moved", "the refusal must say why")
}

// THE ORDER OF TWO GUARDS IS ITSELF THE POINT. The ordinary way to arrive here
// is to bump the version file and forget to save it -- so the unsaved-work
// refusal must come FIRST, or that person is told the mark and the ground
// disagree, which is true and no help at all.
func TestAMarkAtHeadIsRefusedOverUnsavedWorkButAnOlderCommitIsNot(t *testing.T) {
	tn := versionWorld(t, "0.1.5")
	old := headOf(t, tn)
	saveVersion(t, tn, "0.2.0")
	write(t, tn.Home, "unsaved.txt", "work in hand\n")

	// At HEAD the name would AGREE with the file, and it still refuses.
	out := call(t, toolGitTag, tn, map[string]any{
		"action": "cut", "name": "v0.2.0", "message": "cut over a dirty tree"})
	mustContain(t, out, "unsaved work", "a mark at HEAD over unsaved work must refuse")
	mustContain(t, out, "bumped the version file", "the refusal must name the usual cause")
	mustNotContain(t, out, "disagree", "the unsaved-work refusal must come before the version one")

	// An older commit has nothing to do with what is unsaved now.
	out = call(t, toolGitTag, tn, map[string]any{
		"action": "cut", "name": "v0.1.5", "message": "the older mark", "at": old})
	mustContain(t, out, "Cut v0.1.5", "unsaved work must not block a mark at an older commit")
}

func TestAMarkNeedsAMessageAndAVersionToAgreeWith(t *testing.T) {
	tn := versionWorld(t, "0.1.5")
	out := call(t, toolGitTag, tn, map[string]any{"action": "cut", "name": "v0.1.5"})
	mustContain(t, out, "needs a message", "a mark with no message must refuse")
	mustNotContain(t, out, "Cut v", "nothing may be cut without a message")

	// A world that declares nothing has nothing for a mark to mean.
	bare := tempWorld(t)
	out = call(t, toolGitTag, bare, map[string]any{
		"action": "cut", "name": "v0.1.5", "message": "against nothing"})
	mustContain(t, out, "declares no version", "an undeclared world must refuse the mark")
	mustContain(t, out, "mean nothing", "the refusal must say why that matters")
}

func TestSendingAMarkIsWalledAndNamesAMarkItCannotFind(t *testing.T) {
	tn := versionWorld(t, "0.1.5")
	t.Setenv("MANJUEL_GIT_REMOTE", "")
	t.Setenv("CHAINKIT_GIT_REMOTE", "")
	out := call(t, toolGitTag, tn, map[string]any{"action": "send", "name": "v0.1.5"})
	mustContain(t, out, "MANJUEL_GIT_REMOTE", "a shut wall must refuse the send and name the dial")
	mustContain(t, out, "operator's alone", "the refusal must say whose the dial is")

	// With the wall OPEN, a mark that was never cut is still refused -- and
	// this refusal is not the wall's.
	t.Setenv("MANJUEL_GIT_REMOTE", "1")
	out = call(t, toolGitTag, tn, map[string]any{"action": "send", "name": "v9.9.9"})
	mustContain(t, out, "no mark called v9.9.9", "an uncut mark must be named, not sent")
	mustNotContain(t, out, "MANJUEL_GIT_REMOTE", "this refusal is not the wall's")
}

func TestTheMarkListNamesWhatIsCutAndWhatTheGroundDeclares(t *testing.T) {
	tn := versionWorld(t, "0.1.5")
	t.Setenv("MANJUEL_GIT_REMOTE", "")
	t.Setenv("CHAINKIT_GIT_REMOTE", "")

	var before struct {
		Tags       []map[string]any `json:"tags"`
		Declared   string           `json:"declared"`
		DeclaredBy string           `json:"declared_by"`
		Next       string           `json:"next"`
		SentKnown  bool             `json:"sent_known"`
	}
	if err := json.Unmarshal([]byte(call(t, toolGitTag, tn, nil)), &before); err != nil {
		t.Fatalf("the list must be JSON: %v", err)
	}
	if len(before.Tags) != 0 {
		t.Fatalf("an unmarked world must list no marks: %v", before.Tags)
	}
	if before.Declared != "0.1.5" || before.DeclaredBy != "VERSION" || before.Next != "v0.1.5" {
		t.Fatalf("the list must say what the ground declares and what that makes the mark: %+v", before)
	}
	// WITH THE WALL SHUT, WHAT GITHUB HAS IS NOT KNOWN -- and the answer says
	// so rather than guessing false.
	if before.SentKnown {
		t.Fatal("a shut wall cannot know what the remote holds")
	}

	call(t, toolGitTag, tn, map[string]any{
		"action": "cut", "name": "v0.1.5", "message": "the flow confirmation"})
	var after struct {
		Tags []struct {
			Name    string `json:"name"`
			Subject string `json:"subject"`
			Sent    bool   `json:"sent"`
		} `json:"tags"`
	}
	if err := json.Unmarshal([]byte(call(t, toolGitTag, tn, nil)), &after); err != nil {
		t.Fatalf("the list must be JSON: %v", err)
	}
	if len(after.Tags) != 1 || after.Tags[0].Name != "v0.1.5" {
		t.Fatalf("the cut mark must be listed: %+v", after.Tags)
	}
	if after.Tags[0].Subject != "the flow confirmation" {
		t.Fatalf("the mark's own message must be carried: %+v", after.Tags[0])
	}
	if after.Tags[0].Sent {
		t.Fatal("a mark that was never sent must not be reported as sent")
	}
}

func TestAnUnknownTagActionIsRefusedByName(t *testing.T) {
	tn := versionWorld(t, "0.1.5")
	out := call(t, toolGitTag, tn, map[string]any{"action": "delete", "name": "v0.1.5"})
	mustContain(t, out, `"delete" is not something this does`, "an unknown verb must be named")
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
		"git_tag":    toolGitTag,
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
