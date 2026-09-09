// Store: the mesh on disk — per-actor chains plus the channel-head chain.
//
// Layout under <home>/state/mesh/:
//
//	members.json          actor -> {pub, mark} (mesh-local admission)
//	chains/<actor>.jsonl  one pen per actor; append-only
//	head.jsonl            the SSM channel-head: one entry per post, citing it
//	ledger.jsonl          deciphering ledger: entry hash -> salt + commitment
//
// One writer at a time (the tool layer holds the ask lock; a package mutex
// backs direct callers). No fork is ever permitted: a second head is TAMPER.
package mesh

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
)

var mu sync.Mutex

var actorRe = regexp.MustCompile(`^[a-z0-9][a-z0-9_.-]*$`)

// Member is one enrolled mesh voice: key binding, not the key.
type Member struct {
	Pub  string `json:"pub"`
	Mark string `json:"mark"`
}

func membersPath(dir string) string { return filepath.Join(dir, "members.json") }
func chainsDir(dir string) string   { return filepath.Join(dir, "chains") }
func headPath(dir string) string    { return filepath.Join(dir, "head.jsonl") }
func ledgerPath(dir string) string  { return filepath.Join(dir, "ledger.jsonl") }

func loadMembers(dir string) (map[string]Member, error) {
	m := map[string]Member{}
	b, err := os.ReadFile(membersPath(dir))
	if err != nil {
		if os.IsNotExist(err) {
			return m, nil
		}
		return nil, err
	}
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, fmt.Errorf("members.json unparsable: %s", err)
	}
	return m, nil
}

func saveMembers(dir string, m map[string]Member) error {
	b, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	tmp := membersPath(dir) + ".tmp"
	if err := os.WriteFile(tmp, append(b, '\n'), 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, membersPath(dir))
}

// Enroll binds actor -> pub. The pub must be a real curve point; the mark
// welds inside every later post. A conflicting pub is REFUSED — re-keying is
// an operator procedure (new epoch note on-chain), never a silent overwrite.
func Enroll(dir, actor, pubHex string) (Member, error) {
	mu.Lock()
	defer mu.Unlock()
	if !actorRe.MatchString(actor) {
		return Member{}, fmt.Errorf("refused: actor %q is not a mesh name (lowercase id)", actor)
	}
	pub, err := hex.DecodeString(strings.ToLower(pubHex))
	if err != nil || len(pub) != 64 {
		return Member{}, fmt.Errorf("refused: pub for %q is not 64 bytes hex", actor)
	}
	pt, err := deser(pub)
	if err != nil || !OnCurve(pt) {
		return Member{}, fmt.Errorf("refused: pub for %q is not a curve point", actor)
	}
	members, err := loadMembers(dir)
	if err != nil {
		return Member{}, err
	}
	if old, ok := members[actor]; ok {
		if old.Pub != hex.EncodeToString(pub) {
			return Member{}, fmt.Errorf("refused: %q already bound to another key — "+
				"re-keying rides an operator epoch note, never a rewrite", actor)
		}
		return old, nil // idempotent
	}
	mb := Member{Pub: hex.EncodeToString(pub), Mark: Mark(pub)}
	members[actor] = mb
	if err := os.MkdirAll(chainsDir(dir), 0o755); err != nil {
		return Member{}, err
	}
	if err := saveMembers(dir, members); err != nil {
		return Member{}, err
	}
	return mb, nil
}

// scalarFor derives the signing scalar and seal key from the actor's env
// secret (domain-separated), and checks the scalar against the enrolled pub.
// A key that does not match the binding signs nothing.
func scalarFor(actor string, mb Member) (scalar, sealKey []byte, err error) {
	secret, err := KeyFromEnv(actor)
	if err != nil {
		return nil, nil, err
	}
	sh := sha256.New()
	sh.Write([]byte("MESH|sign|"))
	sh.Write(secret)
	sc := modN(sh.Sum(nil))
	if new(big.Int).SetBytes(sc.Bytes()).Sign() == 0 {
		return nil, nil, fmt.Errorf("derived scalar for %q is zero — re-key", actor)
	}
	if hex.EncodeToString(Pub(new(big.Int).SetBytes(sc.Bytes()))) != mb.Pub {
		return nil, nil, fmt.Errorf("refused: the key at hand does not match %q's enrolled pub", actor)
	}
	return sc.Bytes(), SealKey(secret), nil
}

