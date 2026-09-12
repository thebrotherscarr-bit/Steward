package tools

// gitctl: the verbs that CHANGE a repository, as against gitstate.go which
// only reports one. Split on purpose -- gitstate.go's own header promises
// "REMOTE OPERATIONS ARE REPORTED, NEVER PERFORMED", and a file must not
// quietly stop meaning what it says at the top.
//
// WHOSE HAND THIS IS. RULE 6: no agent commits, pushes, or lands. Nothing
// here violates that, because nothing here fires on its own -- these are the
// buttons on the operator's own glass, and the hand on the button is his. The
// tool is the instrument, not the decision. He asked for exactly this on
// 2026-09-10: "this page is for the git versioning, it needs to be able to
// control which ones are open and closed, which repos are mains, branches."
//
// PLAIN GIT, NOT gh. The GitHub CLI is free and open source and sitting on
// this machine, and it still does not go in: RULE 4 walls anything that needs
// someone else's server ("this holds even when the remote thing is better,
// free, or open source") and atlas law 6 is "zero external dependencies --
// hand-roll or refuse". Everything the operator named -- branches, mains,
// open and closed, sending -- is plain git. What gh alone could add is
// GitHub-side objects (pull requests, issues, releases, CI runs), and those
// are a separate wall to open deliberately, not a dependency to acquire by
// accident.
//
// THREE RULES EVERY VERB HERE KEEPS:
//   1. stdin closed, every call. A child that inherits a headless door's
//      stdin deadlocks on a pipe another thread is already reading. That cost
//      this estate nine sittings on 2026-09-10.
//   2. jailed to the tenant's Home. cmd.Dir is never anything else, and a
//      path argument is resolved before it is judged, never judged as stated.
//   3. sending is walled. push and pull refuse BY NAME when the estate's
//      dial is shut. The wall is read, never opened, from here.

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"atlas/line/internal/tenant"
)

// gitRun runs one git command in a tenant's ground and returns everything it
// said. Unlike gitstate's helper this keeps stderr: a refused push explains
// itself there, and swallowing it would turn a nameable failure into a shrug.
func gitRun(t tenant.Tenant, timeout time.Duration, args ...string) (string, error) {
	// Through the one spawn contract (ADR-006 item 5). This seam already had
	// the discipline — closed stdin, a bound, hardened env, stderr kept —
	// and it was the ONLY one of the four that had all of it. What was local
	// here is now what every seam gets.
	res := spawn("git", args, spawnOpts{Dir: t.Home, Timeout: timeout, Env: gitEnv()})
	return strings.TrimRight(res.Combined, "\r\n"), res.Err
}

func isRepo(t tenant.Tenant) bool {
	_, err := gitRun(t, 5*time.Second, "rev-parse", "--is-inside-work-tree")
	return err == nil
}

// notARepo is the same honest denial everywhere, so the glass can match on it.
const notARepo = "Refused: this world is not a repository -- there is nothing to save, and nothing to lose."

// branchName is git's own law for refs, narrowed: no spaces, no leading dash,
// none of the characters git itself rejects. Checked here so a bad name is
// refused by name instead of becoming an argument git reads as a flag.
func badBranchName(b string) string {
	if b == "" {
		return "Refused: name the branch."
	}
	if strings.HasPrefix(b, "-") {
		return "Refused: a branch name may not begin with '-' -- git would read it as a flag."
	}
	for _, bad := range []string{" ", "..", "~", "^", ":", "?", "*", "[", "\\", "@{"} {
		if strings.Contains(b, bad) {
			return fmt.Sprintf("Refused: %q is not a lawful branch name (%q is not allowed).", b, bad)
		}
	}
	if strings.HasSuffix(b, "/") || strings.HasSuffix(b, ".lock") {
		return fmt.Sprintf("Refused: %q is not a lawful branch name.", b)
	}
	return ""
}

// --- saving ----------------------------------------------------------------

