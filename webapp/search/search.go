package search

import (
	"atlas/webapp/agents"
	"atlas/webapp/traces"
	"strings"
)

type Result struct {
	Type  string      `json:"type"`
	ID    string      `json:"id"`
	Name  string      `json:"name"`
	Extra string      `json:"extra"`
	Data  interface{} `json:"data"`
}

type Engine struct {
	store  *traces.Store
	agents *agents.Registry
}

func NewEngine(store *traces.Store, agentReg *agents.Registry) *Engine {
	return &Engine{store: store, agents: agentReg}
}

func (e *Engine) Query(q string) []Result {
	q = strings.ToLower(q)
	var results []Result

	for _, a := range e.agents.List() {
		if strings.Contains(strings.ToLower(a.ID), q) ||
			strings.Contains(strings.ToLower(a.Role), q) ||
			strings.Contains(strings.ToLower(a.Office), q) {
			results = append(results, Result{
				Type:  "agent",
				ID:    a.ID,
				Name:  a.ID,
				Extra: a.Role,
				Data:  a,
			})
		}
	}

	traces := e.store.List("", 500)
	for _, t := range traces {
		if strings.Contains(strings.ToLower(t.Tool), q) ||
			strings.Contains(strings.ToLower(t.AgentID), q) ||
			strings.Contains(strings.ToLower(t.Output), q) {
			results = append(results, Result{
				Type:  "trace",
				ID:    t.ID,
				Name:  t.Tool,
				Extra: t.AgentID,
				Data:  t,
			})
		}
	}

	return results
}
