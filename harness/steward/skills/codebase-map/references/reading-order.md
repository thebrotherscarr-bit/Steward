# Reading order for an unfamiliar codebase

1. **README and docs** — what the project claims to be and how to run it.
2. **Build and dependency files** — `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`,
   `*.csproj`, `Makefile`, CI workflows. They tell you the language, the entry points, and the real
   build and test commands (trust these over the README when they disagree).
3. **Entry points** — `main.py`, `__main__.py`, `cli.py`, `index.ts`, `main.go`, `Program.cs`,
   `src/main.rs`, server start files. Follow the first few calls to find the core modules.
4. **Core domain modules** — the code the entry points call into; usually the largest non-test
   source files.
5. **Tests** — they show intended behaviour and how components are used. Read the test for a module
   right after the module.
6. **Glue and infrastructure last** — config loading, logging, utilities.

When a codebase has several large modules, explore them in parallel (one per explorer) and then
reconcile: how does data flow from the entry point through the modules?