// toolGitCommit stages the whole tree and records it. WRITES.
//
// EVERYTHING, OR WHAT HE NAMED. With no `files` it is `git add -A` -- the
// operator's own words, 2026-09-10: "the whole thing will commit to git,
// obviously". Naming files narrows it to those, each jailed the same way.
//
// A MESSAGE IS NOT OPTIONAL. An empty message is refused rather than filled
// in: the subject line is the record of why, and a hand that invents one is
// writing his history for him.
//
// NOTHING IS SENT. A commit is local. Sending is git_push, behind the wall.
func toolGitCommit(t tenant.Tenant, args map[string]any) (string, error) {
	if !isRepo(t) {
		return notARepo, nil
	}
	msg := strings.TrimSpace(str(args, "message"))
	if msg == "" {
		return "Refused: a save needs a message saying what it is. Nothing was staged.", nil
	}

	var paths []string
	if raw := strings.TrimSpace(str(args, "files")); raw != "" {
		for _, p := range strings.Split(raw, "\n") {
			p = strings.TrimSpace(p)
			if p == "" {
				continue
			}
			if refusal := jailed(t, p); refusal != "" {
				return refusal, nil
			}
			paths = append(paths, p)
		}
	}

	add := []string{"add", "-A"}
	if len(paths) > 0 {
		add = append([]string{"add", "--"}, paths...)
	}
	if out, err := gitRun(t, 60*time.Second, add...); err != nil {
		return "Refused: nothing was staged -- " + firstLine(out), nil
	}

	staged, _ := gitRun(t, 30*time.Second, "diff", "--cached", "--name-only")
	if strings.TrimSpace(staged) == "" {
		return "Nothing to save: the tree already matches the last save.", nil
	}
	n := len(strings.Split(strings.TrimSpace(staged), "\n"))

	out, err := gitRun(t, 120*time.Second, "commit", "-m", msg)
	if err != nil {
		return "Refused: the save did not land -- " + firstLine(out), nil
	}
	head, _ := gitRun(t, 10*time.Second, "rev-parse", "--short", "HEAD")
	return fmt.Sprintf("Saved %d file%s as %s: %q\n\n%s",
		n, plural(n), head, msg, out), nil
}

// --- sending ---------------------------------------------------------------

// toolGitPush sends the saves this world has and the remote does not. WRITES,
// and walled: the dial is the operator's, read here and never opened here.
func toolGitPush(t tenant.Tenant, args map[string]any) (string, error) {
	if !isRepo(t) {
		return notARepo, nil
	}
	if !dial(t.Home, "GIT_REMOTE") {
		return walled("Sending"), nil
	}
	branch, err := currentBranch(t)
	if err != nil {
		return "Refused: this world has no branch to send (no commits yet).", nil
	}

	// AN UPSTREAM IS SET ONCE, DELIBERATELY, AND SAID OUT LOUD. A silent
	// --set-upstream binds a local branch to a remote one forever; the
	// operator is told when that happened and to what.
	first := false
	if _, e := gitRun(t, 10*time.Second, "rev-parse", "--abbrev-ref", "@{upstream}"); e != nil {
		first = true
	}
	cmd := []string{"push"}
	if first {
		cmd = append(cmd, "--set-upstream", "origin", branch)
	}
	out, err := gitRun(t, 300*time.Second, cmd...)
	if err != nil {
		return "Sending refused by the remote -- " + firstLine(out) + "\n\n" + out, nil
	}
	note := ""
	if first {
		note = fmt.Sprintf("\n\nThis branch had never been sent before; it now follows origin/%s.", branch)
	}
	if strings.TrimSpace(out) == "" {
		out = "Nothing to send: the remote already has everything here."
	}
	return fmt.Sprintf("Sent %s to origin.\n\n%s%s", branch, out, note), nil
}