func readLines(path string) ([]string, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var out []string
	for _, ln := range strings.Split(string(b), "\n") {
		if strings.TrimSpace(ln) != "" {
			out = append(out, ln)
		}
	}
	return out, nil
}

func appendLine(path, line string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(line + "\n")
	return err
}

func entryHashes(lines []string) (map[string]bool, []*Entry, error) {
	set := map[string]bool{}
	var entries []*Entry
	for _, ln := range lines {
		e, err := ParseLine(ln)
		if err != nil {
			return nil, nil, err
		}
		set[e.Hash] = true
		entries = append(entries, e)
	}
	return set, entries, nil
}

// Post appends one message: per-actor chain entry plus the channel-head weld.
// chanName must equal the caller's project (the wall); to must name a member,
// @channel, or @everyone — anything else is egress and is refused outright.
func Post(dir, chanName, actor, to, mode, text, kind string, cites []string) (*Entry, *Entry, error) {
	mu.Lock()
	defer mu.Unlock()
	if !lawfulKind(kind) || kind == "head" {
		return nil, nil, fmt.Errorf("refused: kind %q is not a mesh kind", kind)
	}
	if strings.TrimSpace(text) == "" {
		return nil, nil, fmt.Errorf("refused: every message says what it is — empty text posts nothing")
	}
	if mode != ModeSealed && mode != ModeOpen {
		return nil, nil, fmt.Errorf("refused: mode is %q or %q, not %q", ModeSealed, ModeOpen, mode)
	}
	members, err := loadMembers(dir)
	if err != nil {
		return nil, nil, err
	}
	mb, ok := members[actor]
	if !ok {
		return nil, nil, fmt.Errorf("refused: actor %q is not enrolled — mesh_enroll first", actor)
	}
	if to != "@channel" && to != "@everyone" {
		if _, ok := members[to]; !ok {
			return nil, nil, fmt.Errorf("refused: destination %q is not this estate — "+
				"egress is a packet, not a message", to)
		}
	}
	for _, c := range cites {
		if !isHexOf(c, 16, 40, 64) {
			return nil, nil, fmt.Errorf("refused: citation %q is not a hash (16/40/64 hex)", c)
		}
	}
	scalar, sealKey, err := scalarFor(actor, mb)
	if err != nil {
		return nil, nil, err
	}

	chainPath := filepath.Join(chainsDir(dir), actor+".jsonl")
	lines, err := readLines(chainPath)
	if err != nil {
		return nil, nil, err
	}
	known, entries, err := entryHashes(lines)
	if err != nil {
		return nil, nil, err
	}
	// 64-hex cites must name entries in this channel's wall.
	for _, c := range cites {
		if len(c) == 64 && !known[c] && !headKnows(dir, c) {
			return nil, nil, fmt.Errorf("refused: citation %q names nothing in channel %q", c, chanName)
		}
	}
	prev := Genesis
	if len(entries) > 0 {
		prev = entries[len(entries)-1].Hash
	}
	ct := text
	var saltHex, commitment string
	if mode == ModeSealed {
		var ctHex string
		saltHex, ctHex, commitment, err = Seal(sealKey, []byte(text))
		if err != nil {
			return nil, nil, err
		}
		ct = ctHex
	}
	e := &Entry{
		TS: NowTS(), Kind: kind,
		Payload: Payload{N: int64(len(entries) + 1), Chan: chanName, To: to,
			Ct: ct, Mode: mode, Cites: append([]string(nil), cites...), Mark: mb.Mark},
		Prev: prev, Actor: actor,
	}
	h, err := HashEntry(e.Prev, e.bodyMap())
	if err != nil {
		return nil, nil, err
	}
	e.Hash = h
	priv := new(big.Int).SetBytes(scalar)
	e.Sig = hex.EncodeToString(Sign(priv, []byte(e.Hash)))
	e.Pub = mb.Pub
	line, err := e.lineJSON()
	if err != nil {
		return nil, nil, err
	}
	if err := appendLine(chainPath, line); err != nil {
		return nil, nil, err
	}
	if mode == ModeSealed {
		rec, _ := json.Marshal(map[string]string{
			"entry": e.Hash, "salt": saltHex, "commitment": commitment})
		if err := appendLine(ledgerPath(dir), string(rec)); err != nil {
			return nil, nil, err
		}
	}
	head, err := appendHead(dir, chanName, actor, e, scalar, mb)
	if err != nil {
		return nil, nil, err
	}
	return e, head, nil
}

