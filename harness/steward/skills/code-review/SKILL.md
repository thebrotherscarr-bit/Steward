---
name: code-review
description: Review uncommitted or staged code changes for bugs, risks and missing tests, using the size of the diff to scope the review. Use when the user asks to review changes, a diff, a branch, or "what I just wrote".
---

## Usage

When the user asks for a code review:

1. Get the workspace path from the `get_repo_status` tool (its `workspace` field) if you do not
   already have it.
2. Run `scripts/diff_stats.py` with the workspace path, e.g. `["C:\\Users\\you\\project"]`, to see
   which files changed and how many lines were added and removed (staged and unstaged). Add
   `--staged` to look at staged changes only.
3. Read `references/review-checklist.md`.
4. See exactly which lines changed in each file with run_shell, e.g.
   `git diff --relative HEAD -- sample-project/test_inventory.py` (use `--cached` for staged only).
   Then open each changed file with the file_access tools and read the changed regions in context,
   plus their callers when a signature or behaviour changed. Describe a change only from its diff.
5. Run the tests with run_shell exactly as the project's README says, from the README's own folder
   (e.g. `cd sample-project && <its command>`), and report the command you ran and its actual
   output.
6. Report findings ordered by severity (bug, risk, test gap, style). For each one give the file and
   line, what is wrong, a concrete failing scenario, and the fix. If nothing is wrong, say so.

Never report a finding you did not verify by reading the code.
