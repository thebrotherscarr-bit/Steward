// Package vc converts .us declarations to W3C Verifiable Credentials.
// Bridges the .us structural trust model to the cross-system VC ecosystem.
package vc

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"strings"
	"time"
)

// VC is a W3C Verifiable Credential 2.0.
type VC struct {
	Context           []string          `json:"@context"`
	Type              []string          `json:"type"`
	Issuer            string            `json:"issuer"`
	IssuanceDate      string            `json:"issuanceDate"`
	CredentialSubject CredentialSubject `json:"credentialSubject"`
	Proof             *Proof            `json:"proof,omitempty"`
}

// CredentialSubject carries the .us declaration mapped to VC fields.
type CredentialSubject struct {
	ID          string         `json:"id"`
	Type        string         `json:"type"`
	Office      string         `json:"office"`
	CanApprove  bool           `json:"canApprove"`
	Covenant    string         `json:"covenant"`
	ReportsTo   string         `json:"reportsTo"`
	Permissions map[string]any `json:"permissions,omitempty"`
	Role        string         `json:"role,omitempty"`
	Source      string         `json:"source,omitempty"`
	Description string         `json:"description,omitempty"`
}

// Proof is an optional cryptographic proof.
type Proof struct {
	Type               string `json:"type"`
	Created            string `json:"created"`
	VerificationMethod string `json:"verificationMethod"`
	Purpose            string `json:"proofPurpose"`
	ProofValue         string `json:"proofValue,omitempty"`
}

// ParseUS extracts the first JSON block from a .us file.
func ParseUS(text string) (map[string]any, string, error) {
	lines := strings.Split(text, "\n")
	inside := false
	var buf []string
	var proseLines []string

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if !inside && strings.HasPrefix(trimmed, "```") {
			candidate := strings.TrimSpace(trimmed[3:])
			lower := strings.ToLower(candidate)
			if lower == "json" || lower == "us" || lower == "json us" {
				inside = true
				continue
			}
		}
		if inside && trimmed == "```" {
			break
		}
		if inside {
			buf = append(buf, line)
		} else {
			proseLines = append(proseLines, line)
		}
	}

	if len(buf) == 0 {
		return nil, "", fmt.Errorf("no JSON block found in .us document")
	}

	var block map[string]any
	if err := json.Unmarshal([]byte(strings.Join(buf, "\n")), &block); err != nil {
		return nil, "", fmt.Errorf("invalid JSON in .us block: %w", err)
	}

	return block, strings.TrimSpace(strings.Join(proseLines, "\n")), nil
}

var idPattern = regexp.MustCompile(`^[a-z][a-z0-9_]*$`)

// ToVC converts a .us JSON block to a W3C Verifiable Credential.
func ToVC(block map[string]any, prose string, issuerDID string) (*VC, error) {
	// Validate can_approve
	canApprove, ok := block["can_approve"].(bool)
	if !ok {
		return nil, fmt.Errorf("can_approve must be explicitly stated as false")
	}
	if canApprove {
		return nil, fmt.Errorf("can_approve must be false; true is refused")
	}

	// Extract fields
	id, _ := block["id"].(string)
	if !idPattern.MatchString(id) {
		return nil, fmt.Errorf("invalid id format: %q", id)
	}
	covenant, _ := block["covenant"].(string)
	office, _ := block["office"].(string)
	reportsTo, _ := block["reports_to"].(string)
	role, _ := block["role"].(string)
	source, _ := block["source"].(string)

	// Build DID
	did := fmt.Sprintf("did:atlas:%s:%s", covenant, id)

	// Map permissions
	var permissions map[string]any
	if p, ok := block["permission"].(map[string]any); ok {
		permissions = make(map[string]any)
		for k, v := range p {
			permissions[k] = v
		}
	}

	// Build reportsTo DID
	reportsToDID := ""
	if reportsTo != "" {
		reportsToDID = fmt.Sprintf("did:atlas:%s:%s", covenant, reportsTo)
	}

	vc := &VC{
		Context: []string{
			"https://www.w3.org/2018/credentials/v1",
			"https://atlas.dev/credentials/v1",
		},
		Type:         []string{"VerifiableCredential", "AgentDeclaration"},
		Issuer:       issuerDID,
		IssuanceDate: time.Now().UTC().Format(time.RFC3339),
		CredentialSubject: CredentialSubject{
			ID:          did,
			Type:        "AgentDeclaration",
			Office:      office,
			CanApprove:  canApprove,
			Covenant:    covenant,
			ReportsTo:   reportsToDID,
			Permissions: permissions,
			Role:        role,
			Source:      source,
			Description: prose,
		},
	}

	return vc, nil
}

// ToJSON serializes the VC to indented JSON.
func ToJSON(vc *VC) ([]byte, error) {
	return json.MarshalIndent(vc, "", "  ")
}

// FromFile reads a .us file and converts it to a VC.
func FromFile(path string, issuerDID string) (*VC, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	block, prose, err := ParseUS(string(data))
	if err != nil {
		return nil, err
	}
	return ToVC(block, prose, issuerDID)
}

// Verify checks a VC for structural validity.
func Verify(vc *VC) []string {
	var errs []string

	// Check canApprove
	if vc.CredentialSubject.CanApprove {
		errs = append(errs, "canApprove must be false")
	}

	// Check required fields
	if vc.CredentialSubject.ID == "" {
		errs = append(errs, "credentialSubject.id is required")
	}
	if vc.CredentialSubject.Covenant == "" {
		errs = append(errs, "credentialSubject.covenant is required")
	}
	if vc.CredentialSubject.Office == "" {
		errs = append(errs, "credentialSubject.office is required")
	}
	if vc.Issuer == "" {
		errs = append(errs, "issuer is required")
	}

	// Check DID format
	if vc.CredentialSubject.ID != "" && !strings.HasPrefix(vc.CredentialSubject.ID, "did:atlas:") {
		errs = append(errs, "credentialSubject.id must be a did:atlas: URI")
	}

	return errs
}
