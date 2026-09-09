// Serve: loopback HTTP for the door. One writer at a time lives in the
// Door mutex; the listener is loopback by default.
package main

import (
	"fmt"
	"net"
	"net/http"
	"net/url"
	"strings"
)

func doorHandler(d *Door) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" && r.URL.Path != "/ask" {
			http.NotFound(w, r)
			return
		}
		q := strings.TrimSpace(r.URL.Query().Get("q"))
		msg := strings.TrimSpace(r.URL.Query().Get("msg"))
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		fmt.Fprint(w, d.page(q, msg))
	})
	mux.HandleFunc("/badge", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		fmt.Fprint(w, d.badgeText())
	})
	mux.HandleFunc("/log", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "post a crew form", http.StatusMethodNotAllowed)
			return
		}
		if err := r.ParseForm(); err != nil {
			http.Error(w, "unreadable form", http.StatusBadRequest)
			return
		}
		said, err := d.logVisit(r.FormValue("prop"), r.FormValue("checks"),
			r.FormValue("notes"), r.FormValue("crew"))
		if err != nil {
			http.Error(w, "refused: "+err.Error(), http.StatusUnprocessableEntity)
			return
		}
		http.Redirect(w, r, "/?msg="+url.QueryEscape(firstLine(said)), http.StatusSeeOther)
	})
	mux.HandleFunc("/work", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "post a crew form", http.StatusMethodNotAllowed)
			return
		}
		if err := r.ParseForm(); err != nil {
			http.Error(w, "unreadable form", http.StatusBadRequest)
			return
		}
		said, err := d.openWork(r.FormValue("prop"), r.FormValue("issue"), r.FormValue("vendor"))
		if err != nil {
			http.Error(w, "refused: "+err.Error(), http.StatusUnprocessableEntity)
			return
		}
		http.Redirect(w, r, "/?msg="+url.QueryEscape(firstLine(said)), http.StatusSeeOther)
	})
	return mux
}

func serve(bind string, port int, d *Door) int {
	addr := fmt.Sprintf("%s:%d", bind, port)
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		fmt.Printf("door refused: cannot bind %s: %s\n", addr, err)
		return 1
	}
	fmt.Printf("  THE DOOR is open — http://%s on loopback. One page: ask, see, log.\n", ln.Addr())
	if err := http.Serve(ln, doorHandler(d)); err != nil {
		fmt.Printf("door closed: %s\n", err)
	}
	return 0
}

func firstLine(s string) string {
	if i := strings.Index(s, "\n"); i >= 0 {
		return s[:i]
	}
	return s
}
