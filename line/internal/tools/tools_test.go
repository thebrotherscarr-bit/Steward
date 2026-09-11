// Strokes for the readers: records, proofs and seats.
//
// `internal/tools` carries every MCP tool handler and had none of these until
// 2026-09-10. gitctl_test.go covered the verbs that WRITE; these cover the three
// that READ the estate's own record, which is where a quiet wrong answer does
// the most damage -- a page that misreports what was proven is worse than a page
// that shows nothing, and all three of these exist because an earlier page did
// exactly that.
//
// HERMETIC BY LAW 5: every stroke builds its own ground in t.TempDir(). Nothing
// reads the estate's real record, nothing writes, nothing reaches a network.
//
// runstream.go is NOT covered here and that is deliberate: RunStream, Answer-
// Stream and ListenStream all require a live engine on an open sitting, which is
// not a thing a hermetic stroke can stand up. It is named in tests/PROVING.md as
// still uncovered rather than papered over with a mock that would prove the mock.
package tools

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"atlas/line/internal/tenant"
)

// --- ground ----------------------------------------------------------------

func world(t *testing.T, files map[string]string) tenant.Tenant {
	t.Helper()
	home := t.TempDir()
	for rel, body := range files {
		p := filepath.Join(home, filepath.FromSlash(rel))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return tenant.Tenant{Name: "probe", Home: home, Manifest: tenant.DefaultManifest()}
}

// jsonOf runs a tool and parses what it answered, failing on a hard error.
func jsonOf(t *testing.T, fn func(tenant.Tenant, map[string]any) (string, error),
	tn tenant.Tenant, args map[string]any) map[string]any {
	t.Helper()
	out, err := fn(tn, args)
	if err != nil {
		t.Fatalf("tool errored: %v", err)
	}
	var m map[string]any
	if err := json.Unmarshal([]byte(out), &m); err != nil {
		t.Fatalf("tool did not answer JSON: %v\n%s", err, out)
	}
	return m
}

func has(t *testing.T, got, want, why string) {
	t.Helper()
	if !strings.Contains(got, want) {
		t.Fatalf("%s\n  wanted %q in:\n%s", why, want, got)
	}
}

// --- records: what the estate carries ---------------------------------------

func TestRecordsSortsByWhatADocumentIs(t *testing.T) {
	tn := world(t, map[string]string{
		"CLAUDE.md":            "the rules",
		"CHANGELOG.md":         "what changed",
		"SPEC.md":              "what it is",
		"pipelines.md":         "## Pipeline: default\n1. Steward\n",
		"law/ESTATE_LAWS.md":   "the ten",
		"agents/steward.md":    "## Steward\n",
		"skills/git_status.md": "# Skill\n",
		"logs/a_run.md":        "a transcript",
		"WANDERING.md":         "claimed by nothing",
	})
	d := jsonOf(t, toolRecords, tn, nil)

	kinds := map[string]int{}
	for _, k := range d["kinds"].([]any) {
		m := k.(map[string]any)
		kinds[m["kind"].(string)] = int(m["count"].(float64))
	}
	for kind, n := range map[string]int{
		"doctrine": 2, "record": 1, "spec": 1, "commands": 1,
		"agents": 1, "skills": 1, "logs": 1, "other": 1,
	} {
		if kinds[kind] != n {
			t.Fatalf("kind %q holds %d, wanted %d (%v)", kind, kinds[kind], n, kinds)
		}
	}
	// ALPHABETICAL WOULD PUT AGENTS ABOVE THE LAW. The order is the estate's
	// furniture: what binds a hand first, what happened second.
	first := d["kinds"].([]any)[0].(map[string]any)["kind"]
	if first != "doctrine" {
		t.Fatalf("the law does not come first: %v", first)
	}
	// A root file no set claims is still SHOWN -- nothing is hidden.
	check := jsonOf(t, toolRecords, tn, map[string]any{"kind": "other"})
	has(t, check["documents"].([]any)[0].(map[string]any)["name"].(string),
		"WANDERING.md", "an unclaimed root document must still be listed")
}

func TestLawIsMarkedSealed(t *testing.T) {
	tn := world(t, map[string]string{
		"law/SITTING_LAWS.md": "the laws",
		"CLAUDE.md":           "the rules",
	})
	d := jsonOf(t, toolRecords, tn, map[string]any{"kind": "doctrine"})
	sealed := map[string]bool{}
	for _, x := range d["documents"].([]any) {
		m := x.(map[string]any)
		s, _ := m["sealed"].(bool)
		sealed[m["name"].(string)] = s
	}
	if !sealed["law/SITTING_LAWS.md"] {
		t.Fatal("a law is not marked sealed")
	}
	if sealed["CLAUDE.md"] {
		t.Fatal("a root document is marked sealed and is not")
	}
}

// IT IS A LIST, NOT A PATH. Nothing is joined onto Home from the caller's
// string, so there is no traversal to defend against -- the escape simply is
// not IN the listing, and so cannot resolve.
func TestARecordNameIsMatchedAgainstTheListingNotTheDisk(t *testing.T) {
	tn := world(t, map[string]string{"CLAUDE.md": "the rules"})
	if err := os.WriteFile(filepath.Join(tn.Home, ".env"),
		[]byte("MANJUEL_GIT_REMOTE=1\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{
		"../.env", ".env", "/etc/passwd", "C:\\keys.txt",
		"law/../.env", "../../CLAUDE.md",
	} {
		out, err := toolRecords(tn, map[string]any{"name": name})
		if err == nil {
			t.Fatalf("%q was served: %s", name, out[:120])
		}
		has(t, err.Error(), "no record named", "the refusal must say it is not in the list")
	}
}

func TestOnlyMarkdownIsADocument(t *testing.T) {
	tn := world(t, map[string]string{
		"CLAUDE.md":        "the rules",
		"secrets.txt":      "not a document",
		"index/vectors.db": "not a document",
		"notes.json":       "not a document",
	})
	d := jsonOf(t, toolRecords, tn, nil)
	body, _ := json.Marshal(d)
	for _, gone := range []string{"secrets.txt", "vectors.db", "notes.json"} {
		if strings.Contains(string(body), gone) {
			t.Fatalf("%s was listed as a document", gone)
		}
	}
	if int(d["count"].(float64)) != 1 {
		t.Fatalf("wanted 1 document, got %v", d["count"])
	}
}

// The receipt is the point: a page showing a document can be checked against
// the disk without trusting the page.
func TestADocumentComesBackWithTheShaOfTheBytesServed(t *testing.T) {
	body := "# The rules\nevery turn.\n"
	tn := world(t, map[string]string{"CLAUDE.md": body})
	d := jsonOf(t, toolRecords, tn, map[string]any{"name": "CLAUDE.md"})
	sum := sha256.Sum256([]byte(body))
	if d["sha256"] != hex.EncodeToString(sum[:]) {
		t.Fatalf("sha256 does not match the bytes served:\n  got  %v\n  want %s",
			d["sha256"], hex.EncodeToString(sum[:]))
	}
	if d["text"] != body {
		t.Fatal("the text served is not the file")
	}
	if int(d["bytes"].(float64)) != len(body) {
		t.Fatalf("byte count %v != %d", d["bytes"], len(body))
	}
}

func TestAnAbsentNameIsDeniedBySayingWhatThereIs(t *testing.T) {
	tn := world(t, map[string]string{"CLAUDE.md": "x", "CHANGELOG.md": "y"})
	_, err := toolRecords(tn, map[string]any{"name": "NOPE.md"})
	if err == nil {
		t.Fatal("an absent name was not refused")
	}
	has(t, err.Error(), "doctrine (1)", "the refusal must name the kinds carried")
	has(t, err.Error(), "record (1)", "the refusal must name the kinds carried")
}

// The count reported is the TRUE count, not the shown one: a listing that
// silently truncated would be a page lying about the record.
func TestTheTranscriptsAreCappedNewestFirst(t *testing.T) {
	files := map[string]string{"CLAUDE.md": "x"}
	for i := 0; i < LOGS_SHOWN+7; i++ {
		files[filepath.ToSlash(filepath.Join("logs",
			"run_"+string(rune('a'+i/26))+string(rune('a'+i%26))+".md"))] = "t"
	}
	tn := world(t, files)
	d := jsonOf(t, toolRecords, tn, map[string]any{"kind": "logs"})
	if n := len(d["documents"].([]any)); n != LOGS_SHOWN {
		t.Fatalf("logs returned %d, wanted the %d cap", n, LOGS_SHOWN)
	}
	docs := d["documents"].([]any)
	for i := 1; i < len(docs); i++ {
		a := docs[i-1].(map[string]any)["modified"].(string)
		b := docs[i].(map[string]any)["modified"].(string)
		if a < b {
			t.Fatal("the transcripts are not newest first")
		}
	}
}

// --- proofs: what a world has actually proved -------------------------------

// A world that never ran a suite has not FAILED at anything, and one missing
// file must never blank the other two.
func TestAProofPageWithAGapBeatsNoProofPage(t *testing.T) {
	tn := world(t, map[string]string{
		"tests/last_run.json": `{"strokes":{"passed":2106,"total":2106,"green":true}}`,
	})
	d := jsonOf(t, toolProofs, tn, nil)
	if d["suites"] == nil {
		t.Fatal("the suite that IS on disk was not read")
	}
	for _, absent := range []string{"standups_error", "parity_error"} {
		s, _ := d[absent].(string)
		if s != "never run in this world" {
			t.Fatalf("%s says %q, wanted the honest sentence", absent, s)
		}
	}
}

// sessions.jsonl is append-only and a CLOSING line supersedes its opening one.
// Keyed by n, last line wins -- get this wrong and every sitting counts twice.
func TestAClosingLineSupersedesItsOpening(t *testing.T) {
	tn := world(t, map[string]string{
		"sessions/sessions.jsonl": strings.Join([]string{
			`{"n":1,"started":"a","runs":[]}`,
			`{"n":2,"started":"b","runs":[{}]}`,
			`{"n":1,"started":"a","ended":"z","toll_paid":true,"runs":[{},{}]}`,
			`  `,
			`{"n":3,"started":"c","runs":[]}`,
		}, "\n"),
	})
	rec := jsonOf(t, toolProofs, tn, nil)["record"].(map[string]any)
	if int(rec["sittings"].(float64)) != 3 {
		t.Fatalf("sittings counted %v, wanted 3 -- a superseded line was double counted", rec["sittings"])
	}
	if int(rec["tolled"].(float64)) != 1 {
		t.Fatalf("tolled %v, wanted 1", rec["tolled"])
	}
	// 2 from the closing line of sitting 1, 1 from sitting 2, 0 from sitting 3.
	if int(rec["runs"].(float64)) != 3 {
		t.Fatalf("runs %v, wanted 3", rec["runs"])
	}
	// Sittings 2 and 3 never ended.
	if int(rec["still_open"].(float64)) != 2 {
		t.Fatalf("still_open %v, wanted 2", rec["still_open"])
	}
}

// A half-written last line is what a KILLED PROCESS leaves. The lines before it
// are still true, so it is dropped rather than failing the whole read.
func TestAHalfWrittenLineDoesNotLoseTheLinesBeforeIt(t *testing.T) {
	tn := world(t, map[string]string{
		"sessions/sessions.jsonl": "{\"n\":1,\"started\":\"a\",\"ended\":\"z\",\"runs\":[]}\n{\"n\":2,\"star",
	})
	rec := jsonOf(t, toolProofs, tn, nil)["record"].(map[string]any)
	if rec["error"] != nil {
		t.Fatalf("a torn last line failed the whole read: %v", rec["error"])
	}
	if int(rec["sittings"].(float64)) != 1 {
		t.Fatalf("sittings %v, wanted the 1 whole line", rec["sittings"])
	}
}

// Some numbers are the CORE's to define. A second definition here would drift
// from his the first time it changed, so they are named as not counted.
func TestTheNumbersTheCoreOwnsAreNamedNotRecounted(t *testing.T) {
	tn := world(t, map[string]string{"CLAUDE.md": "x"})
	rec := jsonOf(t, toolProofs, tn, nil)["record"].(map[string]any)
	named := []string{}
	for _, x := range rec["counted_by_the_engine"].([]any) {
		named = append(named, x.(string))
	}
	joined := strings.Join(named, " | ")
	has(t, joined, "memory entries", "the core's own counts must be named")
	has(t, joined, "index docs", "the core's own counts must be named")
}

// --- seats: the declarations, read as a SHAPE -------------------------------

// The core parses a declaration with two regexes and NEITHER NAMES A FIELD.
// So this returns whatever keys a declaration carries -- including one added
// tomorrow. Encoding a field list here is what would drift.
func TestASeatsFieldsAreWhateverItDeclares(t *testing.T) {
	tn := world(t, map[string]string{
		"agents/steward.md": "## Steward\n" +
			"- **Model Target:** llama3.2\n" +
			"- **Stage:** deliver\n" +
			"- **Invented Tomorrow:** and still read\n",
		"pipelines.md": "## Pipeline: default\n1. Steward\n2. Router (when: needs_tool)\n",
	})
	d := jsonOf(t, toolSeats, tn, nil)
	seat := d["seats"].([]any)[0].(map[string]any)
	if seat["name"] != "Steward" {
		t.Fatalf("name read as %v", seat["name"])
	}
	fields := seat["fields"].(map[string]any)
	// THE COLON LIVES INSIDE THE BOLD MARKERS in this estate's files, so a key
	// that kept it would label every field with a trailing colon.
	for k, want := range map[string]string{
		"Model Target": "llama3.2", "Stage": "deliver",
		"Invented Tomorrow": "and still read",
	} {
		if fields[k] != want {
			t.Fatalf("field %q read as %v, wanted %q (%v)", k, fields[k], want, fields)
		}
	}
	stands := seat["stands_in"].([]any)
	if len(stands) != 1 || stands[0].(map[string]any)["pipeline"] != "default" {
		t.Fatalf("the seat does not know where it stands: %v", stands)
	}
	if int(stands[0].(map[string]any)["step"].(float64)) != 1 {
		t.Fatal("the step is wrong")
	}
}

// A field with an empty value and a body beneath it IS the body's heading --
// the core's own shape. The prompt must come back whole, and not as a field.
func TestASystemPromptIsTheBodyBeneathIt(t *testing.T) {
	body := "You are the Steward. Speak plainly.\nNever invent a tool result."
	tn := world(t, map[string]string{
		"agents/steward.md": "## Steward\n- **Model Target:** llama3.2\n" +
			"- **System Prompt:**\n" + body + "\n",
	})
	d := jsonOf(t, toolSeats, tn, nil)
	seat := d["seats"].([]any)[0].(map[string]any)
	if got, _ := seat["prompt"].(string); got != body {
		t.Fatalf("prompt read as %q", got)
	}
	if _, still := seat["fields"].(map[string]any)["System Prompt"]; still {
		t.Fatal("the prompt is also sitting in fields, counted twice")
	}
	if int(seat["prompt_chars"].(float64)) != len(body) {
		t.Fatal("prompt_chars does not match the prompt")
	}
}

// A world with no agents/ has not failed at anything either.
func TestAWorldWithNoSeatsSaysSoRatherThanCrashing(t *testing.T) {
	tn := world(t, map[string]string{"CLAUDE.md": "x"})
	d := jsonOf(t, toolSeats, tn, nil)
	if d["seats_error"] == nil {
		t.Fatal("an absent agents/ was not reported")
	}
	if d["world"] != "probe" {
		t.Fatal("the answer does not name its world")
	}
}

// The registry is the contract the door is: a tool that writes must SAY it
// writes, because that flag is what the read-only table is refused by.
func TestTheRegistryAgreesWithWhatEachToolDoes(t *testing.T) {
	// Built the way the door builds it, against an empty tenant registry: the
	// wiring is what is under test, not any world's contents.
	r := Build(tenant.NewRegistry(), Options{})
	writes := map[string]bool{}
	for _, name := range r.Names() {
		writes[name] = r.byName[name].Writes
	}
	for _, name := range []string{"git", "git_diff", "git_remote", "records", "proofs", "seats"} {
		if v, ok := writes[name]; !ok {
			t.Fatalf("%s is not registered", name)
		} else if v {
			t.Fatalf("%s is declared as writing and does not", name)
		}
	}
	for _, name := range []string{"git_commit", "git_push", "git_pull", "git_branch"} {
		if v, ok := writes[name]; !ok {
			t.Fatalf("%s is not registered", name)
		} else if !v {
			t.Fatalf("%s writes and does not declare it", name)
		}
	}
}
