// Bundle prove: depth-1 and depth-2 bundles byte-exact from fixtures;
// depth 3 structural (it embeds the live pack).
package rack

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func openFixtures(t *testing.T) (voices []Voice, caps map[string][]string, ladder string, ledger []string) {
	t.Helper()
	tags, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures", "rack_tags.json"))
	if err != nil {
		t.Fatal(err)
	}
	voices, err = ParseTags(tags)
	if err != nil {
		t.Fatal(err)
	}
	ask, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures", "rack_ask.json"))
	if err != nil {
		t.Fatal(err)
	}
	var doc struct {
		Shows map[string]struct {
			Capabilities []string `json:"capabilities"`
		} `json:"shows"`
	}
	if err := json.Unmarshal(ask, &doc); err != nil {
		t.Fatal(err)
	}
	caps = map[string][]string{}
	for n, s := range doc.Shows {
		caps[n] = s.Capabilities
	}
	ladder = Ladder(voices)
	raw, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures",
		"rack_open_ground", "state", "rack_ledger.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	for _, ln := range strings.Split(string(raw), "\n") {
		if strings.TrimSpace(ln) != "" {
			ledger = append(ledger, ln)
		}
	}
	return voices, caps, ladder, ledger
}

func voiceByName(t *testing.T, voices []Voice, name string) Voice {
	t.Helper()
	for _, v := range voices {
		if v.Name == name {
			return v
		}
	}
	t.Fatalf("voice %q not folded", name)
	return Voice{}
}

func TestBundleDepthsByteExact(t *testing.T) {
	voices, caps, ladder, ledger := openFixtures(t)
	v := voiceByName(t, voices, "llama3.2:latest")
	for depth, file := range map[int]string{1: "rack_bundle_d1.txt", 2: "rack_bundle_d2.txt"} {
		got, err := Bundle("atlas", v.Name, TierOf(v.Size), v.Size, v.Family,
			caps[v.Name], ladder, ledger, "", depth)
		if err != nil {
			t.Fatal(err)
		}
		want, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures", file))
		if err != nil {
			t.Fatal(err)
		}
		if got != string(want) {
			t.Fatalf("depth-%d mismatch:\n go %q\n py %q", depth, got, want)
		}
	}
}

func TestBundleDepthThreeStructural(t *testing.T) {
	voices, caps, ladder, ledger := openFixtures(t)
	v := voiceByName(t, voices, "llama3.2:latest")
	got, err := Bundle("atlas", v.Name, TierOf(v.Size), v.Size, v.Family,
		caps[v.Name], ladder, ledger, "-- LINE (atlas) --\nstanding law\n", 3)
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"CONTEXT BUNDLE — llama3.2:latest at depth 3 (atlas)",
		"VOICE llama3.2:latest", "LADDER", "MEMORY (last 5)", "GROUND",
		"-- LINE (atlas) --", "(+100 more)",
	} {
		if !strings.Contains(got, want) {
			t.Fatalf("depth-3 missing %q", want)
		}
	}
	if _, err := Bundle("atlas", v.Name, TierOf(v.Size), v.Size, v.Family,
		caps[v.Name], ladder, ledger, "", 0); err == nil {
		t.Fatal("depth 0 admitted")
	}
	if _, err := Bundle("atlas", v.Name, TierOf(v.Size), v.Size, v.Family,
		caps[v.Name], ladder, ledger, "", 4); err == nil {
		t.Fatal("depth 4 admitted")
	}
}

func TestShortenRule(t *testing.T) {
	if Shorten("abc") != "abc" {
		t.Fatal("short answer altered")
	}
	got := Shorten(strings.Repeat("L", 300))
	if !strings.HasPrefix(got, strings.Repeat("L", 200)) || !strings.HasSuffix(got, "… (+100 more)") {
		t.Fatalf("truncate rule broke: %q", got[len(got)-20:])
	}
}
