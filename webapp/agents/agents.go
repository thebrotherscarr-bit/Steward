package agents

import (
	"atlas/webapp/db"
)

type Registry struct {
	db *db.DB
}

func NewRegistry(database *db.DB) *Registry {
	return &Registry{db: database}
}

func (r *Registry) List() []db.Agent {
	return r.db.GetAgents()
}

func (r *Registry) Get(id string) *db.Agent {
	return r.db.GetAgent(id)
}

func (r *Registry) Upsert(a db.Agent) {
	r.db.UpsertAgent(a)
}
