package evals

import (
	"atlas/webapp/db"
	"atlas/webapp/traces"
)

type Engine struct {
	db    *db.DB
	store *traces.Store
}

func NewEngine(database *db.DB, store *traces.Store) *Engine {
	return &Engine{db: database, store: store}
}

func (e *Engine) Add(ev db.Eval) {
	e.db.AddEval(ev)
}

func (e *Engine) ListByTrace(traceID string) []db.Eval {
	return e.db.GetEvals(traceID)
}

func (e *Engine) Count() int {
	return len(e.db.GetEvals(""))
}
