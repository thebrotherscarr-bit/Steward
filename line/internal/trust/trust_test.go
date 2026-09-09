package trust

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestUpsertPersistsAndRenders(t *testing.T) {
	home := t.TempDir()
	if got := Render(home); !strings.Contains(got, "no delegations") {
		t.Fatalf("empty store must name absence: %q", got)
	}
	if _, err := Upsert(home, Grant{From: "atlas", To: "manjuel", Tool: "rack_list", Action: "allow"}); err != nil {
		t.Fatal(err)
	}
	if _, err := Upsert(home, Grant{From: "atlas", To: "manjuel", Tool: "rack_list", Action: "deny"}); err != nil {
		t.Fatal(err)
	}
	s := Load(home)
	if len(s.Grants) != 1 || s.Grants[0].Action != "deny" {
		t.Fatalf("upsert must replace same triple: %+v", s.Grants)
	}
	raw, err := os.ReadFile(filepath.Join(home, "state", "trust.json"))
	if err != nil || len(raw) == 0 {
		t.Fatalf("trust.json witnessed: %v", err)
	}
	if got := Render(home); !strings.Contains(got, "DENY rack_list") {
		t.Fatalf("render must list the grant: %q", got)
	}
}
