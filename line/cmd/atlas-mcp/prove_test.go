package main

// The prove battery lives in the binary (prove.go, SPEC_COMMANDS law);
// the test suite drives it so `go test ./...` never passes with a red line.

import "testing"

func TestProveStrokesGreen(t *testing.T) {
	if code := runProve(); code != 0 {
		t.Fatalf("runProve exited %d -- a stroke failed", code)
	}
}
