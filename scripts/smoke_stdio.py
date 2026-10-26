"""Smoke test: start an `astromcp` executable over stdio, send MCP initialize + tools/list, print the result.

usage: python scripts/smoke_stdio.py [path/to/astromcp]
"""

import json
import subprocess
import sys

cmd = sys.argv[1] if len(sys.argv) > 1 else "astromcp"
p = subprocess.Popen([cmd], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
assert p.stdin and p.stdout


def send(msg: dict[str, object]) -> None:
    assert p.stdin
    p.stdin.write(json.dumps(msg) + "\n")
    p.stdin.flush()


send(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}},
    }
)
init = json.loads(p.stdout.readline())
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
tools = json.loads(p.stdout.readline())
p.terminate()
info = init["result"]["serverInfo"]
names = [t["name"] for t in tools["result"]["tools"]]
print(f"{info['name']} {info['version']}: {len(names)} tools: {', '.join(names)}")
sys.exit(0 if len(names) == 14 else 1)
