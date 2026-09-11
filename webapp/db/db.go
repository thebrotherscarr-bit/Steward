package db

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type DB struct {
	dir    string
	mu     sync.RWMutex
	traces []Trace
	evals  []Eval
	agents []Agent
	msgs   []Message
	keys   map[string]string
}

type Trace struct {
	ID         string    `json:"id"`
	AgentID    string    `json:"agent_id"`
	Tool       string    `json:"tool"`
	Input      string    `json:"input"`
	Output     string    `json:"output"`
	Hash       string    `json:"hash"`
	Status     string    `json:"status"`
	DurationMs int64     `json:"duration_ms"`
	CreatedAt  time.Time `json:"created_at"`
	Tenant     string    `json:"tenant,omitempty"`
}

type Eval struct {
	ID        string    `json:"id"`
	TraceID   string    `json:"trace_id"`
	Name      string    `json:"name"`
	Score     float64   `json:"score"`
	Passed    bool      `json:"passed"`
	Detail    string    `json:"detail"`
	CreatedAt time.Time `json:"created_at"`
	Tenant    string    `json:"tenant,omitempty"`
}

type Agent struct {
	ID          string `json:"id"`
	Office      string `json:"office"`
	ReportsTo   string `json:"reports_to"`
	Role        string `json:"role"`
	Mode        string `json:"mode"`
	Permissions string `json:"permissions"`
	USContent   string `json:"us_content"`
	Tenant      string `json:"tenant,omitempty"`
}

type Message struct {
	ID        string    `json:"id"`
	Channel   string    `json:"channel"`
	Platform  string    `json:"platform"`
	AgentID   string    `json:"agent_id"`
	Content   string    `json:"content"`
	Direction string    `json:"direction"`
	CreatedAt time.Time `json:"created_at"`
	Tenant    string    `json:"tenant,omitempty"`
}

type fileData struct {
	Traces []Trace           `json:"traces"`
	Evals  []Eval            `json:"evals"`
	Agents []Agent           `json:"agents"`
	Msgs   []Message         `json:"messages"`
	Keys   map[string]string `json:"keys"`
}

func Open(dir string) (*DB, error) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	d := &DB{
		dir:  dir,
		keys: make(map[string]string),
	}
	d.load()
	return d, nil
}

func (d *DB) load() {
	path := filepath.Join(d.dir, "store.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	var fd fileData
	if json.Unmarshal(data, &fd) == nil {
		d.traces = fd.Traces
		d.evals = fd.Evals
		d.agents = fd.Agents
		d.msgs = fd.Msgs
		if fd.Keys != nil {
			d.keys = fd.Keys
		}
	}
}

func (d *DB) Save() error {
	d.mu.RLock()
	fd := fileData{
		Traces: d.traces,
		Evals:  d.evals,
		Agents: d.agents,
		Msgs:   d.msgs,
		Keys:   d.keys,
	}
	d.mu.RUnlock()
	data, err := json.MarshalIndent(fd, "", "  ")
	if err != nil {
		return err
	}
	tmp := filepath.Join(d.dir, "store.json.tmp")
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, filepath.Join(d.dir, "store.json"))
}

func (d *DB) AddTrace(t Trace) {
	d.mu.Lock()
	d.traces = append(d.traces, t)
	d.mu.Unlock()
	d.Save()
}

func (d *DB) GetTraces(agentID string, limit int) []Trace {
	d.mu.RLock()
	defer d.mu.RUnlock()
	var result []Trace
	for i := len(d.traces) - 1; i >= 0; i-- {
		if agentID == "" || d.traces[i].AgentID == agentID {
			result = append(result, d.traces[i])
			if limit > 0 && len(result) >= limit {
				break
			}
		}
	}
	return result
}

func (d *DB) GetTrace(id string) *Trace {
	d.mu.RLock()
	defer d.mu.RUnlock()
	for i := range d.traces {
		if d.traces[i].ID == id {
			return &d.traces[i]
		}
	}
	return nil
}

func (d *DB) AddEval(e Eval) {
	d.mu.Lock()
	d.evals = append(d.evals, e)
	d.mu.Unlock()
	d.Save()
}

func (d *DB) GetEvals(traceID string) []Eval {
	d.mu.RLock()
	defer d.mu.RUnlock()
	var result []Eval
	for _, e := range d.evals {
		if traceID == "" || e.TraceID == traceID {
			result = append(result, e)
		}
	}
	return result
}

func (d *DB) UpsertAgent(a Agent) {
	d.mu.Lock()
	for i := range d.agents {
		if d.agents[i].ID == a.ID {
			d.agents[i] = a
			d.mu.Unlock()
			d.Save()
			return
		}
	}
	d.agents = append(d.agents, a)
	d.mu.Unlock()
	d.Save()
}

func (d *DB) GetAgents() []Agent {
	d.mu.RLock()
	defer d.mu.RUnlock()
	out := make([]Agent, len(d.agents))
	copy(out, d.agents)
	return out
}

func (d *DB) GetAgent(id string) *Agent {
	d.mu.RLock()
	defer d.mu.RUnlock()
	for i := range d.agents {
		if d.agents[i].ID == id {
			return &d.agents[i]
		}
	}
	return nil
}

func (d *DB) AddMessage(m Message) {
	d.mu.Lock()
	d.msgs = append(d.msgs, m)
	d.mu.Unlock()
	d.Save()
}

func (d *DB) GetMessages(channel string, limit int) []Message {
	d.mu.RLock()
	defer d.mu.RUnlock()
	var result []Message
	for i := len(d.msgs) - 1; i >= 0; i-- {
		if channel == "" || d.msgs[i].Channel == channel {
			result = append(result, d.msgs[i])
			if limit > 0 && len(result) >= limit {
				break
			}
		}
	}
	return result
}

func (d *DB) SetKey(key, value string) {
	d.mu.Lock()
	d.keys[key] = value
	d.mu.Unlock()
	d.Save()
}

func (d *DB) GetKey(key string) string {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return d.keys[key]
}

func (d *DB) Close() error {
	return d.Save()
}
