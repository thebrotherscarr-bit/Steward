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
	"os"
)

//go:embed static/index.html static/css/* static/js/*
var staticFiles embed.FS

func main() {
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
