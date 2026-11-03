---
name: run-tests
description: Run a project's tests in the workspace with pytest and report the actual result. Use when the user asks you to run the tests, check that something passes, or see which test fails.
---

## Usage

This skill has no script: run the tests with the run_shell tool, as below.

1. Find the tests: the folder the user named, or the folder of the code in question. Test files are named
   `test_*.py`; list them with the file_access tools first.
2. Run them once with the run_shell tool, from the workspace root:
   `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <folder or file>`
   To run one test, add `-k <name>`.
3. Report the summary line exactly as printed (for example `3 passed, 1 failed in 0.4s`), then each failing
   test's name and the lines of its error that say why. Never report a result the output did not show.
4. Run them once per request. If something fails, explain the cause from the output and the code; do not run
   them again hoping for a different result.
5. Do not change any file while running tests. A fix is a separate change, planned and approved.

Notes:
- Your own harness suite is `harness/steward/step04_production_ready/test_harness.py`. It sets
  `STEWARD_CHECK_RUNNING` itself, so it never starts your workflow's check inside itself.
- Your workflow's check runs the tests of every changed file by itself after you write code; you do not need to
  run them again for that.