func headKnows(dir, hash string) bool {
	lines, err := readLines(headPath(dir))
	if err != nil {
		return false
	}
	for _, ln := range lines {
		e, err := ParseLine(ln)
		if err != nil {
			continue
		}
		if e.Hash == hash {
			return true
		}
		for _, c := range e.Payload.Cites {
			if c == hash {
				return true
			}
		}
	}
	return false
}

// appendHead welds the channel-head: one entry per post, citing it. The head
// entry is signed by the posting actor — no invented ssm actor.
func appendHead(dir, chanName, actor string, ref *Entry, scalar []byte, mb Member) (*Entry, error) {
	lines, err := readLines(headPath(dir))
	if err != nil {
		return nil, err
	}
	_, entries, err := entryHashes(lines)
	if err != nil {
		return nil, err
	}
	prev := Genesis
	if len(entries) > 0 {
		prev = entries[len(entries)-1].Hash
	}
	h := &Entry{
		TS: NowTS(), Kind: "head",
		Payload: Payload{N: int64(len(entries) + 1), Chan: chanName, To: "@channel",
			Ct: fmt.Sprintf("head %d: %s n=%d %s", len(entries)+1, actor, ref.Payload.N, ref.Hash[:16]),
			Mode: ModeOpen, Cites: []string{ref.Hash}, Mark: mb.Mark},
		Prev: prev, Actor: actor,
	}
	hh, err := HashEntry(h.Prev, h.bodyMap())
	if err != nil {
		return nil, err
	}
	h.Hash = hh
	priv := new(big.Int).SetBytes(scalar)
	h.Sig = hex.EncodeToString(Sign(priv, []byte(h.Hash)))
	h.Pub = mb.Pub
	line, err := h.lineJSON()
	if err != nil {
		return nil, err
	}
	if err := appendLine(headPath(dir), line); err != nil {
		return nil, err
	}
	return h, nil
}

func isHexOf(s string, lens ...int) bool {
	for _, l := range lens {
		if len(s) == l {
			ok := true
			for i := 0; i < len(s); i++ {
				c := s[i]
				if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F') {
					ok = false
					break
				}
			}
			if ok {
				return true
			}
		}
	}
	return false
}

// ReadResult is one entry plus its readable face.
type ReadResult struct {
	Entry     *Entry
	Plaintext string // set when open, or sealed + reveal succeeded
	Withheld  string // set when sealed and reveal honestly refused
}

