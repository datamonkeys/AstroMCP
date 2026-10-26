"""End-to-end: launch the server as a subprocess and speak MCP over stdio (no network needed)."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


def _rpc(proc: subprocess.Popen[str], msg: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def test_initialize_and_list_tools_over_stdio() -> None:
    proc = subprocess.Popen([sys.executable, "-m", "astromcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout is not None
        _rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
            },
        )
        init = json.loads(proc.stdout.readline())
        assert init["result"]["serverInfo"]["name"] == "astromcp"
        assert "whats_here" in init["result"]["instructions"]
        _rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = json.loads(proc.stdout.readline())["result"]["tools"]
        assert len(tools) == 14
        assert all(t["annotations"]["readOnlyHint"] for t in tools)
        _rpc(
            proc,
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "simbad", "arguments": {"ra": 400, "dec": 0}}},
        )
        call = json.loads(proc.stdout.readline())["result"]
        assert "invalid input" in json.dumps(call)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
