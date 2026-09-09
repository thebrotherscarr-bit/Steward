// Mesh store prove: envelope byte-compat, sealed round-trip, the three
// refusals, tamper verdicts, and the estate's own signatures verifying under
// Go hands. Hermetic: temp dirs, t.Setenv keys, fixed vectors.
package mesh

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func jsonDecoder(raw string) *json.Decoder {
	d := json.NewDecoder(strings.NewReader(raw))
	d.UseNumber()
	return d
}

func jsonNumber(s string) any { return json.Number(s) }

func sha256Hex(b []byte) string {
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:])
}

// Oracle-cut canon strings (tools probe over json.dumps sort_keys/ascii-off).
// Go must emit these bytes exactly.
var canonGoldens = []struct{ name, body, want string }{
	{"mesh-body",
		`{"actor":"alice"}`,
		`{"actor": "alice"}`,
	},
	{"full-body",
		`{"actor":"alice","kind":"mesh","payload":{"n":1,"chan":"atlas","to":"@everyone","ct":"hello","mode":"open","cites":[],"mark":"ed9f182fdf22bc11"},"prev":"` + Genesis + `","ts":"2026-09-03T00:00:00Z"}`,
		`{"actor": "alice", "kind": "mesh", "payload": {"chan": "atlas", "cites": [], "ct": "hello", "mark": "ed9f182fdf22bc11", "mode": "open", "n": 1, "to": "@everyone"}, "prev": "` + Genesis + `", "ts": "2026-09-03T00:00:00Z"}`,
	},
}

func canonOf(t *testing.T, raw string) any {
	t.Helper()
	dec := jsonDecoder(raw)
	var v any
	if err := dec.Decode(&v); err != nil {
		t.Fatalf("bad golden body: %s", err)
	}
	return v
}

func TestCanonMatchesOracle(t *testing.T) {
	for _, g := range canonGoldens {
		got, err := Canon(canonOf(t, g.body))
		if err != nil {
			t.Fatalf("%s: %s", g.name, err)
		}
		if got != g.want {
			t.Fatalf("%s:\n go %q\n py %q", g.name, got, g.want)
		}
	}
	// Floats never hash.
	if _, err := Canon(jsonNumber("1.5")); err == nil {
		t.Fatal("float canon accepted")
	}
	if s, err := Canon(jsonNumber("42")); err != nil || s != "42" {
		t.Fatalf("integer number refused: %v %q", err, s)
	}
}

// Escapes, bignums, and control bytes against the oracle probe: short escapes,
// \u00xx for other C0 controls, DEL raw, bignum verbatim. Control bytes are
// built programmatically so no fragile literal sits in source.
func TestCanonEscapes(t *testing.T) {
	ctrl1 := string([]byte{0x01})
	del := string([]byte{0x7f})
	val := map[string]any{
		"a": "q\"b\\c\nd\te\rf\fg" + ctrl1 + "h" + del + "Z",
		"b": true, "c": nil,
		"d": []any{jsonNumber("1"), jsonNumber("-2"),
			map[string]any{"k": []any{}}},
		"e": map[string]any{},
		"f": jsonNumber("123456789012345678901234567890"),
	}
	// The oracle's exact bytes: backslash-u-0-0-0-1 as six text chars, DEL raw.
	want := "{\"a\": \"q\\\"b\\\\c\\nd\\te\\rf\\fg\\u0001h" + del +
		"Z\", \"b\": true, \"c\": null, \"d\": [1, -2, {\"k\": []}], " +
		"\"e\": {}, \"f\": 123456789012345678901234567890}"
	got, err := Canon(val)
	if err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("\n go %q\n py %q", got, want)
	}
}

// Two fixed test voices. Secrets are test-only, env-scoped, never in repo.
func testKeys(t *testing.T) {
	t.Helper()
	t.Setenv("MESH_KEY_ALICE", strings.Repeat("01", 32))
	t.Setenv("MESH_KEY_BOB", strings.Repeat("02", 32))
}

func pubFor(t *testing.T, secretHex string) string {
	t.Helper()
	b, _ := hex.DecodeString(secretHex)
	pub, err := PubForSecret(b)
	if err != nil {
		t.Fatal(err)
	}
	return pub
}

