# Diff stats script
# Summarizes the uncommitted changes in a git repository: files changed, lines added and removed.
#
# Usage:
#   python scripts/diff_stats.py <repo-path>            # staged + unstaged changes vs HEAD
#   python scripts/diff_stats.py <repo-path> --staged   # staged changes only

import argparse
import json
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize uncommitted git changes.")
    parser.add_argument("repo", help="Path to the repository (or a folder inside it).")
    parser.add_argument("--staged", action="store_true", help="Only count staged changes.")
    args = parser.parse_args()

    diff_args = ["git", "diff", "--numstat"] + (["--cached"] if args.staged else ["HEAD"]) + ["--", "."]
    result = subprocess.run(diff_args, cwd=args.repo, capture_output=True, text=True)
    if result.returncode != 0:
        print(json.dumps({"error": result.stderr.strip() or "git diff failed"}))
        return

    files = []
    for line in result.stdout.splitlines():
        added, removed, path = line.split("\t", 2)
        binary = added == "-"
        files.append(
            {
                "path": path,
                "added": 0 if binary else int(added),
                "removed": 0 if binary else int(removed),
                "binary": binary,
            }
        )

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "."],
        cwd=args.repo,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    total = sum(f["added"] + f["removed"] for f in files)
    size = "small" if total < 50 else "medium" if total < 300 else "large"
    print(
        json.dumps(
            {
                "files": files,
                "untracked_files": [] if args.staged else untracked,
                "total_added": sum(f["added"] for f in files),
                "total_removed": sum(f["removed"] for f in files),
                "size": size,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
