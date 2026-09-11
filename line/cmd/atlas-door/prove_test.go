package main

// The door prove battery lives in the binary; the test suite drives it so
// `go test ./...` never passes with a red door.

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

// ABSENT IS NOT A FAILURE, AND IT IS NOT A PASS EITHER.
//
// Every stroke in this battery goes through the Rust spine, so on a machine
// where it has not been built there is nothing to prove and nothing has gone
// wrong. This test used to report that as FAIL, which made a fresh clone look
// broken: the very first thing `go test ./...` said on a clean checkout was a
// red door, and the actual cause -- one undocumented `cargo build` -- was
// buried in a refusal nobody read.
//
// Found twice on 2026-09-11. First on a clean clone of both repos, where it
// was the ONLY red in sixteen packages. Then again by atlas's first CI, where
// the Linux job cannot build the spine at all (store/src/ffi.rs links
// Windows' winsqlite3) and so could never have passed this.
//
// `tests/prove.py` has held the right shape since it was written -- PASS,
// FAIL, ABSENT, where ABSENT names the command that would answer it and is
// never counted as a pass. This is that doctrine, in Go.
func TestDoorProveStrokesGreen(t *testing.T) {
	if bin := spine(); bin == "" {
		t.Skip("ABSENT: the Rust spine is not built, so every stroke in this " +
			"battery has nothing to ask. Build it with `cargo build -p atlas`, " +
			"or point ATLAS_BIN at one. Not a pass: nothing here was proven.")
	}
	if code := runProve(); code != 0 {
		t.Fatalf("runProve exited %d -- a stroke failed", code)
	}
}

// spine resolves the Rust binary the way findAtlas does, and returns "" when
// there is none. It deliberately mirrors findAtlas rather than calling it,
// because findAtlas RETURNS "atlas" when it finds nothing -- a sentinel that
// reads like an answer -- and a skip decision cannot be made on a value that
// cannot say "no".
func spine() string {
	if v := os.Getenv("ATLAS_BIN"); v != "" {
		if st, err := os.Stat(v); err == nil && !st.IsDir() {
			return v
		}
		return ""
	}
	if exe, err := exec.LookPath("atlas"); err == nil {
		return exe
	}
	name := "atlas"
	if os.PathSeparator == '\\' {
		name = "atlas.exe"
	}
	// Both profiles. findAtlas checks only debug, so a tree built with
	// --release would skip here and refuse there; checking both means the
	// skip is never wider than the door's own reach.
	for _, profile := range []string{"debug", "release"} {
		for _, up := range []string{".", "..", filepath.Join("..", ".."),
			filepath.Join("..", "..", "..")} {
			c := filepath.Join(up, "target", profile, name)
			if st, err := os.Stat(c); err == nil && !st.IsDir() {
				return c
			}
		}
	}
	return ""
}
