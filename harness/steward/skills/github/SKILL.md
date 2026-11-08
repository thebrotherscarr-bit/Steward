---
name: github
description: Read the estate's repositories on GitHub through Atlas's door - the line each is on, unsaved and unsent work, the diff, the record, and a pull request's checks - and answer GitHub write requests (open a branch or line of work, commit on another repository, push or send, open or merge a pull request) by saying the hand does them for now. Use when the user asks about a repository's state, its pull requests or their checks, or asks to branch, push, send, open or merge on GitHub, on your own repository or another part of the estate.
---

## Usage

The door addresses each repository by its `project`: `steward` (yours), `research` (Manjuel, the ground), `atlas`
(Aurora) and `secondbrain` (Jesster). Neiro, the Estate lock, is retired (2026-11-05, archived read-only): the
Estate's versions come from `secondbrain_estate_status`, and each repository's own checks are its gate. Every
`atlas_*` call names one of them; any other, or none, is refused. Use `steward` unless the user names another part.

**GitHub writes are withheld from you for now** (2026-11-08, the operator: "when he has passed reliably, he can gain
the tools to control github"). You have no tool to open a line of work on the door, commit on another repository,
push, or open or merge a pull request. Your own workflow's commit step (`git_commit`, on your own workspace) is not
a GitHub write and stays yours.

1. **Read.** Call `atlas_git` with the `project`: the line it is on, unsaved files, and whether it has been sent.
   `atlas_git_diff` shows what changed; `atlas_records` the record. Report it in a few lines. For `research`, call
   `secondbrain_estate_status` too: while a Manjuel sitting is open (RULE 9) say so.
2. **A pull request's checks.** `pr_checks` with the `line` or the `number` and the `project` waits for its checks
   and returns passed, failed, closed or timed_out. Report that as given. It never opens, approves or merges.
3. **A write asked for** (a branch or line of work, a push or send, a pull request opened or merged, a commit on
   another repository): answer in words, with no plan and no card, that GitHub writes are withheld from you for
   now and the hand does them; say what you read (step 1) if it helps. Call no tool to do it.

Never, on any repository:
- a write through the shell instead: no `git push`, `git commit`, `git checkout`, `git branch` or `git merge` in
  `run_shell` on a repository of the estate, and never a way around the withholding;
- a force-push, a tag, a release, or rewriting history (rebase, amend, filter-branch); closing or deleting main;
- any path under `Desktop\Archive`. The Archive never goes on GitHub.

Rules:
- A refusal names its reason. Report it exactly and stop; do not guess a way past it.
- Never put a name, byline or attribution in a commit message or a pull request.
