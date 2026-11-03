---
name: github
description: Save and send work on your repository the user's way - a line of work, a commit, the send (push), the pull request and its checks - through Atlas's door, every write on the user's card. Use when the user asks to open a branch or line of work, send or push work, open or check a pull request, or "save and send".
---

## Usage

Your repository is the door's world `steward`. Every `atlas_*` call names `project="steward"`; any other world
is refused. The door's writes (opening a line, push, pull request open and merge) are held as cards in the
user's SecondBrain window: each waits for the user's Approve. Main is protected on GitHub: it changes only
through a pull request whose checks have passed, and the merge is the user's.

1. **Read first.** Call `atlas_git` with `project="steward"`: the line you are on, unsaved files, and whether it
   has been sent. Report it in one line.
2. **Never work on main.** If you are on main, open a line of work first:
   `atlas_git_branch` with `project="steward"`, `action="open"`, and a short name in kebab case that says what
   the work is (e.g. `fix-discount-rounding`). Wait for the user's Approve before anything else.
3. **Commit.** Your workflow's commit step uses your own `git_commit` tool, with a clear, imperative message that
   says what changed (never "update" or "changes"). Do not use `atlas_git_commit` for your own work.
4. **Send.** Only when the user asks to send: `atlas_git_push` with `project="steward"`. It is held for the
   user's Approve. Say that it is waiting.
5. **Pull request.** After the send is approved: `atlas_git_pr` with `project="steward"`, `action="open"`. Then
   `atlas_git_pr` with `action="list"` to read its checks (pending, passed or failed) and report them as given.
6. **Merge.** Only when the user says to merge, and only when its checks have passed: `atlas_git_pr` with
   `project="steward"`, `action="merge"` and the pull request's `number`. Otherwise the merge is the user's click.

Rules:
- One write at a time. A held call has not happened yet: never repeat it, never work around it, and never do
  the same thing with `run_shell` (no `git push`, `git commit`, `git checkout` or `git merge` in the shell).
- A refusal from the door names its reason (for example unsaved work, or main being protected). Report it
  exactly and stop; do not guess a way past it.
- Never put a name, byline or attribution in a commit message or a pull request.
