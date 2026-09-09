// Package guard is F1-02: the Guard/Redact/Scan pipeline over ask packs.
//
// GUARD ports the gatehouse pokes (neiro/gatehouse.py _POKES, verbatim):
// injection attempts are BLOCKED with the gate's own plain words. REDACT
// strips PII (specified classes, golden-pinned — the oracle has no
// redactor). SCAN flags mechanical poison markers (specified, pinned).
// Order is load-bearing: guard, then redact, then scan.
//
// What the oracle does NOT port: the 600-char clamp belongs to chat
// vestibules, not the rack — asks carry full questions. The trust
// floors/ledger book belong to tool calls, not questions.
package guard

import (
	"regexp"
	"strings"
)

// pokes: not obeyed, only flagged — then blocked at the rack door. Verbatim
// from the oracle (case-insensitive).
var pokeRes = []string{
	`ignore (all |your |the )?(previous|prior|above|earlier|instructions|rules|prompt)`,
	`disregard (all |your |the )?(previous|prior|above|instructions|rules|prompt)`,
	`forget (your|the|all) (instructions|rules|prompt)`,
	`you are now\b`,
	`pretend (you|to be)\b`,
	`\bact as\b`,
	`system prompt`,
	`(reveal|tell me|show me|what.?s) your (prompt|instructions|rules|key|seed|covenant|private)`,
	`developer mode`,
	`jailbreak`,
	`\bsudo\b`,
	`drop the (seal|gate|wall)`,
	`bypass (the |your )?(gate|seal|rule|wall)`,
	`override (the |your )?(gate|seal|owner|rule)`,
}

var pokeRe = regexp.MustCompile(`(?i)(?:` + strings.Join(pokeRes, ")|(?:") + `)`)

// GateWords are the gate's own plain refusal, quoted (not paraphrased).
const GateWords = "I read that as an attempt to move my gate. I don't have one " +
	"you can talk around - I answer from the record, and I only " +
	"act for my owner. Ask me something and I'll tell you true."

// Guard blocks injection attempts, naming the match like the oracle's
// "matched:" receipts.
func Guard(text string) (blocked bool, match string) {
	m := pokeRe.FindString(text)
	return m != "", m
}

var (
	emailRe = regexp.MustCompile(`[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`)
	ssnRe   = regexp.MustCompile(`\b\d{3}-\d{2}-\d{4}\b`)
	cardRe  = regexp.MustCompile(`\b(?:\d[ -]?){12,18}\d\b`)
	keyRe   = regexp.MustCompile(`\b(sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._~+/-]{16,}|xox[bap]-[A-Za-z0-9-]{10,})\b`)
	phoneRe = regexp.MustCompile(`\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b`)
)

// Redact strips PII classes in the golden order (email, ssn, card, key,
// phone — a card holds phone-shaped runs, so cards first).
func Redact(text string) string {
	text = emailRe.ReplaceAllString(text, "[redacted:email]")
	text = ssnRe.ReplaceAllString(text, "[redacted:ssn]")
	text = cardRe.ReplaceAllString(text, "[redacted:card]")
	text = keyRe.ReplaceAllString(text, "[redacted:key]")
	return phoneRe.ReplaceAllString(text, "[redacted:phone]")
}

var (
	zwRe   = regexp.MustCompile("[\u200b-\u200f\ufeff]")
	bidiRe = regexp.MustCompile("[\u202a-\u202e\u2066-\u2069]")
	b64Re  = regexp.MustCompile(`[A-Za-z0-9+/=]{60,}`)
)

// Scan flags mechanical poison markers (fixtures pin them). Flags report;
// blocking is the guard's job, not the scan's.
func Scan(text string) []string {
	var flags []string
	if zwRe.MatchString(text) {
		flags = append(flags, "zero-width")
	}
	if bidiRe.MatchString(text) {
		flags = append(flags, "bidi-override")
	}
	if b64Re.MatchString(text) {
		flags = append(flags, "b64-blob")
	}
	return flags
}

// Pipeline runs guard, then redact, then scan. Blocked injections refuse
// with the gate's words; everything else continues cleaned and flagged.
func Pipeline(text string) (clean string, flags []string, blocked bool, reason string) {
	if blocked, match := Guard(text); blocked {
		return "", nil, true, GateWords + " (matched: \"" + match + "\")"
	}
	clean = Redact(text)
	return clean, Scan(clean), false, ""
}
