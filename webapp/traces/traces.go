package traces

import (
	"atlas/webapp/db"
)

type Store struct {
	db *db.DB
}

func NewStore(database *db.DB) *Store {
	return &Store{db: database}
}

func (s *Store) Add(t db.Trace) {
	s.db.AddTrace(t)
}

func (s *Store) List(agentID string, limit int) []db.Trace {
	return s.db.GetTraces(agentID, limit)
}

func (s *Store) ListByAgent(agentID string, limit int) []db.Trace {
	return s.db.GetTraces(agentID, limit)
}

func (s *Store) Get(id string) *db.Trace {
	return s.db.GetTrace(id)
}

func (s *Store) Count() int {
	return len(s.db.GetTraces("", 0))
}

func (s *Store) GetSetting(key string) string {
	return s.db.GetKey(key)
}

func (s *Store) SetSetting(key, value string) {
	s.db.SetKey(key, value)
}