// toolGitPull fetches and fast-forwards. WRITES, and walled.
//
// FAST-FORWARD ONLY. A merge commit the operator did not ask for is a change
// to his history made by a machine. If the branches have diverged this
// refuses and says so, leaving the decision where it belongs.
func toolGitPull(t tenant.Tenant, args map[string]any) (string, error) {
	if !isRepo(t) {
		return notARepo, nil
	}
	if !dial(t.Home, "GIT_REMOTE") {
		return walled("Fetching"), nil
	}
	if dirty(t) {
		return "Refused: there is unsaved work here. Save it first -- a fetch " +
			"over a dirty tree is how work goes missing.", nil
	}
	out, err := gitRun(t, 300*time.Second, "pull", "--ff-only")
	if err != nil {
		return "Fetching refused -- " + firstLine(out) +
			"\n\nThis pulls fast-forward only: if this world and the remote have " +
			"both moved, joining them is your call, not the door's.\n\n" + out, nil
	}
	if strings.Contains(out, "Already up to date") {
		return "Already in step: the remote has nothing this world does not.", nil
	}
	return "Fetched and caught up.\n\n" + out, nil
}

func walled(what string) string {
	return "Refused: " + what + " is OFF. The estate's wall (MANJUEL_GIT_REMOTE) " +
		"is shut, so nothing here reaches the remote. That dial is the " +
		"operator's alone -- this door reads it and never opens it."
}

// --- the marks a version is cut at -----------------------------------------

// toolGitTag lists the marks on this world's history, cuts one, or sends one.
//
// A TAG IS THE ONE ARTIFACT A STRANGER TAKES ON FAITH. He fetches v0.1.5 and
// believes it is 0.1.5 because the name says so, and unlike a branch a mark is
// not expected to move under him. Every refusal below exists to keep that one
// sentence true.
//
// `action` is list (default) | cut | send.
func toolGitTag(t tenant.Tenant, args map[string]any) (string, error) {
	if !isRepo(t) {
		return notARepo, nil
	}
	action := strings.ToLower(strings.TrimSpace(str(args, "action")))
	if action == "" {
		action = "list"
	}
	name := strings.TrimSpace(str(args, "name"))

	switch action {
	case "list":
		return tagList(t)
	case "cut", "new":
		return tagCut(t, name, strings.TrimSpace(str(args, "message")),
			strings.TrimSpace(str(args, "at")))
	case "send", "push":
		return tagSend(t, name)
	}
	return fmt.Sprintf("Refused: %q is not something this does. It lists the marks "+
		"(list), cuts one (cut), or sends one to GitHub (send).", action), nil
}

// badTagName is stricter than git's own law for refs, deliberately: this door
// cuts VERSION marks and nothing else, so the only lawful shape is
// vMAJOR.MINOR.PATCH.
//
// EARNED 2026-09-12. release.ps1 appended a build moniker to the tag it told
// the operator to cut -- a plain 0.1.5 came out of it as `v0.1.5+f1`, which no
// longer equals what VERSION says. atlas's own release.yml refuses that on
// arrival; refusing it HERE kills it before the mark exists at all, which
// matters because a mark that has been sent may already have been fetched.
func badTagName(v string) string {
	if v == "" {
		return "Refused: name the mark, e.g. v0.1.5."
	}
	if !strings.HasPrefix(v, "v") {
		return fmt.Sprintf("Refused: %q does not begin with 'v'. A version mark "+
			"here is vMAJOR.MINOR.PATCH, e.g. v0.1.5.", v)
	}
	parts := strings.Split(strings.TrimPrefix(v, "v"), ".")
	if len(parts) != 3 {
		return fmt.Sprintf("Refused: %q is not vMAJOR.MINOR.PATCH -- three numbers "+
			"and two dots, e.g. v0.1.5.", v)
	}
	for _, p := range parts {
		if p == "" {
			return fmt.Sprintf("Refused: %q is not vMAJOR.MINOR.PATCH -- three "+
				"numbers and two dots, e.g. v0.1.5.", v)
		}
		for _, c := range p {
			if c < '0' || c > '9' {
				return fmt.Sprintf("Refused: %q carries %q, which is not a number. "+
					"A version mark is vMAJOR.MINOR.PATCH and nothing else -- no "+
					"build moniker, no suffix, no trailing word. A mark that does "+
					"not equal what the version file says is a lie to whoever "+
					"fetches it.", v, string(c))
			}
		}
	}
	return ""
}

