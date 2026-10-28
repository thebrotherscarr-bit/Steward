# Code review checklist

Work through these in order; stop and report a finding as soon as one is confirmed.

## Correctness
- Does the change do what its commit message or the user says it does?
- Off-by-one, wrong comparison, inverted condition, wrong operator precedence.
- Edge cases: empty input, zero, negative numbers, None/null, very large values, unicode.
- Error handling: are errors caught too broadly, swallowed, or not handled at all?
- State: shared mutable defaults, globals, caching that goes stale.

## Interfaces
- Changed function signatures or return types: are all callers updated? (grep for the name)
- Changed behaviour that callers rely on, even when the signature is the same.

## Tests
- Is there a test that would fail without this change? If not, that is a test gap.
- Do the existing tests still pass? Run them rather than assuming.

## Risk
- Security: injection (SQL, shell, path), secrets in code or logs, unsafe deserialization.
- Performance: work inside loops that could move out, N+1 queries, unbounded reads.
- Concurrency: races on shared state, missing awaits, blocking calls in async code.

## Style (lowest priority)
- Matches the surrounding code's naming, structure and comment density.
- Dead code, debug prints, commented-out blocks left behind.
