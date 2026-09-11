// The first strokes on the MCP protocol layer.
//
// WHY THIS FILE DID NOT EXIST UNTIL 2026-09-11. internal/httpserver is 800
// lines and had ZERO tests -- and it is the thing that makes atlas-mcp an MCP
// server rather than a pile of functions. Every wire-visible promise the door
// makes (the protocol version, the shape of a tool, the JSON-RPC error codes,
// what a caller is told when a tool fails) lived here unguarded, while the
// tool bodies BEHIND it carried 755 lines of strokes. ADR-006 measured it:
// the two things that define the door as a product -- the protocol layer and
// the tenant model -- were the two least-tested things in it.
//
// These strokes are hermetic. They stand up a real registry against a real
// temp tenant, and assert only what the WIRE says. Nothing here needs a
// model, a network, the Rust spine or a built engine, with one named
// exception that skips itself and says why.
package httpserver

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"atlas/line/internal/protocol"
	"atlas/line/internal/tenant"
	"atlas/line/internal/tools"
)

// newTestServer stands up the real tool surface over one temp tenant.
// The tenant is a bare directory: no agents/, no pipelines.md, no sessions/.
// That is deliberate -- the door's promise is that it answers for ANY ground,
// and a fixture that looked like manjuel would prove the opposite of that.
func newTestServer(t *testing.T) (*Server, string) {
	t.Helper()
	home := t.TempDir()
	tr := tenant.NewRegistry()
	if err := tr.Add("t", home); err != nil {
		t.Fatalf("could not carry the temp tenant: %v", err)
	}
	if err := tr.SetDefault("t"); err != nil {
		t.Fatalf("could not set the default tenant: %v", err)
	}
	reg := tools.Build(tr, tools.Options{})
	return New(protocol.ServerInfo{Name: "atlas-mcp", Version: "test"},
		"instructions", reg, tr, Auth{}), home
}

// rpc posts one JSON-RPC line and returns the decoded reply. An empty map
// means the server answered with nothing, which is correct for a notification
// and wrong for everything else.
func rpc(t *testing.T, s *Server, line string) map[string]any {
	t.Helper()
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/rpc", strings.NewReader(line+"\n"))
	s.Handler().ServeHTTP(rec, req)
	body := strings.TrimSpace(rec.Body.String())
	if body == "" {
		return map[string]any{}
	}
	var out map[string]any
	if err := json.Unmarshal([]byte(body), &out); err != nil {
		t.Fatalf("the door answered something that is not JSON: %q (%v)", body, err)
	}
	return out
}

func result(t *testing.T, resp map[string]any) map[string]any {
	t.Helper()
	r, ok := resp["result"].(map[string]any)
	if !ok {
		t.Fatalf("expected a result, got %v", resp)
	}
	return r
}

func errOf(t *testing.T, resp map[string]any) (int, string) {
	t.Helper()
	e, ok := resp["error"].(map[string]any)
	if !ok {
		t.Fatalf("expected an error, got %v", resp)
	}
	code, _ := e["code"].(float64)
	msg, _ := e["message"].(string)
	return int(code), msg
}

// ---- the handshake -------------------------------------------------------

// THE PROTOCOL VERSION IS A PROMISE TO EVERY CLIENT, so it is pinned by a
// stroke rather than by whoever last edited the line. A client that speaks
// 2025-06-18 and is answered with something else has no way to know it.
func TestInitializePinsTheProtocolVersion(t *testing.T) {
	s, _ := newTestServer(t)
	r := result(t, rpc(t, s, `{"jsonrpc":"2.0","id":1,"method":"initialize"}`))

	if got := r["protocolVersion"]; got != "2025-06-18" {
		t.Errorf("protocolVersion = %v, want 2025-06-18", got)
	}
	caps, ok := r["capabilities"].(map[string]any)
	if !ok {
		t.Fatalf("capabilities missing: %v", r)
	}
	if _, ok := caps["tools"]; !ok {
		t.Errorf("the door advertises tools and must say so in capabilities: %v", caps)
	}
	info, ok := r["serverInfo"].(map[string]any)
	if !ok {
		t.Fatalf("serverInfo missing: %v", r)
	}
	if info["name"] != "atlas-mcp" {
		t.Errorf("serverInfo.name = %v, want atlas-mcp", info["name"])
	}
	if info["version"] != "test" {
		t.Errorf("serverInfo.version = %v, want the version it was built with", info["version"])
	}
}