// declaredVersionAt reads the version the ground DECLARED AT THAT COMMIT --
// out of git, never off the disk.
//
// The disk is the tip. A mark may be cut at an older commit, and checking a
// tag against a VERSION that moved AFTER that commit is exactly how a green
// check passes a wrong tag. This is the same arithmetic release.yml does by
// checking the tag out before it compares.
//
// Two spellings, because this estate has two kinds of world: a VERSION file
// (atlas) and pyproject.toml (the core). Returns the version and the name of
// the file that said so, so a refusal can cite its source.
func declaredVersionAt(t tenant.Tenant, rev string) (string, string) {
	if out, err := gitRun(t, 15*time.Second, "show", rev+":VERSION"); err == nil {
		if v := strings.TrimSpace(out); v != "" {
			return v, "VERSION"
		}
	}
	if out, err := gitRun(t, 15*time.Second, "show", rev+":pyproject.toml"); err == nil {
		for _, ln := range strings.Split(out, "\n") {
			ln = strings.TrimSpace(ln)
			if !strings.HasPrefix(ln, "version") {
				continue
			}
			rest := strings.TrimSpace(strings.TrimPrefix(ln, "version"))
			if !strings.HasPrefix(rest, "=") {
				continue
			}
			v := strings.Trim(strings.TrimSpace(strings.TrimPrefix(rest, "=")), "\"'")
			if v != "" {
				return v, "pyproject.toml"
			}
		}
	}
	return "", ""
}

// tagCut cuts ONE annotated mark, at a commit whose declared version it must
// equal. WRITES, and local: sending is a separate button behind the wall.
func tagCut(t tenant.Tenant, name, message, at string) (string, error) {
	if refusal := badTagName(name); refusal != "" {
		return refusal, nil
	}
	if message == "" {
		return "Refused: a mark needs a message saying what this version is. " +
			"Nothing was cut -- the name carries the number and the message " +
			"carries what it was for.", nil
	}
	if at == "" {
		at = "HEAD"
	}
	sha, err := gitRun(t, 10*time.Second, "rev-parse", "--verify", at+"^{commit}")
	if err != nil {
		return fmt.Sprintf("Refused: %q is not a commit in this world.", at), nil
	}
	sha = strings.TrimSpace(sha)

	// A MARK IS NEVER MOVED. Re-pointing a tag that has been fetched is the
	// same act as a force-push, except the fetcher never finds out: his clone
	// keeps the old object and agrees with nobody. The next number is free.
	if _, err := gitRun(t, 10*time.Second, "rev-parse", "--verify", "refs/tags/"+name); err == nil {
		short, _ := gitRun(t, 10*time.Second, "rev-parse", "--short", "refs/tags/"+name+"^{commit}")
		return fmt.Sprintf("Refused: %s already exists here, on %s. A mark is "+
			"never moved -- anyone who already fetched it would keep the old one "+
			"and never learn it changed. Cut the next number instead.",
			name, strings.TrimSpace(short)), nil
	}

	// UNSAVED WORK IS CHECKED BEFORE THE VERSION IS. This order is the whole
	// usefulness of the refusal: the ordinary way to arrive here is to bump
	// the version file and forget to save it, and then the version AT HEAD is
	// still the old one. Checked the other way round, that person is told the
	// mark and the ground disagree -- true, and no help at all.
	headSha, _ := gitRun(t, 10*time.Second, "rev-parse", "--verify", "HEAD^{commit}")
	if strings.TrimSpace(headSha) == sha && dirty(t) {
		return "Refused: there is unsaved work here. Save it first -- a mark cut " +
			"now would point at a commit that is not what is on your disk, and " +
			"nothing built from it would be what you tested. If you have just " +
			"bumped the version file, that bump is part of what needs saving.", nil
	}

	// THE THREE THINGS THAT MUST AGREE: the name, the file, and plain semver
	// (badTagName, above). The same arithmetic release.yml runs on arrival.
	declared, source := declaredVersionAt(t, sha)
	if declared == "" {
		return "Refused: this world declares no version at that commit -- no " +
			"VERSION file, and no version in pyproject.toml. There is nothing " +
			"for the mark to agree with, so the mark would mean nothing.", nil
	}
	if "v"+declared != name {
		return fmt.Sprintf("Refused: the mark and the ground disagree. You asked "+
			"for %s; %s at that commit says %s, so the mark to cut there is v%s. "+
			"Bump the file or change the name -- but a stranger fetches %s and "+
			"believes it is %s because the name says so, and this refusal is "+
			"what keeps that true.",
			name, source, declared, declared, name, strings.TrimPrefix(name, "v")), nil
	}

	out, err := gitRun(t, 30*time.Second, "tag", "-a", name, "-m", message, sha)
	if err != nil {
		return "Refused: the mark did not land -- " + firstLine(out), nil
	}
	short, _ := gitRun(t, 10*time.Second, "rev-parse", "--short", sha)
	subject, _ := gitRun(t, 10*time.Second, "log", "-1", "--format=%s", sha)
	return fmt.Sprintf("Cut %s at %s (%q), against %s saying %s.\n\nIt is on this "+
		"machine only -- sending it is a separate button.",
		name, strings.TrimSpace(short), strings.TrimSpace(subject), source, declared), nil
}

