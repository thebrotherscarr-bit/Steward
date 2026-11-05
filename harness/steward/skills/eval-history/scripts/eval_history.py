# Eval history script
# Compares the last runs of one eval set from storage/evals/history.jsonl (written by evals.py's record_history) and
# prints, as JSON, each run's counts and which checks flipped between the last two runs. A read only.
#
# Usage:
#   python scripts/eval_history.py                 # the set of the newest run, its last 2 runs
#   python scripts/eval_history.py small --runs 5  # the "small" set, its last 5 runs
#   python scripts/eval_history.py --file <path>   # another history file

import argparse
import json
from pathlib import Path

HISTORY = Path(__file__).resolve().parents[5] / "storage" / "evals" / "history.jsonl"


def failed_checks(run: dict) -> dict[str, set[str]]:
    """Each case (its step, if any, and input) and the names of its failed checks; a case missing from the run is absent."""
    return {
        f"{case['step']}: {case.get('input', '')}" if case.get("step") else case.get("input", ""):
        {check.get("name", "") for check in case.get("failed_checks") or []}
        for case in run.get("cases") or []
    }


def flips(before: dict, after: dict) -> list[dict]:
    """The checks that changed between two runs of a set, case by case (a check not listed as failed passed)."""
    old, new = failed_checks(before), failed_checks(after)
    changed = []
    for case in sorted(old.keys() & new.keys()):
        for name in sorted(new[case] - old[case]):
            changed.append({"case": case, "check": name, "now": "fail"})
        for name in sorted(old[case] - new[case]):
            changed.append({"case": case, "check": name, "now": "pass"})
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare the last runs of an eval set.")
    parser.add_argument("set", nargs="?", help="The set's name (small, steps, heldout, memory, regression); default the newest run's.")
    parser.add_argument("--runs", type=int, default=2, help="How many of its last runs to list (2 to 20).")
    parser.add_argument("--file", default=str(HISTORY), help="The history file.")
    args = parser.parse_args()
    path = Path(args.file)
    if not path.is_file():
        print(json.dumps({"error": f"No eval history at {path}: no set has been run yet."}))
        return
    runs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            runs.append(json.loads(line))
        except ValueError:
            continue
    if not runs:
        print(json.dumps({"error": f"The eval history at {path} holds no runs."}))
        return
    name = args.set or runs[-1].get("set")
    mine = [run for run in runs if run.get("set") == name]
    if not mine:
        print(json.dumps({"error": f"No run of the set {name!r}.", "sets": sorted({str(run.get('set')) for run in runs})}))
        return
    last = mine[-max(2, min(args.runs, 20)):]
    report = {
        "set": name,
        "runs": [
            {
                "ts": run.get("ts"), "set_version": run.get("set_version"), "tier": run.get("tier"),
                "passed": run.get("passed"), "total": run.get("total"),
                "checks_passed": run.get("checks_passed"), "checks_total": run.get("checks_total"),
                "git_head": run.get("git_head"), "model": run.get("model"),
                "options": (run.get("options") or {}).get("name"),
                "failed": [f"{case} / {check}" for case, checks in failed_checks(run).items() for check in sorted(checks)],
            }
            for run in last
        ],
        "flipped": flips(last[-2], last[-1]) if len(last) > 1 else [],
    }
    if len(last) < 2:
        report["note"] = "Only one run of this set: nothing to compare yet."
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