// A NOTIFICATION HAS NO ID AND GETS NO REPLY. Answering one is a protocol
// violation that a lenient client hides and a strict one chokes on.
func TestInitializedNotificationIsAnsweredWithSilence(t *testing.T) {
	s, _ := newTestServer(t)
	for _, m := range []string{"notifications/initialized", "initialized"} {
		if got := rpc(t, s, `{"jsonrpc":"2.0","method":"`+m+`"}`); len(got) != 0 {
			t.Errorf("%s was answered with %v; a notification gets nothing", m, got)
		}
	}
}

// ---- the tool surface ----------------------------------------------------

// EVERY TOOL THE DOOR ADVERTISES MUST DESCRIBE ITSELF. A name with no
// description and no schema is a tool no client can call without guessing,
// and guessing is what the schema exists to prevent.
func TestToolsListDescribesEveryToolItAdvertises(t *testing.T) {
	s, _ := newTestServer(t)
	r := result(t, rpc(t, s, `{"jsonrpc":"2.0","id":2,"method":"tools/list"}`))

	list, ok := r["tools"].([]any)
	if !ok || len(list) == 0 {
		t.Fatalf("tools/list returned nothing usable: %v", r)
	}
	seen := map[string]bool{}
	for _, raw := range list {
		tool, ok := raw.(map[string]any)
		if !ok {
			t.Fatalf("a tool entry is not an object: %v", raw)
		}
		name, _ := tool["name"].(string)
		if name == "" {
			t.Fatalf("a tool was advertised with no name: %v", tool)
		}
		if seen[name] {
			t.Errorf("%q is advertised twice; a client cannot tell them apart", name)
		}
		seen[name] = true

		if d, _ := tool["description"].(string); strings.TrimSpace(d) == "" {
			t.Errorf("%q has no description", name)
		}
		schema, ok := tool["inputSchema"].(map[string]any)
		if !ok {
			t.Errorf("%q has no inputSchema", name)
			continue
		}
		if schema["type"] != "object" {
			t.Errorf("%q inputSchema.type = %v, want object", name, schema["type"])
		}
		if _, ok := schema["properties"].(map[string]any); !ok {
			t.Errorf("%q inputSchema has no properties object", name)
		}
		// Every name in `required` must exist in `properties`, or the client
		// is being told to send something the schema does not define.
		props, _ := schema["properties"].(map[string]any)
		req, _ := schema["required"].([]any)
		for _, rn := range req {
			n, _ := rn.(string)
			if _, ok := props[n]; !ok {
				t.Errorf("%q requires %q but does not declare it in properties", name, n)
			}
		}
	}
}

// GET /tools AND tools/list RENDER THE SAME SCHEMA FROM THE SAME REGISTRY,
// in two places, by two copies of the same 28 lines (handleTools and the
// tools/list case). Nothing but this stroke stops one being edited and the
// other left behind -- and a REST caller and an MCP caller disagreeing about
// what a tool takes is the worst kind of quiet.
func TestTheRestListAndTheRpcListCannotDisagree(t *testing.T) {
	s, _ := newTestServer(t)

	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/tools", nil))
	var rest map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &rest); err != nil {
		t.Fatalf("GET /tools is not JSON: %v", err)
	}

	viaRPC := result(t, rpc(t, s, `{"jsonrpc":"2.0","id":3,"method":"tools/list"}`))

	a, _ := json.Marshal(rest["tools"])
	b, _ := json.Marshal(viaRPC["tools"])
	if string(a) != string(b) {
		t.Errorf("GET /tools and tools/list describe the tools differently.\n"+
			"They are two copies of one rendering; one has drifted.\n"+
			"  REST: %d bytes\n  RPC : %d bytes", len(a), len(b))
	}
}

