package main

import (
	"atlas/webapp/agents"
	"atlas/webapp/db"
	"atlas/webapp/evals"
	"atlas/webapp/handlers"
	"atlas/webapp/messaging"
	"atlas/webapp/search"
	"atlas/webapp/server"
	"atlas/webapp/traces"
	"embed"
	"fmt"
	"mime"
	"os"
)

// THE FONTS ARE NAMED HERE OR THEY DO NOT SHIP. This directive lists each
// directory explicitly, so a new one is invisible to the binary until it is
// added -- static/fonts/ would have 404'd silently and the console would have
// gone on falling back to Segoe UI with nothing to say it had.
//
//go:embed static/index.html static/css/* static/js/* static/fonts/*
var staticFiles embed.FS

func main() {
	// Go's builtin MIME table knows .css, .js, .svg and .wasm -- NOT .woff2.
	// Without this the file server sniffs the bytes and answers
	// application/octet-stream. Browsers are lenient about font types in
	// @font-face and would probably still render it, and "probably" is not a
	// thing to ship a typeface on.
	mime.AddExtensionType(".woff2", "font/woff2")

	port := "8091"
	if p := os.Getenv("ATLAS_WEB_PORT"); p != "" {
		port = p
	}

	database, err := db.Open("data/webapp.db")
	if err != nil {
		fmt.Fprintf(os.Stderr, "db open: %v\n", err)
		os.Exit(1)
	}
	defer database.Close()

	store := traces.NewStore(database)
	agentReg := agents.NewRegistry(database)
	evalEngine := evals.NewEngine(database, store)
	searchEngine := search.NewEngine(store, agentReg)
	msgBus := messaging.NewBus()
	msgBus.SetDB(database)

	h := handlers.New(store, agentReg, evalEngine, searchEngine, msgBus)
	srv := server.New(h, port, staticFiles)

	fmt.Printf("atlas-webapp listening on :%s\n", port)
	if err := srv.ListenAndServe(); err != nil {
		fmt.Fprintf(os.Stderr, "server: %v\n", err)
		os.Exit(1)
	}
}