// tagSend sends ONE named mark. WRITES, and walled like every other verb that
// reaches a remote.
func tagSend(t tenant.Tenant, name string) (string, error) {
	if refusal := badTagName(name); refusal != "" {
		return refusal, nil
	}
	if !dial(t.Home, "GIT_REMOTE") {
		return walled("Sending"), nil
	}
	if _, err := gitRun(t, 10*time.Second, "rev-parse", "--verify", "refs/tags/"+name); err != nil {
		return fmt.Sprintf("Refused: there is no mark called %s here to send. "+
			"Cut it first.", name), nil
	}
	// ONE MARK, NAMED IN FULL. Never --tags, which sends every mark this
	// machine holds. That is the same class as `git push --all`, which is
	// written into CLAUDE.md RULE 1 because it has already cost this estate
	// something: a verb that looks like it acts on the thing you named quietly
	// acts on all of them.
	out, err := gitRun(t, 300*time.Second, "push", "origin", "refs/tags/"+name)
	if err != nil {
		return fmt.Sprintf("Sending refused by the remote -- %s\n\n%s",
			firstLine(out), out), nil
	}
	if strings.TrimSpace(out) == "" {
		out = "GitHub already had it."
	}
	return fmt.Sprintf("Sent %s to origin.\n\n%s", name, out), nil
}

// tagList names every mark, newest first, and says which ones GitHub has.
func tagList(t tenant.Tenant) (string, error) {
	raw, _ := gitRun(t, 15*time.Second, "for-each-ref", "--sort=-creatordate",
		"--format=%(refname:short)\t%(objectname:short)\t%(creatordate:relative)\t%(contents:subject)",
		"refs/tags")

	// WHAT GITHUB HAS IS ASKED OF GITHUB, and only while the wall is open. A
	// local repository genuinely does not know what a remote holds, and a
	// guess dressed as a fact is the one thing this panel must never show.
	// `sent_known` says which of the two answers the caller is looking at.
	sent := map[string]bool{}
	known := false
	if dial(t.Home, "GIT_REMOTE") {
		if ls, err := gitRun(t, 30*time.Second, "ls-remote", "--tags", "origin"); err == nil {
			known = true
			for _, ln := range strings.Split(ls, "\n") {
				f := strings.Fields(ln)
				if len(f) < 2 {
					continue
				}
				n := strings.TrimSuffix(strings.TrimPrefix(f[1], "refs/tags/"), "^{}")
				sent[n] = true
			}
		}
	}

	type mark struct {
		Name    string `json:"name"`
		At      string `json:"at"`
		When    string `json:"when"`
		Subject string `json:"subject"`
		Sent    bool   `json:"sent"`
	}
	marks := []mark{}
	for _, ln := range strings.Split(raw, "\n") {
		if strings.TrimSpace(ln) == "" {
			continue
		}
		f := strings.SplitN(ln, "\t", 4)
		for len(f) < 4 {
			f = append(f, "")
		}
		marks = append(marks, mark{
			Name: f[0], At: f[1], When: f[2], Subject: f[3], Sent: sent[f[0]],
		})
	}

	declared, source := declaredVersionAt(t, "HEAD")
	next := ""
	if declared != "" {
		next = "v" + declared
	}
	doc := map[string]any{
		"world":       t.Name,
		"tags":        marks,
		"declared":    declared,
		"declared_by": source,
		"next":        next,
		"sent_known":  known,
	}
	b, err := json.MarshalIndent(doc, "", " ")
	return string(b), err
}