// ---- the error codes -----------------------------------------------------

// JSON-RPC RESERVES THESE NUMBERS and clients branch on them. -32601 means
// "I do not have that method"; a client can fall back. A generic failure
// cannot be told apart from a broken server.
func TestUnknownMethodIsMethodNotFound(t *testing.T) {
	s, _ := newTestServer(t)
	code, msg := errOf(t, rpc(t, s, `{"jsonrpc":"2.0","id":4,"method":"resources/list"}`))
	if code != -32601 {
		t.Errorf("code = %d, want -32601 (method not found)", code)
	}
	if !strings.Contains(msg, "resources/list") {
		t.Errorf("the refusal must name the method it did not know; got %q", msg)
	}
}

// -32602 is "invalid params" and is what an unknown TOOL NAME earns: the
// method exists, the argument to it does not.
func TestUnknownToolIsInvalidParams(t *testing.T) {
	s, _ := newTestServer(t)
	code, msg := errOf(t, rpc(t, s,
		`{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"no_such_tool","arguments":{}}}`))
	if code != -32602 {
		t.Errorf("code = %d, want -32602 (invalid params)", code)
	}
	if !strings.Contains(msg, "no_such_tool") {
		t.Errorf("the refusal must name the tool it did not know; got %q", msg)
	}
}

func TestMalformedLineIsParseError(t *testing.T) {
	s, _ := newTestServer(t)
	code, _ := errOf(t, rpc(t, s, `{"jsonrpc":"2.0","id":6,`))
	if code != -32700 {
		t.Errorf("code = %d, want -32700 (parse error)", code)
	}
}

// The id is echoed so a client can match a reply to its request. A door that
// answers with a null id on a pipelined connection is unusable.
func TestTheIdComesBack(t *testing.T) {
	s, _ := newTestServer(t)
	resp := rpc(t, s, `{"jsonrpc":"2.0","id":77,"method":"initialize"}`)
	if got, _ := resp["id"].(float64); int(got) != 77 {
		t.Errorf("id = %v, want 77", resp["id"])
	}
	if resp["jsonrpc"] != "2.0" {
		t.Errorf("jsonrpc = %v, want 2.0", resp["jsonrpc"])
	}
}

// ---- what a caller is told when a tool fails -----------------------------

// A FAILING TOOL IS isError, NOT A TRANSPORT ERROR. The call reached the
// tool; the tool refused. Those are different things and MCP spells them
// differently -- a client that retries on transport errors would retry this
// one forever.
func TestARefusingToolIsIsErrorAndNotAnRpcError(t *testing.T) {
	s, _ := newTestServer(t)
	resp := rpc(t, s,
		`{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"records","arguments":{"project":"t","kind":"doctrine"}}}`)
	if _, isRPCErr := resp["error"]; isRPCErr {
		t.Fatalf("a tool's own refusal must not be a JSON-RPC error: %v", resp)
	}
	r := result(t, resp)
	if r["isError"] != true {
		t.Errorf("isError = %v, want true", r["isError"])
	}
	text := firstText(t, r)
	if strings.TrimSpace(text) == "" {
		t.Fatal("a refusal with no text tells the caller nothing")
	}
}