func testGround(t *testing.T, alicePub, bobPub string) string {
	t.Helper()
	dir := t.TempDir()
	if _, err := Enroll(dir, "alice", alicePub); err != nil {
		t.Fatal(err)
	}
	if _, err := Enroll(dir, "bob", bobPub); err != nil {
		t.Fatal(err)
	}
	return dir
}

func TestPostReadRoundTrip(t *testing.T) {
	testKeys(t)
	dir := testGround(t, pubFor(t, strings.Repeat("01", 32)), pubFor(t, strings.Repeat("02", 32)))
	e, head, err := Post(dir, "atlas", "alice", "bob", ModeOpen, "hello bob", "mesh", nil)
	if err != nil {
		t.Fatal(err)
	}
	if e.Payload.N != 1 || e.Prev != Genesis || head == nil {
		t.Fatalf("bad first entry: %+v", e)
	}
	// Sealed round-trip with commitment.
	se, _, err := Post(dir, "atlas", "bob", "alice", ModeSealed, "meet at 3", "mesh", []string{e.Hash})
	if err != nil {
		t.Fatal(err)
	}
	if se.Payload.Ct == "meet at 3" {
		t.Fatal("sealed ct is plaintext")
	}
	got, err := Read(dir, "bob", 0, true)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Plaintext != "meet at 3" {
		t.Fatalf("reveal failed: %+v", got)
	}
	// Alice's open post reads plain on her own pen.
	open, err := Read(dir, "alice", 0, false)
	if err != nil || len(open) != 1 || open[0].Plaintext != "hello bob" {
		t.Fatalf("open read failed: %+v", open)
	}
	// Unrevealed read withholds honestly, failing nothing.
	dark, err := Read(dir, "bob", 0, false)
	if err != nil || len(dark) != 1 || dark[0].Plaintext != "" || dark[0].Withheld == "" {
		t.Fatalf("sealed read must withhold: %+v", dark)
	}
	// Ledger pins the salted commitment, not H(plaintext).
	ledger := mustLines(ledgerPath(dir))
	if len(ledger) != 1 {
		t.Fatalf("ledger holds %d salts, want 1", len(ledger))
	}
	var rec map[string]string
	if err := json.Unmarshal([]byte(ledger[0]), &rec); err != nil {
		t.Fatal(err)
	}
	if rec["entry"] != se.Hash || len(rec["salt"]) != 64 {
		t.Fatalf("bad ledger record: %s", ledger[0])
	}
	bare := sha256Hex([]byte("meet at 3"))
	if rec["commitment"] == bare {
		t.Fatal("commitment is the bare hash — low-entropy messages would brute-force")
	}
	// Chain sound: two pens + head, all INTACT.
	v, err := Chain(dir)
	if err != nil {
		t.Fatal(err)
	}
	if !v.Sound || v.Overall != "INTACT" {
		t.Fatalf("chain not sound: %+v", v)
	}
}

func TestRefusals(t *testing.T) {
	testKeys(t)
	dir := testGround(t, pubFor(t, strings.Repeat("01", 32)), pubFor(t, strings.Repeat("02", 32)))
	cases := []struct {
		name string
		call func() error
		want string
	}{
		{"auth", func() error {
			_, _, err := Post(dir, "atlas", "stranger", "alice", ModeOpen, "hi", "mesh", nil)
			return err
		}, "not enrolled"},
		{"egress", func() error {
			_, _, err := Post(dir, "atlas", "alice", "https://example.com/x", ModeOpen, "hi", "mesh", nil)
			return err
		}, "not this estate"},
		{"badcite", func() error {
			_, _, err := Post(dir, "atlas", "alice", "bob", ModeOpen, "hi", "mesh", []string{"nope"})
			return err
		}, "not a hash"},
		{"ghostcite", func() error {
			_, _, err := Post(dir, "atlas", "alice", "bob", ModeOpen, "hi", "mesh", []string{strings.Repeat("ab", 32)})
			return err
		}, "names nothing"},
		{"badkind", func() error {
			_, _, err := Post(dir, "atlas", "alice", "bob", ModeOpen, "hi", "approve", nil)
			return err
		}, "not a mesh kind"},
		{"emptytext", func() error {
			_, _, err := Post(dir, "atlas", "alice", "bob", ModeOpen, "  ", "mesh", nil)
			return err
		}, "says what it is"},
		{"badactor", func() error {
			_, err := Enroll(dir, "Not A Name", pubFor(t, strings.Repeat("01", 32)))
			return err
		}, "not a mesh name"},
		{"offcurve", func() error {
			_, err := Enroll(dir, "mallory", strings.Repeat("01", 64))
			return err
		}, "not a curve point"},
	}
	for _, c := range cases {
		err := c.call()
		if err == nil || !strings.Contains(err.Error(), c.want) {
			t.Fatalf("%s: want refusal containing %q, got %v", c.name, c.want, err)
		}
	}
	// Conflicting re-key refused; identical re-enroll idempotent.
	if _, err := Enroll(dir, "alice", pubFor(t, strings.Repeat("02", 32))); err == nil {
		t.Fatal("conflicting pub accepted")
	}
	mb, err := Enroll(dir, "alice", pubFor(t, strings.Repeat("01", 32)))
	if err != nil || mb.Mark == "" {
		t.Fatalf("idempotent re-enroll failed: %v", err)
	}
}

