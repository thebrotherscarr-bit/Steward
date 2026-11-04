---
name: github
description: Save and send work on the estate's repositories the user's way - a line of work, a commit, the send (push), the pull request and its checks - through Atlas's door, every write on the user's card. Use when the user asks to open a branch or line of work, send or push work, open or check a pull request, or "save and send", on your own repository or another part of the estate.
---

## Usage

The door addresses each repository by its `project`: `steward` (yours), `research` (Manjuel, the ground), `atlas`
(Aurora), `secondbrain` (Jesster) and `neiro` (the Estate lock; the door does not carry it yet and says so). Every
`atlas_*` call names one of them; any other, or none, is refused. Use `steward` unless the user names another part.
The door's writes (opening a line, push, pull request open and merge) are held as cards in the user's SecondBrain
window: each waits for the user's Approve. Main is protected on GitHub: it changes only through a pull request whose
checks have passed.

1. **Read first.** Call `atlas_git` with the `project`: the line you are on, unsaved files, and whether it has been
   sent. Report it in one line. For `research`, call `secondbrain_estate_status` too: while a Manjuel sitting is
   open (RULE 9) nothing in the ground is committed or sent. Say so and stop.
2. **Never work on main.** If you are on main, open a line of work first: `atlas_git_branch` with the `project`,
   `action="open"`, and a short name in kebab case that says what the work is (e.g. `fix-discount-rounding`).
   Wait for the user's Approve before anything else.
3. **Commit.** On your own repository your workflow's commit step uses your own `git_commit` tool. On another
   repository use `atlas_git_commit` with the `project`, the `message` and the `files`, one per line. The message
   is clear and imperative and says what changed (never "update" or "changes").
4. **Send.** Only when the user asks to send: `atlas_git_push` with the `project`. It is held for the user's
   Approve. Say that it is waiting.
5. **Pull request.** After the send is approved: `atlas_git_pr` with the `project`, `action="open"`. Then, before
   you report, call `pr_checks` with your `line` and the `project`: it waits for the user's Approve and for the
   checks, and returns passed, failed, closed or timed_out. Report that as given.
6. **Merge.** Only when the user says to merge, and only when its checks have passed: `atlas_git_pr` with the
   `project`, `action="merge"` and the pull request's `number`. Otherwise the merge is the user's click.

Never, on any repository (refused before any card):
- a force-push, a push of `--all` or `--mirror`, a tag, a release, or rewriting history (rebase, amend,
  filter-branch);
- closing or deleting main;
- any path under `Desktop\Archive`. The Archive never goes on GitHub.

Rules:
- One write at a time. A held call has not happened yet: never repeat it, never work around it, and never do
  the same thing with `run_shell` (no `git push`, `git commit`, `git checkout` or `git merge` in the shell).
- A refusal names its reason (for example unsaved work, an open sitting, or main being protected). Report it
  exactly and stop; do not guess a way past it.
- Never put a name, byline or attribution in a commit message or a pull request.