// Read walks a chain: actor "" reads the channel-head index; otherwise one
// actor's chain. last caps the tail (0 = all). reveal opens sealed entries
// for callers holding the ledger salt and the posting actor's key; anything
// missing withholds per entry, never failing the whole read.
func Read(dir, actor string, last int, reveal bool) ([]ReadResult, error) {
	path := headPath(dir)
	if actor != "" {
		path = filepath.Join(chainsDir(dir), actor+".jsonl")
	}
	lines, err := readLines(path)
	if err != nil {
		return nil, err
	}
	if last > 0 && len(lines) > last {
		lines = lines[len(lines)-last:]
	}
	ledger := map[string]map[string]string{}
	if reveal {
		for _, ln := range mustLines(ledgerPath(dir)) {
			var r map[string]string
			if json.Unmarshal([]byte(ln), &r) == nil && r["entry"] != "" {
				ledger[r["entry"]] = r
			}
		}
	}
	var out []ReadResult
	for _, ln := range lines {
		e, err := ParseLine(ln)
		if err != nil {
			return nil, err
		}
		rr := ReadResult{Entry: e}
		if e.Payload.Mode == ModeOpen {
			rr.Plaintext = e.Payload.Ct
		} else if reveal {
			rec, ok := ledger[e.Hash]
			if !ok {
				rr.Withheld = "no ledger salt for this entry"
			} else if key, err := KeyFromEnv(e.Actor); err != nil {
				rr.Withheld = err.Error()
			} else {
				pt, err := Open(SealKey(key), rec["salt"], e.Payload.Ct, rec["commitment"])
				if err != nil {
					rr.Withheld = err.Error()
				} else {
					rr.Plaintext = string(pt)
				}
			}
		} else {
			rr.Withheld = "sealed: ciphertext at rest — reveal to open"
		}
		out = append(out, rr)
	}
	return out, nil
}

func mustLines(path string) []string {
	lines, _ := readLines(path)
	return lines
}

// ChainVerdict rewalks every pen plus the head: EMPTY | INTACT | FLIP |
// TAMPER | FORGERY, the A1 vocabulary extended only by the signature's own
// refusal. Sound (appendable) requires INTACT everywhere with all sigs good.
type ChainVerdict struct {
	Overall string            `json:"overall"`
	Detail  string            `json:"detail"`
	Chains  map[string]string `json:"chains"`
	Sound   bool              `json:"sound"`
}

// Chain verifies the whole mesh ground: each actor chain and the head.
func Chain(dir string) (*ChainVerdict, error) {
	v := &ChainVerdict{Overall: "EMPTY", Chains: map[string]string{}}
	fps, err := filepath.Glob(filepath.Join(chainsDir(dir), "*.jsonl"))
	if err != nil {
		return nil, err
	}
	sort.Strings(fps)
	anyEntries := false
	worst := "INTACT"
	detail := "all pens intact, all signatures good"
	walk := func(name, path string) {
		lines, err := readLines(path)
		if err != nil || len(lines) == 0 {
			if err == nil {
				v.Chains[name] = "EMPTY"
			}
			return
		}
		anyEntries = true
		prev := Genesis
		for _, ln := range lines {
			e, perr := ParseLine(ln)
			if perr != nil {
				v.Chains[name] = "TAMPER: line is not JSON"
				worst, detail = "TAMPER", name+": line is not JSON"
				return
			}
			if verr := VerifyEntry(e, prev); verr != nil {
				msg := verr.Error()
				status := msg[:strings.Index(msg, " ")]
				v.Chains[name] = msg
				worst, detail = status, name+": "+msg
				return
			}
			prev = e.Hash
		}
		v.Chains[name] = fmt.Sprintf("INTACT (%d entries)", len(lines))
	}
	for _, fp := range fps {
		base := strings.TrimSuffix(filepath.Base(fp), ".jsonl")
		walk("actor/"+base, fp)
		if worst != "INTACT" {
			break
		}
	}
	if worst == "INTACT" {
		walk("head", headPath(dir))
	}
	if !anyEntries && v.Chains["head"] == "" {
		v.Overall, v.Detail, v.Sound = "EMPTY", "no mesh entries yet", true
		return v, nil
	}
	if worst != "INTACT" {
		v.Overall, v.Detail = worst, detail
		return v, nil
	}
	if h, ok := v.Chains["head"]; ok && h != "" && h != "EMPTY" && !strings.HasPrefix(h, "INTACT") {
		v.Overall, v.Detail = "TAMPER", "head: "+h
		return v, nil
	}
	v.Overall, v.Detail, v.Sound = "INTACT", detail, true
	return v, nil
}
