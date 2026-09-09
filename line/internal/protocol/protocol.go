// Package protocol speaks MCP over stdio: newline-delimited JSON-RPC 2.0
// (protocol 2025-06-18). Handshake, tools/list, tools/call; nothing else.
package protocol

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"

	"atlas/line/internal/tenant"
	"atlas/line/internal/tools"
)

type ServerInfo struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

type server struct {
	info         ServerInfo
	instructions string
	tools        *tools.Registry
	tenants      *tenant.Registry
}

// Serve reads one JSON-RPC request per line, writes one response per line.
func Serve(in io.Reader, out io.Writer, info ServerInfo, instructions string,
	reg *tools.Registry, tenants *tenant.Registry) error {
	s := &server{info: info, instructions: instructions, tools: reg, tenants: tenants}
	sc := bufio.NewScanner(in)
	sc.Buffer(make([]byte, 0, 1<<20), 16<<20)
	for sc.Scan() {
		line := sc.Bytes()
		if len(line) == 0 {
			continue
		}
		resp := s.handle(line)
		if resp == nil {
			continue // notification
		}
		b, err := json.Marshal(resp)
		if err != nil {
			return err
		}
		fmt.Fprintln(out, string(b))
	}
	return sc.Err()
}

type request struct {
	Jsonrpc string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
	Params  struct {
		Name      string         `json:"name"`
		Arguments map[string]any `json:"arguments"`
	} `json:"params"`
}

func (s *server) handle(line []byte) any {
	var req request
	if err := json.Unmarshal(line, &req); err != nil {
		return errResponse(nil, -32700, "parse error")
	}
	switch req.Method {
	case "initialize":
		return resultResponse(req.ID, map[string]any{
			"protocolVersion": "2025-06-18",
			"capabilities":    map[string]any{"tools": map[string]any{}},
			"serverInfo":      s.info,
			"instructions":    s.instructions,
		})
	case "notifications/initialized", "initialized":
		return nil
	case "tools/list":
		list := []map[string]any{}
		for _, t := range s.tools.All() {
			// THE SCHEMA MUST SAY WHAT IS OPTIONAL. Until 2026-08-27 this
			// computed `required` and then discarded it (`_ = required`),
			// emitting properties with no `required` array and no property
			// descriptions. By JSON Schema that means nothing is required --
			// but nothing SAYS so, and a model reading {"project":{"type":
			// "string"}} has no signal at all.
			//
			// Measured, live: a seat asked to call read_handoffs with no
			// arguments REFUSED, reporting "project is a required parameter",
			// and did so twice. It was wrong, and the wall it hit was ours: the
			// server knew the answer, computed it, and threw it away. The
			// default-ground path -- which the prove asserts with "default
			// tenant serves unnamed calls" -- was unreachable over the wire
			// because nothing told the caller it existed.
			//
			// A law the caller cannot read is not a law. It is a trap.
			props := map[string]any{}
			required := []string{}
			for _, a := range t.Args {
				name := trimOptional(a)
				desc := "the ground this call names"
				if endsWithOptional(a) {
					desc = "the ground this call names; OPTIONAL -- omit it " +
						"and the ground the session was opened in answers"
				} else {
					required = append(required, name)
				}
				props[name] = map[string]any{
					"type":        "string",
					"description": desc,
				}
			}
			list = append(list, map[string]any{
				"name":        t.Name,
				"description": t.Description,
				"inputSchema": map[string]any{
					"type":       "object",
					"properties": props,
					// Always emitted, even empty: an absent `required` is
					// silence, and silence is what got guessed at.
					"required": required,
				},
			})
		}
		return resultResponse(req.ID, map[string]any{"tools": list})
	case "tools/call":
		if _, ok := s.tools.Get(req.Params.Name); !ok {
			return errResponse(req.ID, -32602,
				fmt.Sprintf("unknown tool %q", req.Params.Name))
		}
		out, err := s.tools.Call(s.tenants, req.Params.Name, req.Params.Arguments)
		if err != nil {
			// Honest refusal as tool content: the caller sees the named why.
			return resultResponse(req.ID, map[string]any{
				"isError": true,
				"content": []map[string]any{{"type": "text", "text": err.Error()}},
			})
		}
		return resultResponse(req.ID, map[string]any{
			"content": []map[string]any{{"type": "text", "text": out}},
		})
	default:
		return errResponse(req.ID, -32601, fmt.Sprintf("unknown method %q", req.Method))
	}
}

func endsWithOptional(a string) bool {
	n := len(a)
	return n > 1 && a[n-1] == '?' && a[n-2] == '?'
}
func trimOptional(a string) string {
	for len(a) > 0 && a[len(a)-1] == '?' {
		a = a[:len(a)-1]
	}
	return a
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

func resultResponse(id json.RawMessage, result any) map[string]any {
	var idVal any
	if len(id) > 0 {
		_ = json.Unmarshal(id, &idVal)
	}
	return map[string]any{"jsonrpc": "2.0", "id": idVal, "result": result}
}

func errResponse(id json.RawMessage, code int, msg string) map[string]any {
	var idVal any
	if len(id) > 0 {
		_ = json.Unmarshal(id, &idVal)
	}
	return map[string]any{
		"jsonrpc": "2.0",
		"id":      idVal,
		"error":   rpcError{Code: code, Message: msg},
	}
}
