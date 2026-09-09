package main

// The door prove battery lives in the binary; the test suite drives it so
// `go test ./...` never passes with a red door.

import "testing"

func TestDoorProveStrokesGreen(t *testing.T) {
	if code := runProve(); code != 0 {
		t.Fatalf("runProve exited %d -- a stroke failed", code)
	}
}
