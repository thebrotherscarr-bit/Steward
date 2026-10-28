---
name: codebase-map
description: Build a map of an unfamiliar codebase — languages, size, layout, entry points, tests and build files — and a reading order for understanding it. Use when the user asks what a repo is, how it is structured, where to start, or before a large change.
---

## Usage

When the user asks to understand or map a codebase:

1. Run `scripts/repo_map.py` with the path to map, e.g. `["<workspace>"]`. It prints languages by
   file count and lines, the top-level layout, likely entry points, test files, and build or
   config files.
2. Read `references/reading-order.md` and pick a reading order from the map.
3. Open the entry points and build files with the file_access tools to confirm what the project is
   and how it runs and is tested. For several large modules, delegate each to the background
   CodeExplorer agent.
4. Report: what the project is, how to build/run/test it, the main modules and how they connect,
   and the order to read it in. Name real files only.
