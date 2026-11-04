"""Traces for the improvement loop (OpenAI cookbook "agent improvement loop", step 2: Traces).

The cookbook registers ``HaloJsonlTraceProcessor`` with the Agents SDK: every finished span is
converted by ``span_to_halo_jsonl_line`` and appended as one compact JSON line to
``halo_traces/traces.jsonl``, in the OpenTelemetry-style shape HALO reads later.

Steward runs on Microsoft Agent Framework, which already emits OpenTelemetry GenAI spans
(``invoke_agent``, ``chat``, ``execute_tool``). So the processor here is an OpenTelemetry
``SpanExporter`` that writes the same line shape, mapping MAF's ``gen_ai.*`` attributes onto the
cookbook's keys:

    invoke_agent -> AGENT  (agent.name)
    chat         -> LLM    (llm.provider, llm.model_name, messages, llm.token_count.*)
    execute_tool -> TOOL   (tool.name, input.value, output.value)
    anything else-> CHAIN  (sdk.span.type, sdk.span.name)

Message and tool content is captured (``enable_sensitive_data``), as the cookbook's traces carry
inputs and outputs. The file stays on this PC: ``halo_traces/`` is gitignored.

The file is capped (Kyle, 2026-11-01: "cut the traces file down to a 100MB max"; it had reached 988 MB): when a
write takes it past HALO_TRACE_MAX_BYTES, the oldest spans are dropped and the newest half is kept, from a whole line.

Environment variables:
    HALO_TRACE_PATH — where to write (defaults to <repo>/halo_traces/traces.jsonl)
    HALO_TRACE_MAX_BYTES — the cap (defaults to 100 MB)
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_framework.observability import configure_otel_providers
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind, StatusCode

_REPO_DIR = Path(__file__).resolve().parents[3]
HALO_TRACE_PATH = Path(os.environ.get("HALO_TRACE_PATH") or _REPO_DIR / "halo_traces" / "traces.jsonl")
HALO_TRACE_MAX_BYTES = int(os.environ.get("HALO_TRACE_MAX_BYTES") or 100 * 1024 * 1024)


def keep_newest(path: Path, keep_bytes: int) -> None:
    """Cut the file to its newest ``keep_bytes`` or less, from the first whole line; in place, so a process that
    holds it open for appending keeps appending at the new end."""
    with path.open("r+b") as f:
        size = f.seek(0, os.SEEK_END)
        if size <= keep_bytes:
            return
        f.seek(size - keep_bytes)
        tail = f.read()
        start = tail.find(b"\n")
        tail = tail[start + 1 :] if start >= 0 else b""
        f.seek(0)
        f.write(tail)
        f.truncate()

_SCHEMA_VERSION = 1
_PROJECT_ID = "steward"


def _timestamp(ns: int | None) -> str | None:
    if ns is None:
        return None
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _hex(value: int, width: int) -> str:
    return format(value, f"0{width}x")


def _json_or_raw(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _expand_messages(prefix: str, raw: Any, out: dict[str, Any]) -> None:
    """The cookbook's expanded ``llm.<input|output>_messages.<i>.message.*`` keys."""
    messages = _json_or_raw(raw)
    if not isinstance(messages, list):
        return
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        out[f"{prefix}.{i}.message.role"] = message.get("role")
        parts = message.get("parts") or []
        text = "".join(p.get("content", "") for p in parts if isinstance(p, dict) and p.get("type") == "text")
        if text:
            out[f"{prefix}.{i}.message.content"] = text
        calls = [p for p in parts if isinstance(p, dict) and p.get("type") == "tool_call"]
        for j, call in enumerate(calls):
            out[f"{prefix}.{i}.message.tool_calls.{j}.tool_call.function.name"] = call.get("name")
            out[f"{prefix}.{i}.message.tool_calls.{j}.tool_call.function.arguments"] = json.dumps(call.get("arguments"))


