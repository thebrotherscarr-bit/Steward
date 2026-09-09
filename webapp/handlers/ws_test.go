package handlers

import (
	"net"
	"testing"
)

// The WS face is hand-rolled (zero deps); the frames are the risky half.
// net.Pipe stands in for the hijacked socket: client masks, server reads.
func TestWsFramesRoundTrip(t *testing.T) {
	a, b := net.Pipe()
	defer a.Close()
	defer b.Close()
	srv := &wsConn{c: a}

	// Client -> server masked "hello".
	go func() {
		payload := []byte("hello")
		hdr := []byte{0x81, 0x80 | byte(len(payload)), 0x01, 0x02, 0x03, 0x04}
		_, _ = b.Write(hdr)
		masked := make([]byte, len(payload))
		for i := range payload {
			masked[i] = payload[i] ^ hdr[2+i%4]
		}
		_, _ = b.Write(masked)
	}()
	got, err := srv.readText()
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "hello" {
		t.Fatalf("readText = %q", got)
	}

	// Server -> client unmasked; first two bytes must be FIN+text, len.
	go func() {
		_ = srv.writeText([]byte("world!"))
	}()
	hdr := make([]byte, 2)
	if _, err := b.Read(hdr); err != nil {
		t.Fatal(err)
	}
	if hdr[0] != 0x81 || hdr[1] != 6 {
		t.Fatalf("bad server frame header: %x", hdr)
	}
}