func TestTamperVerdicts(t *testing.T) {
	testKeys(t)
	dir := testGround(t, pubFor(t, strings.Repeat("01", 32)), pubFor(t, strings.Repeat("02", 32)))
	if _, _, err := Post(dir, "atlas", "alice", "@everyone", ModeOpen, "one", "mesh", nil); err != nil {
		t.Fatal(err)
	}
	if _, _, err := Post(dir, "atlas", "alice", "@everyone", ModeOpen, "two", "mesh", nil); err != nil {
		t.Fatal(err)
	}
	chain := filepath.Join(dir, "chains", "alice.jsonl")
	// Flip a byte inside entry 2: weld holds, hash breaks -> FLIP.
	b, _ := os.ReadFile(chain)
	lines := strings.Split(strings.TrimRight(string(b), "\n"), "\n")
	lines[1] = strings.Replace(lines[1], "two", "TWO", 1)
	if err := os.WriteFile(chain, []byte(strings.Join(lines, "\n")+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	v, _ := Chain(dir)
	if v.Overall != "FLIP" {
		t.Fatalf("want FLIP, got %+v", v)
	}
	// Drop entry 1: the weld breaks -> TAMPER.
	if err := os.WriteFile(chain, []byte(lines[1]+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	v, _ = Chain(dir)
	if v.Overall != "TAMPER" {
		t.Fatalf("want TAMPER, got %+v", v)
	}
}

// The cutter-built golden ground (Python canon + jesster signatures)
// verifies whole under Go hands: hash, weld, signature, and mark on every
// entry. This is the cross-impl direction estate->atlas for mesh chains.
func TestFacesGoldenGround(t *testing.T) {
	dir := filepath.Join("..", "..", "..", "tests", "fixtures", "faces_ground")
	v, err := Chain(dir)
	if err != nil {
		t.Fatal(err)
	}
	if !v.Sound || v.Overall != "INTACT" {
		t.Fatalf("golden ground not sound: %+v", v)
	}
	if len(v.Chains) != 3 { // actor/alice, actor/bob, head
		t.Fatalf("want 3 chains, got %+v", v.Chains)
	}
	got, err := Read(dir, "alice", 0, false)
	if err != nil || len(got) != 2 || got[0].Plaintext != "the face shows the record" {
		t.Fatalf("golden read failed: %+v", got)
	}
}
func TestEstateSignaturesVerify(t *testing.T) {
	p := filepath.Join("..", "..", "..", "tests", "fixtures", "chains", "forge_links_chain.jsonl")
	b, err := os.ReadFile(p)
	if err != nil {
		t.Skip("forge fixture absent")
	}
	n := 0
	for _, ln := range strings.Split(string(b), "\n") {
		if strings.TrimSpace(ln) == "" {
			continue
		}
		e, err := ParseLine(ln)
		if err != nil {
			t.Fatal(err)
		}
		if e.Sig == "" {
			continue
		}
		sig, _ := hex.DecodeString(e.Sig)
		pub, _ := hex.DecodeString(e.Pub)
		if !Verify(pub, []byte(e.Hash), sig) {
			t.Fatalf("estate entry n=%d rejected", e.Payload.N)
		}
		n++
	}
	if n != 3 {
		t.Fatalf("want 3 estate signatures, verified %d", n)
	}
}
