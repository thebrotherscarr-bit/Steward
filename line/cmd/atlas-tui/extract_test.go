package main

import (
	"testing"
)

func TestExtractField(t *testing.T) {
	data := map[string]any{
		"agents": []any{
			map[string]any{"name": "manjuel.us", "status": "enrolled"},
			map[string]any{"name": "council.us", "status": "enrolled"},
		},
		"count": 2,
	}

	tests := []struct {
		path string
		want string
	}{
		{"agents.*.name", "manjuel.us\ncouncil.us"},
		{"*.name", "manjuel.us\ncouncil.us"},
		{"count", "2"},
	}

	for _, tt := range tests {
		got := extractField(data, tt.path)
		if got != tt.want {
			t.Errorf("extractField(%q) = %q, want %q", tt.path, got, tt.want)
		}
	}
}

func TestExtractFieldNested(t *testing.T) {
	data := map[string]any{
		"tools": []any{
			map[string]any{"name": "chain_list", "input": map[string]any{"path": "string"}},
			map[string]any{"name": "agent_enroll", "input": map[string]any{"db": "string"}},
		},
	}

	got := extractField(data, "tools.*.name")
	want := "chain_list\nagent_enroll"
	if got != want {
		t.Errorf("extractField(\"tools.*.name\") = %q, want %q", got, want)
	}

	// Auto-find array in wrapper map
	got = extractField(data, "*.name")
	if got != want {
		t.Errorf("extractField(\"*.name\") on wrapper = %q, want %q", got, want)
	}
}

func TestExtractFieldSingle(t *testing.T) {
	data := map[string]any{"name": "hello"}
	got := extractField(data, "name")
	if got != "hello" {
		t.Errorf("extractField(\"name\") = %q, want %q", got, "hello")
	}
}