// --- lines of work ---------------------------------------------------------

// toolGitBranch lists, opens, switches or closes a line of work.
//
// The operator's words for these, 2026-09-10, and the words the glass uses:
// a branch is a LINE OF WORK, main is THE MAIN LINE, creating one is OPENING
// it and deleting one is CLOSING it.
//
// `action` is list (default) | new | switch | close.
func toolGitBranch(t tenant.Tenant, args map[string]any) (string, error) {
	if !isRepo(t) {
		return notARepo, nil
	}
	action := strings.ToLower(strings.TrimSpace(str(args, "action")))
	if action == "" {
		action = "list"
	}
	name := strings.TrimSpace(str(args, "name"))

	switch action {
	case "list":
		return branchList(t)

	case "new", "open":
		if refusal := badBranchName(name); refusal != "" {
			return refusal, nil
		}
		out, err := gitRun(t, 30*time.Second, "switch", "-c", name)
		if err != nil {
			return "Refused: that line could not be opened -- " + firstLine(out), nil
		}
		return fmt.Sprintf("Opened %q and moved you onto it. It exists only here "+
			"until you send it.", name), nil

	case "switch", "use":
		if refusal := badBranchName(name); refusal != "" {
			return refusal, nil
		}
		if dirty(t) {
			return "Refused: there is unsaved work here. Save it first, or it " +
				"follows you onto the other line and confuses both.", nil
		}
		out, err := gitRun(t, 30*time.Second, "switch", name)
		if err != nil {
			return "Refused: could not move to that line -- " + firstLine(out), nil
		}
		return fmt.Sprintf("You are now on %q.", name), nil

	case "close", "delete":
		if refusal := badBranchName(name); refusal != "" {
			return refusal, nil
		}
		cur, _ := currentBranch(t)
		if name == cur {
			return "Refused: you are standing on that line. Move to another one first.", nil
		}
		// UNMERGED WORK IS NOT THROWN AWAY ON A GUESS. Plain -d refuses a
		// branch git cannot see folded in; that refusal is kept and reported
		// rather than escalated to -D behind his back.
		out, err := gitRun(t, 30*time.Second, "branch", "-d", name)
		if err != nil {
			if strings.Contains(out, "not fully merged") {
				return fmt.Sprintf("Refused: %q holds work that is not on any other "+
					"line. Closing it would lose that work. Merge it first, or "+
					"close it yourself with `git branch -D %s` if you mean to "+
					"discard it.", name, name), nil
			}
			return "Refused: could not close that line -- " + firstLine(out), nil
		}
		return fmt.Sprintf("Closed %q. Its work is already on another line.", name), nil
	}
	return fmt.Sprintf("Refused: %q is not something this does. It lists, opens "+
		"(new), moves to (switch), or closes (close) a line of work.", action), nil
}

func branchList(t tenant.Tenant) (string, error) {
	cur, _ := currentBranch(t)
	// One line per branch, git's own format, no pager, no colour.
	raw, _ := gitRun(t, 15*time.Second, "for-each-ref", "--sort=-committerdate",
		"--format=%(refname:short)\t%(upstream:short)\t%(committerdate:relative)\t%(contents:subject)",
		"refs/heads")
	type line struct {
		Name     string `json:"name"`
		Current  bool   `json:"current"`
		Main     bool   `json:"main"`
		Upstream string `json:"upstream"`
		Sent     bool   `json:"sent"`
		When     string `json:"when"`
		Subject  string `json:"subject"`
	}
	var lines []line
	for _, ln := range strings.Split(raw, "\n") {
		if strings.TrimSpace(ln) == "" {
			continue
		}
		f := strings.SplitN(ln, "\t", 4)
		for len(f) < 4 {
			f = append(f, "")
		}
		lines = append(lines, line{
			Name:     f[0],
			Current:  f[0] == cur,
			Main:     f[0] == "main" || f[0] == "master",
			Upstream: f[1],
			Sent:     f[1] != "",
			When:     f[2],
			Subject:  f[3],
		})
	}
	out := map[string]any{
		"world":    t.Name,
		"on":       cur,
		"branches": lines,
	}
	b, err := json.MarshalIndent(out, "", " ")
	return string(b), err
}

