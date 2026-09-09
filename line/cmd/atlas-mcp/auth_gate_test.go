package main

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"atlas/line/internal/auth"
	"atlas/line/internal/httpserver"
	"atlas/line/internal/protocol"
	"atlas/line/internal/tenant"
	"atlas/line/internal/tools"
)

func gateHome(t *testing.T, root, name string) string {
	t.Helper()
	dir := filepath.Join(root, name)
	os.MkdirAll(dir, 0o755)
	os.WriteFile(filepath.Join(dir, "AGENTS.md"), []byte("# "+name), 0o644)
	os.WriteFile(filepath.Join(dir, "THE_ROAD.md"), []byte("road"), 0o644)
	os.WriteFile(filepath.Join(dir, "SEAT_LOG.md"), []byte("log"), 0o644)
	return dir
}

func gateServer(t *testing.T, reg *tenant.Registry, a httpserver.Auth) *httpserver.Server {
	t.Helper()
	return httpserver.New(
		protocol.ServerInfo{Name: "atlas-mcp", Version: "test"},
		"instructions", tools.Build(reg, tools.Options{}), reg, a)
}

func rpcCall(t *testing.T, srv *httpserver.Server, bearer, body string) map[string]any {
	t.Helper()
	req := httptest.NewRequest("POST", "/rpc", strings.NewReader(body+"\n"))
	if bearer != "" {
		req.Header.Set("Authorization", "Bearer "+bearer)
	}
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)
	var doc map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &doc); err != nil {
		t.Fatalf("unparsable rpc answer: %q", rec.Body.String())
	}
	return doc
}

func rpcText(doc map[string]any) (string, bool) {
	res, _ := doc["result"].(map[string]any)
	if res == nil {
		if e, ok := doc["error"].(map[string]any); ok {
			msg, _ := e["message"].(string)
			return msg, true
		}
		return "", true
	}
	if res["isError"] == true {
		content, _ := res["content"].([]any)
		if len(content) > 0 {
			if m, ok := content[0].(map[string]any); ok {
				text, _ := m["text"].(string)
				return text, true
			}
		}
		return "", true
	}
	content, _ := res["content"].([]any)
	if len(content) > 0 {
		if m, ok := content[0].(map[string]any); ok {
			text, _ := m["text"].(string)
			return text, false
		}
	}
	return "", false
}

func TestBearerGate(t *testing.T) {
	root := t.TempDir()
	reg := tenant.NewRegistry()
	reg.Add("alpha", gateHome(t, root, "alpha"))
	reg.Add("beta", gateHome(t, root, "beta"))
	srv := gateServer(t, reg, httpserver.Auth{On: true, Service: "svc-wire"})

	call := func(tool, project string) map[string]any {
		return map[string]any{
			"jsonrpc": "2.0", "id": 1, "method": "tools/call",
			"params": map[string]any{
				"name":      tool,
				"arguments": map[string]any{"project": project},
			},
		}
	}
	marshal := func(v any) string {
		b, _ := json.Marshal(v)
		return string(b)
	}

	// Strangers: 401 without a bearer.
	doc := rpcCall(t, srv, "", marshal(call("muster", "alpha")))
	if _, isErr := rpcText(doc); !isErr {
		t.Fatal("bearerless call must refuse")
	}
	if e, ok := doc["error"].(map[string]any); !ok || !strings.Contains(e["message"].(string), "401") {
		t.Fatalf("want 401, got %v", doc)
	}

	// The login door stays open: bad key fails at the tool, not the gate.
	doc = rpcCall(t, srv, "", marshal(map[string]any{
		"jsonrpc": "2.0", "id": 1, "method": "tools/call",
		"params": map[string]any{"name": "auth_verify",
			"arguments": map[string]any{"project": "alpha", "key": "atl_00"}}},
	))
	text, isErr := rpcText(doc)
	if !isErr || !strings.Contains(text, "refused") {
		t.Fatalf("login door must answer (refusing the key, not the caller): %v", doc)
	}

	// Mint a key directly in alpha's store, then ride it.
	key, _, err := auth.Create(filepath.Join(root, "alpha"), "t", []string{"alpha"}, "test")
	if err != nil {
		t.Fatal(err)
	}
	doc = rpcCall(t, srv, key, marshal(call("muster", "alpha")))
	if text, isErr := rpcText(doc); isErr {
		t.Fatalf("scoped key must pass its own ground: %s", text)
	}
	// Same key on beta's ground: 403.
	doc = rpcCall(t, srv, key, marshal(call("muster", "beta")))
	if e, ok := doc["error"].(map[string]any); !ok || !strings.Contains(e["message"].(string), "403") {
		t.Fatalf("want 403 cross-tenant, got %v", doc)
	}
	// Service wire: everywhere.
	doc = rpcCall(t, srv, "svc-wire", marshal(call("muster", "beta")))
	if text, isErr := rpcText(doc); isErr {
		t.Fatalf("service wire must pass: %s", text)
	}

	// Metrics speak Prometheus.
	req := httptest.NewRequest("GET", "/metrics", nil)
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)
	if !strings.Contains(rec.Body.String(), "atlas_rpc_calls") {
		t.Fatalf("metrics must render counters:\n%s", rec.Body.String())
	}
}

func TestGateOffStaysOpen(t *testing.T) {
	root := t.TempDir()
	reg := tenant.NewRegistry()
	reg.Add("alpha", gateHome(t, root, "alpha"))
	srv := gateServer(t, reg, httpserver.Auth{})
	b, _ := json.Marshal(map[string]any{
		"jsonrpc": "2.0", "id": 1, "method": "tools/call",
		"params": map[string]any{"name": "muster", "arguments": map[string]any{}}},
	)
	doc := rpcCall(t, srv, "", string(b))
	if text, isErr := rpcText(doc); isErr {
		t.Fatalf("gate-off stays open: %s", text)
	}
}
