// Shipped prove battery for atlas-door (SPEC_COMMANDS). Temp book over a
// real loopback socket; the atlas binary is never built here — it must
// already stand (ATLAS_BIN, built tree, or PATH), or the strokes refuse by
// name instead of fabricating.
package main

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

type stroke struct {
	name string
	ok   bool
	det  string
}

func runProve() int {
	strokes := []stroke{}
	check := func(name string, ok bool, det ...any) {
		d := ""
		if len(det) > 0 {
			d = fmt.Sprint(det...)
		}
		strokes = append(strokes, stroke{name, ok, d})
	}

	root, err := os.MkdirTemp("", "atlas_door_prove_")
	if err != nil {
		fmt.Printf("prove refused: %s\n", err)
		return 1
	}
	defer os.RemoveAll(root)

	bin := findAtlas()
	probe := NewDoor(root, bin)
	if _, err := probe.trade("property", "list"); err != nil {
		fmt.Printf("prove refused: no working atlas binary behind %q: %s\n", bin, err)
		fmt.Println("build it first (cargo build -p atlas) or set ATLAS_BIN.")
		return 1
	}

	door := NewDoor(root, bin)
	must := func(skill, arg string) {
		if _, err := door.trade(skill, arg); err != nil {
			check("prove ground stands ("+skill+")", false, err)
		}
	}
	must("property", "enroll Red Rock Loop | 55 Red Rock Loop Rd")
	must("workorder", "add Red Rock Loop | gate hinge javelina damage | Marco")
	must("inspect", "log Red Rock Loop | pressure relief drain=fail | drain weeping, parts ordered")

	srv := httptest.NewUnstartedServer(doorHandler(door))
	// Loopback only, like serve().
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		fmt.Printf("prove refused: no loopback: %s\n", err)
		return 1
	}
	srv.Listener = ln
	srv.Start()
	defer srv.Close()

	get := func(path string) (int, string) {
		resp, err := http.Get(srv.URL + path)
		if err != nil {
			return 0, err.Error()
		}
		defer resp.Body.Close()
		b, _ := io.ReadAll(resp.Body)
		return resp.StatusCode, string(b)
	}
	post := func(path string, form url.Values) (int, string) {
		resp, err := http.PostForm(srv.URL+path, form)
		if err != nil {
			return 0, err.Error()
		}
		defer resp.Body.Close()
		b, _ := io.ReadAll(resp.Body)
		// PostForm follows redirects; the landing page carries the msg.
		return resp.StatusCode, string(b)
	}

	code, page := get("/")
	check("the page opens, one-thumbed", code == 200 && strings.Contains(page, "viewport"))
	check("the badge is green when the record proves whole",
		strings.Contains(page, "record proves whole"))
	check("open work stands on the page",
		strings.Contains(page, "gate hinge javelina damage"))
	check("recent visits carry their receipts",
		strings.Contains(page, "verified") && strings.Contains(page, "drain weeping"))

	code, page = get("/ask?q=" + url.QueryEscape("pressure relief drain"))
	check("a plain question gets the answer with its receipt",
		strings.Contains(page, "THE ANSWER") && strings.Contains(page, "FAILED: pressure relief drain") &&
			strings.Contains(page, "verified"))
	code, page = get("/ask?q=quantum+braiding")
	check("an absent thing is denied honestly", strings.Contains(page, "nothing on file"))

	code, page = post("/log", url.Values{
		"prop": {"Red Rock Loop"}, "checks": {"water filter=pass"},
		"notes": {"replaced filter, 20 minutes"}, "crew": {"Mike"}})
	check("a crew visit logs from the phone form, sealed",
		code == 200 && strings.Contains(page, "inspection logged for Red Rock Loop"))
	_, page = get("/")
	check("and stands on the page, witnessed",
		strings.Contains(page, "by Mike") && strings.Contains(page, "replaced filter"))

	code, page = post("/work", url.Values{
		"prop": {"Red Rock Loop"}, "issue": {"swamp cooler pads worn"}, "vendor": {"Dale"}})
	check("a work order opens from the phone form",
		code == 200 && strings.Contains(page, "opened work order #2"))
	_, page = get("/")
	check("and stands in OPEN WORK", strings.Contains(page, "swamp cooler pads worn"))

	// Entries chained + witnessed: the books verify intact after phone writes.
	whole, _ := door.badge()
	check("phone writes land chained and witnessed", whole)

	p := filepath.Join(root, "inspections.jsonl")
	if raw, err := os.ReadFile(p); err == nil {
		os.WriteFile(p, []byte(strings.Replace(string(raw), "fail", "pass", 1)), 0o644)
	}
	_, page = get("/")
	check("a flipped byte turns the badge red and names the break",
		strings.Contains(page, "RECORD BROKEN") && strings.Contains(page, "BROKEN at entry 0"))

	code, _ = get("/nowhere")
	check("a wrong path is refused", code == 404)

	width := 0
	for _, s := range strokes {
		if len(s.name) > width {
			width = len(s.name)
		}
	}
	allOk := true
	fmt.Println("\n  THE DOOR -- prove (temp book, loopback, nothing passes REVIEW)")
	for _, s := range strokes {
		status := "PASS"
		if !s.ok {
			status = "FAIL"
			allOk = false
		}
		fmt.Printf("    [%s]  %-*s   %s\n", status, width, s.name, s.det)
	}
	fmt.Println()
	if allOk {
		fmt.Println("  PROVEN. The door opens, answers with receipts, and goes red the moment the record lies.")
		return 0
	}
	fmt.Println("  A stroke failed. The door does not open on a claim it cannot show.")
	return 1
}
