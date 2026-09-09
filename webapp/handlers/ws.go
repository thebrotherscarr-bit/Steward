// WebSocket face (N1): GET /ws speaks RFC 6455 hand-rolled over stdlib —
// no npm, no Go modules, handshake to frames by hand.
//
// Frames in:  {type:"chat.send", session, question, voice?, actor?}
// Frames out: {type:"chat.token", session, token} as the voice speaks,
//             {type:"chat.done", session, text} with the receipt,
//             {type:"chat.error", error} on refusal,
//             plus every hub broadcast (chat.opened/done, trace/eval/message).
// Browsers that cannot speak WS keep the SSE faces; nothing is WS-only.
package handlers

import (
	"bufio"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"sync"
)

const wsGUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

type wsConn struct {
	c  net.Conn
	mu sync.Mutex
}

func (w *wsConn) writeText(payload []byte) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	var hdr []byte
	if len(payload) < 126 {
		hdr = []byte{0x81, byte(len(payload))}
	} else if len(payload) < 65536 {
		hdr = []byte{0x81, 126, 0, 0}
		binary.BigEndian.PutUint16(hdr[2:], uint16(len(payload)))
	} else {
		hdr = []byte{0x81, 127, 0, 0, 0, 0, 0, 0, 0, 0}
		binary.BigEndian.PutUint64(hdr[2:], uint64(len(payload)))
	}
	if _, err := w.c.Write(hdr); err != nil {
		return err
	}
	_, err := w.c.Write(payload)
	return err
}

// readText reads one message, assembling fragments, answering pings.
func (w *wsConn) readText() ([]byte, error) {
	var msg []byte
	for {
		hdr := make([]byte, 2)
		if _, err := io.ReadFull(w.c, hdr); err != nil {
			return nil, err
		}
		fin := hdr[0]&0x80 != 0
		op := hdr[0] & 0x0F
		masked := hdr[1]&0x80 != 0
		n := int64(hdr[1] & 0x7F)
		switch n {
		case 126:
			var ext [2]byte
			if _, err := io.ReadFull(w.c, ext[:]); err != nil {
				return nil, err
			}
			n = int64(binary.BigEndian.Uint16(ext[:]))
		case 127:
			var ext [8]byte
			if _, err := io.ReadFull(w.c, ext[:]); err != nil {
				return nil, err
			}
			n = int64(binary.BigEndian.Uint64(ext[:]))
		}
		var mask [4]byte
		if masked {
			if _, err := io.ReadFull(w.c, mask[:]); err != nil {
				return nil, err
			}
		}
		payload := make([]byte, n)
		if _, err := io.ReadFull(w.c, payload); err != nil {
			return nil, err
		}
		if masked {
			for i := range payload {
				payload[i] ^= mask[i%4]
			}
		}
		switch op {
		case 0x8:
			return nil, io.EOF
		case 0x9:
			_ = w.writeText(nil) // pong-ish; browsers tolerate text silence
			continue
		case 0xA:
			continue
		case 0x1, 0x0:
			msg = append(msg, payload...)
			if fin {
				return msg, nil
			}
		default:
			return nil, fmt.Errorf("unsupported opcode %d", op)
		}
	}
}

// wsBroadcast fans one event to every WS client; slow clients are dropped.
func (h *Handlers) wsBroadcast(typ string, data any) {
	b, _ := json.Marshal(map[string]any{"type": typ, "data": data})
	h.wsMu.Lock()
	defer h.wsMu.Unlock()
	for c := range h.wsClients {
		if err := c.writeText(b); err != nil {
			c.c.Close()
			delete(h.wsClients, c)
		}
	}
}

