# Telemetry script
# Summarises the newest spans in halo_traces/traces.jsonl (written by halo_traces.py's HaloJsonlSpanExporter): the
# runs, the model calls, the tool calls and the errors. It reads only the file's tail (--kb, at most 4096 KB), never the
# whole file, which grows past 100 MB. A read only.
#
# Usage:
#   python scripts/telemetry.py                  # the last 1024 KB
#   python scripts/telemetry.py --kb 4096        # more of the tail
#   python scripts/telemetry.py --file <path>    # another traces file

import argparse
import json
import os
from collections import Counter
from pathlib import Path

TRACES = Path(__file__).resolve().parents[5] / "halo_traces" / "traces.jsonl"
MAX_KB = 4096


def tail_lines(path: Path, kb: int) -> list[str]:
    """The whole lines in the file's last kb kilobytes (a line cut by the start is dropped)."""
    size = path.stat().st_size
    start = max(0, size - kb * 1024)
    with path.open("rb") as handle:
        handle.seek(start)
        data = handle.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    return lines[1:] if start > 0 and lines else lines


def summarise(lines: list[str]) -> dict:
    spans = []
    for line in lines:
        try:
            span = json.loads(line)
        except ValueError:
            continue
        if isinstance(span, dict):
            spans.append(span)
    if not spans:
        return {"spans": 0}
    runs = Counter()
    models = Counter()
    tools = Counter()
    errors = []
    for span in spans:
        name = str(span.get("name", ""))
        attributes = span.get("attributes") or {}
        operation = attributes.get("gen_ai.operation.name")
        if name == "workflow.run":
            runs[f"workflow {attributes.get('workflow.name', '?')}"] += 1
        elif operation == "invoke_agent":
            runs[f"agent {attributes.get('gen_ai.agent.name', '?')}"] += 1
        elif operation == "chat":
            models[str(attributes.get("gen_ai.request.model", "?"))] += 1
        elif operation == "execute_tool":
            tools[str(attributes.get("gen_ai.tool.name", "?"))] += 1
        status = span.get("status") or {}
        if status.get("code") == "STATUS_CODE_ERROR":
            errors.append({"span": name, "at": span.get("end_time"), "error": str(status.get("message", ""))[:200]})
    times = sorted(t for span in spans for t in (span.get("start_time"), span.get("end_time")) if t)
    return {
        "spans": len(spans),
        "from": times[0] if times else None,
        "to": times[-1] if times else None,
        "runs": dict(runs.most_common()),
        "model_calls": dict(models.most_common()),
        "tool_calls": dict(tools.most_common(25)),
        "errors": len(errors),
        "last_errors": errors[-10:],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise the newest spans of Steward's traces.")
    parser.add_argument("--kb", type=int, default=1024, help=f"How much of the tail to read, in KB (at most {MAX_KB}).")
    parser.add_argument("--file", default=os.environ.get("HALO_TRACE_PATH") or str(TRACES), help="The traces file.")
    args = parser.parse_args()
    path = Path(args.file)
    if not path.is_file():
        print(json.dumps({"error": f"No traces at {path}."}))
        return
    kb = max(1, min(args.kb, MAX_KB))
    report = {"file": str(path), "file_mb": round(path.stat().st_size / 1_048_576, 1), "read_kb": kb}
    report.update(summarise(tail_lines(path, kb)))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
