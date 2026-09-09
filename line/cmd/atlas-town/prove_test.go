package main

// The town prove battery lives in the binary; the test suite drives it so
// `go test ./...` never passes with a red town.

import "testing"

func TestTownProveStrokesGreen(t *testing.T) {
	if code := runProve(); code != 0 {
		t.Fatalf("runProve exited %d -- a stroke failed", code)
	}
}