// --- remotes ---------------------------------------------------------------

// toolGitRemote names where this world sends, and whether the wall is open.
// Read-only: it never adds, renames or removes one. Pointing a repository at
// a different server is not a button, it is a decision.
func toolGitRemote(t tenant.Tenant, args map[string]any) (string, error) {
	if !isRepo(t) {
		return notARepo, nil
	}
	raw, _ := gitRun(t, 15*time.Second, "remote", "-v")
	seen := map[string]string{}
	var order []string
	for _, ln := range strings.Split(raw, "\n") {
		f := strings.Fields(ln)
		if len(f) < 2 {
			continue
		}
		if _, dup := seen[f[0]]; !dup {
			order = append(order, f[0])
		}
		seen[f[0]] = f[1]
	}
	type rem struct {
		Name string `json:"name"`
		URL  string `json:"url"`
		Host string `json:"host"`
	}
	var out []rem
	for _, n := range order {
		out = append(out, rem{Name: n, URL: seen[n], Host: hostOf(seen[n])})
	}
	doc := map[string]any{
		"world":          t.Name,
		"remotes":        out,
		"remote_allowed": dial(t.Home, "GIT_REMOTE"),
	}
	b, err := json.MarshalIndent(doc, "", " ")
	return string(b), err
}

// hostOf names the server a remote URL points at, for both spellings git
// accepts. RULE 7-adjacent: a URL can carry a token in its userinfo, so only
// the host is ever lifted out, never the whole string's credentials part.
func hostOf(url string) string {
	u := url
	if i := strings.Index(u, "://"); i >= 0 {
		u = u[i+3:]
	}
	if i := strings.LastIndex(u, "@"); i >= 0 {
		u = u[i+1:]
	}
	for _, cut := range []string{"/", ":"} {
		if i := strings.Index(u, cut); i >= 0 {
			u = u[:i]
		}
	}
	return u
}

// --- shared ----------------------------------------------------------------

func currentBranch(t tenant.Tenant) (string, error) {
	out, err := gitRun(t, 10*time.Second, "rev-parse", "--abbrev-ref", "HEAD")
	if err != nil || strings.TrimSpace(out) == "" {
		return "", fmt.Errorf("no branch")
	}
	return strings.TrimSpace(out), nil
}

func dirty(t tenant.Tenant) bool {
	out, err := gitRun(t, 15*time.Second, "status", "--porcelain")
	return err == nil && strings.TrimSpace(out) != ""
}

// jailed judges a path the way the estate's gate does: resolve first, refuse
// what escapes, never judge the stated form. Returns "" when the path is
// lawful.
func jailed(t tenant.Tenant, rel string) string {
	if strings.HasPrefix(rel, "/") || strings.HasPrefix(rel, "\\") || strings.Contains(rel, ":") {
		return "Refused: an absolute path is outside this world (" + rel + ")."
	}
	home, err := filepath.Abs(t.Home)
	if err != nil {
		return "Refused: this world's home could not be resolved."
	}
	full, err := filepath.Abs(filepath.Join(home, rel))
	if err != nil {
		return "Refused: that path could not be resolved (" + rel + ")."
	}
	if full != home && !strings.HasPrefix(full, home+string(os.PathSeparator)) {
		return "Refused: that path resolves outside this world (" + rel + ")."
	}
	return ""
}

func firstLine(s string) string {
	s = strings.TrimSpace(s)
	if s == "" {
		return "git said nothing"
	}
	if i := strings.IndexAny(s, "\r\n"); i >= 0 {
		return s[:i]
	}
	return s
}

func plural(n int) string {
	if n == 1 {
		return ""
	}
	return "s"
}