// WS upgrades GET /ws and serves one client for the life of the socket.
func (h *Handlers) WS(w http.ResponseWriter, r *http.Request) {
	if !strings.EqualFold(r.Header.Get("Upgrade"), "websocket") {
		http.Error(w, "websocket upgrade required", http.StatusBadRequest)
		return
	}
	key := strings.TrimSpace(r.Header.Get("Sec-Websocket-Key"))
	if key == "" {
		http.Error(w, "missing Sec-WebSocket-Key", http.StatusBadRequest)
		return
	}
	sum := sha1.Sum([]byte(key + wsGUID))
	accept := base64.StdEncoding.EncodeToString(sum[:])
	hj, ok := w.(http.Hijacker)
	if !ok {
		http.Error(w, "hijack unsupported", http.StatusInternalServerError)
		return
	}
	conn, rw, err := hj.Hijack()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	fmt.Fprintf(rw, "HTTP/1.1 101 Switching Protocols\r\n"+
		"Upgrade: websocket\r\nConnection: Upgrade\r\n"+
		"Sec-WebSocket-Accept: %s\r\n\r\n", accept)
	_ = rw.Flush()
	c := &wsConn{c: conn}
	h.wsMu.Lock()
	if h.wsClients == nil {
		h.wsClients = map[*wsConn]bool{}
	}
	h.wsClients[c] = true
	h.wsMu.Unlock()
	wsTenant := ""
	if h.authOn {
		sess, ok := h.sessionOf(r)
		if !ok || sess == nil {
			b, _ := json.Marshal(map[string]any{"type": "chat.error", "data": map[string]string{"error": "login required"}})
			_ = c.writeText(b)
			return
		}
		wsTenant = sess.Tenant
	}
	defer func() {
		h.wsMu.Lock()
		delete(h.wsClients, c)
		h.wsMu.Unlock()
		conn.Close()
	}()
	for {
		raw, err := c.readText()
		if err != nil {
			return
		}
		var frame struct {
			Type     string `json:"type"`
			Session  string `json:"session"`
			Question string `json:"question"`
			Voice    string `json:"voice"`
			Actor    string `json:"actor"`
		}
		if json.Unmarshal(raw, &frame) != nil {
			continue
		}
		switch frame.Type {
		case "ping":
			_ = c.writeText([]byte(`{"type":"pong"}`))
		case "chat.send":
			h.wsChatSend(c, wsTenant, frame.Session, frame.Question, frame.Voice, frame.Actor)
		}
	}
}

// wsChatSend runs one turn through the MCP stream face and forwards every
// token as a WS frame. Logic stays in the LINE; this is a face, not a fork.
func (h *Handlers) wsChatSend(c *wsConn, tenant, session, question, voice, actor string) {
	send := func(typ string, data any) {
		b, _ := json.Marshal(map[string]any{"type": typ, "session": session, "data": data})
		_ = c.writeText(b)
	}
	req, err := http.NewRequest("GET", h.mcpURL()+"/chat/stream", nil)
	if err != nil {
		send("chat.error", map[string]string{"error": err.Error()})
		return
	}
	qq := req.URL.Query()
	qq.Set("session", session)
	qq.Set("question", question)
	qq.Set("voice", voice)
	qq.Set("actor", actor)
	if tenant != "" {
		qq.Set("project", tenant)
	}
	req.URL.RawQuery = qq.Encode()
	if h.service != "" {
		req.Header.Set("Authorization", "Bearer "+h.service)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		send("chat.error", map[string]string{"error": fmt.Sprintf("mcp unreachable: %v", err)})
		return
	}
	defer resp.Body.Close()
	sc := bufio.NewScanner(resp.Body)
	sc.Buffer(make([]byte, 0, 1<<20), 8<<20)
	var ev string
	for sc.Scan() {
		line := sc.Text()
		if strings.HasPrefix(line, "event: ") {
			ev = strings.TrimSpace(strings.TrimPrefix(line, "event: "))
			continue
		}
		if !strings.HasPrefix(line, "data: ") {
			continue
		}
		var data map[string]any
		_ = json.Unmarshal([]byte(strings.TrimPrefix(line, "data: ")), &data)
		switch ev {
		case "token":
			if tok, _ := data["token"].(string); tok != "" {
				send("chat.token", map[string]string{"token": tok})
			}
		case "done":
			send("chat.done", map[string]string{"text": fmt.Sprintf("%v", data["text"])})
		case "refused":
			send("chat.error", map[string]string{"error": fmt.Sprintf("%v", data["error"])})
		}
		ev = ""
	}
}
