---
name: code-review
description: Review uncommitted or staged code changes for bugs, risks and missing tests, using the size of the diff to scope the review. Use when the user asks to review changes, a diff, a branch, or "what I just wrote".
---

## Usage

When the user asks for a code review:

1. Run `scripts/diff_stats.py` with the workspace path, e.g. `["<workspace>"]`, to see which files
   changed and how many lines were added and removed (staged and unstaged). Add `--staged` to look
   at staged changes only.
2. Read `references/review-checklist.md`.
3. Open each changed file with the file_access tools and read the changed regions in context, plus
   their callers when a signature or behaviour changed.
4. Report findings ordered by severity (bug, risk, test gap, style). For each one give the file and
   line, what is wrong, a concrete failing scenario, and the fix. If nothing is wrong, say so.

Never report a finding you did not verify by reading the code.
