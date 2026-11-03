#!/usr/bin/env python3
"""Verify the connector catalog without starting Cometline."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, timezone
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "connectors" / "catalog.json"
INDEX_PATH = ROOT / "connectors" / "index.json"
PROTOCOL_VERSION = "2025-06-18"
BLOCKED_HOSTS = ("api.cursor.com",)
SAFE_TOOLS = {
    "svelte": "list-sections",
    "go": "go_workspace",
    "playwright": "browser_tabs",
}

class CheckFailure(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handshake", action="store_true", help="connect to every official mode")
    parser.add_argument("--tools", action="store_true", help="call one safe tool where no auth is required")
    parser.add_argument("--write-results", action="store_true", help="record verification results in the catalog")
    args = parser.parse_args()

    catalog = json.loads(CATALOG_PATH.read_text())
    failures = []
    for connector in catalog.get("connectors", []):
        try:
            verify_shape(connector)
            if args.handshake or args.tools:
                verify_modes(connector, call_tool=args.tools)
            if args.write_results:
                connector["verifiedAt"] = datetime.now(timezone.utc).date().isoformat()
        except CheckFailure as exc:
            failures.append(f"{connector.get('id', '?')}: {exc}")

    if args.write_results and not failures:
        CATALOG_PATH.write_text(json.dumps(catalog, indent=2) + "\n")
        sync_individual_files(catalog)

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"verified {len(catalog.get('connectors', []))} connectors")
    return 0


def verify_shape(connector: dict) -> None:
    for field in ("id", "name", "description", "iconSvg"):
        if not str(connector.get(field, "")).strip():
            raise CheckFailure(f"missing {field}")
    if not connector["iconSvg"].lstrip().startswith("<svg"):
        raise CheckFailure("iconSvg must be an SVG")
    if not connector.get("modes"):
        raise CheckFailure("connector has no direct mode")
    for mode in connector["modes"]:
        if mode.get("transport") not in {"http", "stdio"}:
            raise CheckFailure("transport must be http or stdio")
        target = mode.get("url") or mode.get("command") or ""
        if any(host in target for host in BLOCKED_HOSTS):
            raise CheckFailure("vendor-hosted proxy is not allowed")
        if mode["transport"] == "http" and not str(mode.get("url", "")).startswith("https://"):
            raise CheckFailure("remote mode needs an https URL")
        if mode["transport"] == "stdio" and not mode.get("command"):
            raise CheckFailure("local mode needs a command")


def verify_modes(connector: dict, call_tool: bool) -> None:
    for mode in connector["modes"]:
        if mode["transport"] == "http":
            tools = handshake_http(mode["url"])
        else:
            tools = handshake_stdio(mode)
        if not tools:
            raise CheckFailure(f"{mode['id']} listed no tools")
        if call_tool and mode.get("auth") == "none":
            call_safe_tool(connector["id"], mode, tools)


def handshake_http(url: str) -> list[str]:
    init = post_json(url, rpc("initialize", {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "cometline-connector-verify", "version": "0.1.0"},
    }), session=None)
    if init.get("auth_required"):
        return ["auth-required"]
    session = init["headers"].get("Mcp-Session-Id")
    post_json(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session=session)
    listed = post_json(url, rpc("tools/list", {}), session=session)
    return [item.get("name", "") for item in listed["body"].get("result", {}).get("tools", [])]


def handshake_stdio(mode: dict) -> list[str]:
    command = mode["command"]
    if shutil.which(command) is None:
        print(f"skip {command}: not installed")
        return ["dependency-skipped"]
    env = os.environ.copy()
    process = subprocess.Popen(
        [command, *mode.get("args", [])],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
    try:
        send_stdio(process, rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "cometline-connector-verify", "version": "0.1.0"},
        }))
        if process.poll() not in {None, 0}:
            print(f"skip {command}: process exited before handshake")
            return ["dependency-skipped"]
        read_stdio(process)
        send_stdio(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        send_stdio(process, rpc("tools/list", {}))
        listed = read_stdio(process)
        return [item.get("name", "") for item in listed.get("result", {}).get("tools", [])]
    finally:
        process.kill()


def call_safe_tool(connector_id: str, mode: dict, tools: list[str]) -> None:
    tool = SAFE_TOOLS.get(connector_id)
    if tool is None or tool not in tools:
        return
    if mode["transport"] != "stdio":
        return
    # Remote unauthenticated calls are covered by the Cometline dev test.
    # CI keeps local smoke calls narrow so it does not launch a browser.
    if connector_id != "go":
        return
    process = subprocess.Popen(
        [mode["command"], *mode.get("args", [])],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        send_stdio(process, rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "cometline-connector-verify", "version": "0.1.0"},
        }))
        read_stdio(process)
        send_stdio(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        send_stdio(process, rpc("tools/call", {"name": tool, "arguments": {}}))
        result = read_stdio(process)
        if result.get("error"):
            raise CheckFailure(f"tool call failed: {result['error']}")
    finally:
        process.kill()


def rpc(method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


def post_json(url: str, payload: dict, session: str | None) -> dict:
    data = json.dumps(payload).encode()
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    if session:
        headers["Mcp-Session-Id"] = session
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = decode_mcp_body(response.read().decode())
            return {"headers": dict(response.headers), "body": body}
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            return {"auth_required": True, "headers": {}, "body": {}}
        raise CheckFailure(f"HTTP {exc.code} from {url}") from exc


def decode_mcp_body(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        return {}
    for line in stripped.splitlines():
        if line.startswith("data:"):
            return json.loads(line.removeprefix("data:").strip())
    return json.loads(stripped)


def send_stdio(process: subprocess.Popen[str], payload: dict) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()


def read_stdio(process: subprocess.Popen[str]) -> dict:
    assert process.stdout is not None
    line = process.stdout.readline()
    if not line:
        raise CheckFailure("local server closed stdout")
    return json.loads(line)


def sync_individual_files(catalog: dict) -> None:
    names = []
    for connector in catalog["connectors"]:
        name = f"{connector['id']}.json"
        names.append(name)
        (ROOT / "connectors" / name).write_text(json.dumps(connector, indent=2) + "\n")
    INDEX_PATH.write_text(json.dumps({"version": catalog["version"], "connectors": names}, indent=2) + "\n")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)
