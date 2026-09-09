#!/usr/bin/env python3
"""Shared MCP client for workflow scripts — JSON-RPC 2.0 over HTTP."""

import json
import urllib.request
import socket

MCP_URL = "http://127.0.0.1:8090"

def call(tool, args={}, timeout=60):
    """Call MCP tool via JSON-RPC 2.0."""
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args}
    }).encode()
    req = urllib.request.Request(f"{MCP_URL}/rpc", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = r.read().decode()
    lines = [l for l in resp.strip().split("\n") if l.strip()]
    if not lines:
        return ""
    data = json.loads(lines[-1])
    result = data.get("result", {})
    if "error" in data:
        return data["error"].get("message", str(data["error"]))
    if result.get("isError"):
        content = result.get("content", [])
        return content[0].get("text", "") if content else "error"
    content = result.get("content", [])
    if content and isinstance(content, list):
        return content[0].get("text", "")
    return str(result)

def is_online():
    """Check if MCP server is reachable."""
    try:
        urllib.request.urlopen(f"{MCP_URL}/health", timeout=3)
        return True
    except Exception:
        return False
