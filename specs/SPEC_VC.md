# SPEC_VC — .us → W3C Verifiable Credential adapter

*Bridges Atlas .us declarations to the W3C VC Data Model 2.0 for
cross-system trust and standards interop.*

---

## 1. Purpose

Organizations using .us declarations need to present agent identities to
external systems that speak W3C Verifiable Credentials (ADL, AAE, ATN).
This adapter converts a .us JSON block into a VC without losing the
structural gates that make .us unique.

## 2. Mapping: .us → VC

| .us field | VC field | Notes |
|---|---|---|
| `id` | `credentialSubject.id` | `did:atlas:<covenant>:<id>` |
| `kind` | `credentialSubject.type` | `"AgentDeclaration"` |
| `office` | `credentialSubject.office` | UPPERCASE office name |
| `can_approve` | `credentialSubject.canApprove` | Always `false` (structural gate) |
| `covenant` | `credentialSubject.covenant` | 16-char hex hash |
| `reports_to` | `credentialSubject.reportsTo` | Agent reference |
| `permission` | `credentialSubject.permissions` | Permission map |
| `role` | `credentialSubject.role` | Human-readable role |
| `source` | `credentialSubject.source` | Citation |
| (prose) | `credentialSubject.description` | The .us prose outside fences |
| — | `issuer` | `did:atlas:operator` |
| — | `issuanceDate` | Current timestamp (RFC3339) |
| — | `type` | `["VerifiableCredential", "AgentDeclaration"]` |
| — | `@context` | W3C VC context + Atlas extension |

## 3. DID scheme

Atlas DIDs follow the pattern:

```
did:atlas:<covenant_hash>:<agent_id>
```

Example: `did:atlas:1512741580b7239b:manjuel`

The covenant hash is the identity-of-record derived from foundation
documents. It binds the DID to the constitutional origin.

## 4. VC Structure

```json
{
  "@context": [
    "https://www.w3.org/2018/credentials/v1",
    "https://atlas.dev/credentials/v1"
  ],
  "type": ["VerifiableCredential", "AgentDeclaration"],
  "issuer": "did:atlas:1512741580b7239b:operator",
  "issuanceDate": "2026-09-07T00:00:00Z",
  "credentialSubject": {
    "id": "did:atlas:1512741580b7239b:manjuel",
    "type": "AgentDeclaration",
    "office": "MANJUEL",
    "canApprove": false,
    "covenant": "1512741580b7239b",
    "reportsTo": "did:atlas:1512741580b7239b:operator",
    "permissions": { ... },
    "role": "the living House heart",
    "source": "demo-vault Manjuel core/Archive/law/LAW_001+LAW_002",
    "description": "the living House heart - foundation five..."
  },
  "proof": {
    "type": "SchnorrSecp256k1Signature2025",
    "created": "2026-09-07T00:00:00Z",
    "verificationMethod": "did:atlas:1512741580b7239b:operator#key-1",
    "proofPurpose": "assertionMethod",
    "proofValue": "base64url-encoded-signature"
  }
}
```

## 5. Atlas extension context

```json
{
  "@context": {
    "atlas": "https://atlas.dev/credentials/v1",
    "AgentDeclaration": "atlas:AgentDeclaration",
    "canApprove": "atlas:canApprove",
    "covenant": "atlas:covenant",
    "office": "atlas:office"
  }
}
```

## 6. Tool surface

```
us_to_vc --us <file.us> [--sign] [--key-env MESH_KEY_OPERATOR] [--out <file.json>]
```

- `--us` — input .us file
- `--sign` — sign the VC with the operator's key (optional)
- `--key-env` — env var name for the signing key (default: `MESH_KEY_OPERATOR`)
- `--out` — output file (default: stdout)

## 7. Trust model

- The VC is a **representation** of the .us declaration, not a replacement.
- The .us file remains the source of truth; the VC is a cross-system bridge.
- Signing is optional; unsigned VCs carry structural trust (canApprove:false)
  while signed VCs carry cryptographic trust.
- Verification checks: signature valid, issuer known, canApprove:false.

## 8. Prove requirements

- Parse .us → extract block → map to VC → output valid JSON-LD.
- Round-trip: parse VC → extract credentialSubject → matches .us block.
- Sign → verify: signature verifies against the operator's public key.
- canApprove is always false in the VC; presence of true is a refusal.