// THE REGRESSION STROKE FOR ADR-006 ITEM 1.
//
// `out` was discarded whenever a tool errored, one line before it would have
// been sent, and the caller got err.Error() instead. For anything shelling a
// subprocess that string is "exit status 1" -- a status with no cause.
// verify_chain is the tool that exposed it: it captures the Rust spine's
// CombinedOutput INTO `out`, so the diagnosis was in hand and thrown away.
//
// This stroke needs the spine built, and SAYS SO rather than passing quietly
// when it is absent -- ABSENT is not a pass (tests/PROVING.md).
func TestAToolsOwnWordsSurviveItsError(t *testing.T) {
	if !spineBuilt() {
		t.Skip("ABSENT: the Rust spine is not built -- run `cargo build -p atlas`. " +
			"Not a pass: this stroke proves what a caller is told when a tool " +
			"that writes output exits non-zero.")
	}
	s, home := newTestServer(t)

	// A real file that is emphatically not a chain. The spine will read it,
	// object in its own words, and exit non-zero.
	notAChain := filepath.Join(home, "not_a_chain.txt")
	if err := os.WriteFile(notAChain, []byte("this is not a ledger\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	r := result(t, rpc(t, s,
		`{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"verify_chain","arguments":{"project":"t","path":"not_a_chain.txt"}}}`))

	if r["isError"] != true {
		t.Fatalf("the call failed, so isError must stay true: %v", r)
	}
	text := strings.TrimSpace(firstText(t, r))
	if text == "" {
		t.Fatal("the caller was told nothing at all")
	}
	// The whole point: the bare Go status must not be the entire message.
	if text == "exit status 1" || text == "exit status 2" {
		t.Errorf("the caller got only %q -- the tool's own output was discarded "+
			"again (httpserver.go, the tools/call error branch)", text)
	}
}

// A SUCCEEDING TOOL IS NOT isError, and its text is its own.
func TestASucceedingToolCarriesItsOutputAndNoErrorFlag(t *testing.T) {
	s, _ := newTestServer(t)
	r := result(t, rpc(t, s,
		`{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"muster","arguments":{}}}`))
	if _, ok := r["isError"]; ok {
		t.Errorf("a tool that answered must not carry isError: %v", r)
	}
	if !strings.Contains(firstText(t, r), "t") {
		t.Errorf("muster should name the carried tenant; got %q", firstText(t, r))
	}
}

// ---- the plain endpoints -------------------------------------------------

func TestHealthNamesTheServerAndWhetherTheGateIsOn(t *testing.T) {
	s, _ := newTestServer(t)
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/health", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("GET /health = %d, want 200", rec.Code)
	}
	var h map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &h); err != nil {
		t.Fatalf("GET /health is not JSON: %v", err)
	}
	if h["status"] != "ok" {
		t.Errorf("status = %v, want ok", h["status"])
	}
	if h["server"] != "atlas-mcp" {
		t.Errorf("server = %v, want atlas-mcp", h["server"])
	}
	if h["auth"] != false {
		t.Errorf("auth = %v; this server was built with the gate off and must say so", h["auth"])
	}
}

// ---- helpers -------------------------------------------------------------

func firstText(t *testing.T, r map[string]any) string {
	t.Helper()
	content, ok := r["content"].([]any)
	if !ok || len(content) == 0 {
		t.Fatalf("no content in %v", r)
	}
	first, ok := content[0].(map[string]any)
	if !ok {
		t.Fatalf("content[0] is not an object: %v", content[0])
	}
	if first["type"] != "text" {
		t.Errorf("content[0].type = %v, want text", first["type"])
	}
	s, _ := first["text"].(string)
	return s
}

// spineBuilt walks out from this package the way the door itself does, so the
// stroke skips for the same reason the door would refuse.
func spineBuilt() bool {
	if p := os.Getenv("ATLAS_BIN"); p != "" {
		if st, err := os.Stat(p); err == nil && !st.IsDir() {
			return true
		}
	}
	name := "atlas"
	if os.PathSeparator == '\\' {
		name = "atlas.exe"
	}
	dir := "."
	for i := 0; i < 6; i++ {
		for _, profile := range []string{"release", "debug"} {
			if st, err := os.Stat(filepath.Join(dir, "target", profile, name)); err == nil && !st.IsDir() {
				return true
			}
		}
		dir = filepath.Join(dir, "..")
	}
	return false
}
