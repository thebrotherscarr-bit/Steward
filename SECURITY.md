# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability in ATLAS, please report it responsibly:

1. **Do NOT** open a public GitHub Issue
2. Email the maintainer directly (see package.json or Cargo.toml for contact)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Scope

ATLAS is a governance and provenance system. Security-relevant areas:

- **Chain integrity**: SHA-256 hashing of traces — tampering detection
- **Append-only enforcement**: Fold, never delete — audit trail integrity
- **Structural governance**: `can_approve: false` — no agent can self-approve
- **Multi-tenancy**: Strangers refused by name — no cross-project leakage
- **Zero dependencies**: No supply chain attacks from external packages
- **Secrets handling**: Never logged, never committed, never displayed

## Response

- Acknowledge receipt within 48 hours
- Provide assessment within 7 days
- Coordinate disclosure with maintainer

## Scope Limitations

ATLAS is alpha software (0.1.x). It is not designed for:
- Production workloads requiring SOC 2 compliance
- Environments with untrusted network access
- Systems requiring authentication/authorization beyond operator gate

## Hardening Checklist

- [ ] All `.us` files validated (`atlas agent enroll --dry`)
- [ ] No secrets in source code
- [ ] No external dependencies
- [ ] All tests pass
- [ ] Prove chain unbroken
- [ ] Forbidden verbs absent by construction