def span_to_halo_jsonl_line(span: ReadableSpan, resource_attributes: dict[str, Any]) -> dict[str, Any]:
    """One finished MAF span as the cookbook's HALO JSONL line."""
    attrs = dict(span.attributes or {})
    operation = str(attrs.get("gen_ai.operation.name") or "")
    ctx = span.get_span_context()

    out: dict[str, Any] = {
        "inference.export.schema_version": _SCHEMA_VERSION,
        "inference.project_id": _PROJECT_ID,
        "inference.observation_kind": operation or "span",
        "inference.llm.provider": attrs.get("gen_ai.provider.name") or attrs.get("gen_ai.system"),
        "inference.llm.model_name": attrs.get("gen_ai.response.model") or attrs.get("gen_ai.request.model"),
        "inference.llm.input_tokens": attrs.get("gen_ai.usage.input_tokens"),
        "inference.llm.output_tokens": attrs.get("gen_ai.usage.output_tokens"),
        "inference.session_id": attrs.get("gen_ai.conversation.id"),
        "inference.agent_name": attrs.get("gen_ai.agent.name"),
    }

    if operation in ("invoke_agent", "create_agent"):
        out["openinference.span.kind"] = "AGENT"
        out["agent.name"] = attrs.get("gen_ai.agent.name")
        tools = _json_or_raw(attrs.get("gen_ai.tool.definitions"))
        if isinstance(tools, list):
            out["agent.tools"] = json.dumps([t.get("name") for t in tools if isinstance(t, dict)])
        out["agent.output_type"] = attrs.get("gen_ai.output.type")
    elif operation == "chat":
        out["openinference.span.kind"] = "LLM"
        out["llm.provider"] = out["inference.llm.provider"]
        out["llm.model_name"] = out["inference.llm.model_name"]
        out["llm.input_messages"] = attrs.get("gen_ai.input.messages")
        out["llm.output_messages"] = attrs.get("gen_ai.output.messages")
        _expand_messages("llm.input_messages", attrs.get("gen_ai.input.messages"), out)
        _expand_messages("llm.output_messages", attrs.get("gen_ai.output.messages"), out)
        prompt, completion = attrs.get("gen_ai.usage.input_tokens"), attrs.get("gen_ai.usage.output_tokens")
        out["llm.token_count.prompt"] = prompt
        out["llm.token_count.completion"] = completion
        if isinstance(prompt, int) and isinstance(completion, int):
            out["llm.token_count.total"] = prompt + completion
    elif operation == "execute_tool":
        out["openinference.span.kind"] = "TOOL"
        out["tool.name"] = attrs.get("gen_ai.tool.name")
        out["input.value"] = attrs.get("gen_ai.tool.call.arguments")
        out["output.value"] = attrs.get("gen_ai.tool.call.result")
        out["tool.call_id"] = attrs.get("gen_ai.tool.call.id")
    else:
        out["openinference.span.kind"] = "CHAIN"
        out["sdk.span.type"] = operation or "custom"
        out["sdk.span.name"] = span.name

    # Everything MAF recorded rides along under its own name, so nothing is lost to the mapping.
    for key, value in attrs.items():
        out.setdefault(key, value)

    kind = "SPAN_KIND_CLIENT" if span.kind == SpanKind.CLIENT or operation == "chat" else "SPAN_KIND_INTERNAL"
    error = span.status.status_code == StatusCode.ERROR
    return {
        "trace_id": _hex(ctx.trace_id, 32),
        "span_id": _hex(ctx.span_id, 16),
        # The cookbook writes "" for a root span (HALO's SpanRecord requires a string).
        "parent_span_id": _hex(span.parent.span_id, 16) if span.parent else "",
        "trace_state": "",
        "name": f"{operation}.{span.name}" if operation else span.name,
        "kind": kind,
        "start_time": _timestamp(span.start_time),
        "end_time": _timestamp(span.end_time),
        "status": {
            "code": "STATUS_CODE_ERROR" if error else "STATUS_CODE_OK",
            "message": span.status.description or "",
        },
        "resource": {"attributes": resource_attributes},
        "scope": {"name": "agent-framework", "version": _framework_version()},
        "attributes": {k: v for k, v in out.items() if v is not None},
    }


def _framework_version() -> str:
    try:
        from importlib.metadata import version

        return version("agent-framework")
    except Exception:  # noqa: BLE001
        return ""


class HaloJsonlSpanExporter(SpanExporter):
    """The cookbook's ``HaloJsonlTraceProcessor``: each finished span is one line, appended."""

    def __init__(self, path: Path = HALO_TRACE_PATH, max_bytes: int = HALO_TRACE_MAX_BYTES) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.max_bytes = max_bytes
        self._file = path.open("a", encoding="utf-8")
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        lines = []
        for span in spans:
            resource = dict(span.resource.attributes) if span.resource else {}
            lines.append(json.dumps(span_to_halo_jsonl_line(span, resource), separators=(",", ":"), default=str))
        with self._lock:
            for line in lines:
                self._file.write(line + "\n")
            self._file.flush()
            if os.fstat(self._file.fileno()).st_size > self.max_bytes:
                keep_newest(self.path, self.max_bytes // 2)
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        with self._lock:
            self._file.flush()
        return True

    def shutdown(self) -> None:
        with self._lock:
            self._file.close()


# An OTLP collector named by OTEL_EXPORTER_OTLP_ENDPOINT is spoken to over http/protobuf: MAF's otlp_protocol defaults
# to "grpc" (agent_framework/observability.py:1671-1672), and only the http exporter package is installed here.
OTLP_PROTOCOL = "http/protobuf"


def setup_halo_tracing(path: Path = HALO_TRACE_PATH, exporters: Sequence[Any] = ()) -> HaloJsonlSpanExporter:
    """Write every span to the HALO JSONL file, alongside whatever tracing is already set up.

    ``exporters``: metric and log exporters for MAF's providers (hosted.py's telemetry files), used when this call is
    the one that sets the providers up.
    """
    exporter = HaloJsonlSpanExporter(path)
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        configure_otel_providers(exporters=[exporter, *exporters], enable_sensitive_data=True, otlp_protocol=OTLP_PROTOCOL)
    return exporter
