# Repository map script
# Prints a JSON map of a codebase: languages, top-level layout, entry points, tests and build files.
#
# Usage:
#   python scripts/repo_map.py <path>

import argparse
import json
from collections import Counter
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".mypy_cache", "target", "bin", "obj"}
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".cjs": "JavaScript", ".mjs": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".jsx": "JavaScript", ".go": "Go", ".rs": "Rust", ".cs": "C#", ".java": "Java",
    ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP", ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++",
    ".swift": "Swift", ".ps1": "PowerShell", ".sh": "Shell", ".sql": "SQL",
}
ENTRY_NAMES = {"main.py", "__main__.py", "cli.py", "app.py", "manage.py", "index.js", "index.ts", "main.ts",
               "main.go", "main.rs", "program.cs", "server.js", "server.ts"}
BUILD_NAMES = {"pyproject.toml", "setup.py", "requirements.txt", "package.json", "go.mod", "cargo.toml",
               "makefile", "dockerfile", "tsconfig.json", "pom.xml", "build.gradle"}


def is_test(path: Path) -> bool:
    name = path.name.lower()
    return (
        name.startswith("test_") or name.endswith(("_test.py", "_test.go", ".test.ts", ".test.js", ".spec.ts", ".spec.js"))
        or "tests" in path.parts or "test" in path.parts
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Map a codebase.")
    parser.add_argument("path", help="Folder to map.")
    args = parser.parse_args()
    root = Path(args.path).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"{root} is not a folder."}))
        return

    files = [p for p in root.rglob("*") if p.is_file() and not SKIP_DIRS.intersection(p.relative_to(root).parts)]
    lang_files: Counter[str] = Counter()
    lang_lines: Counter[str] = Counter()
    for p in files:
        lang = LANGUAGES.get(p.suffix.lower())
        if not lang:
            continue
        lang_files[lang] += 1
        try:
            lang_lines[lang] += sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
        except OSError:
            pass

    rel = lambda p: str(p.relative_to(root))  # noqa: E731
    top_level = sorted(
        (p.name + "/" if p.is_dir() else p.name) for p in root.iterdir() if p.name not in SKIP_DIRS
    )
    sources = [p for p in files if p.suffix.lower() in LANGUAGES and not is_test(p)]
    largest = sorted(sources, key=lambda p: p.stat().st_size, reverse=True)[:10]

    print(
        json.dumps(
            {
                "root": str(root),
                "total_files": len(files),
                "languages": [
                    {"language": lang, "files": n, "lines": lang_lines[lang]} for lang, n in lang_files.most_common()
                ],
                "top_level": top_level,
                "entry_points": sorted(rel(p) for p in files if p.name.lower() in ENTRY_NAMES),
                "build_and_config": sorted(
                    rel(p) for p in files if p.name.lower() in BUILD_NAMES or ".github" in p.parts
                ),
                "readmes": sorted(rel(p) for p in files if p.name.lower().startswith("readme")),
                "test_files": sorted(rel(p) for p in files if is_test(p) and p.suffix.lower() in LANGUAGES)[:50],
                "largest_source_files": [rel(p) for p in largest],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
