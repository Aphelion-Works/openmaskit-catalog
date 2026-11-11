#!/usr/bin/env python3
"""Build the static files OpenMaskit fetches from this catalog."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "servers"
EXAMPLES = ROOT / "examples"
API = ROOT / "api"

SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
CONTAINER_COMMANDS = {"docker", "podman", "finch", "nerdctl"}
FORBIDDEN_KEYS = {"client_secret", "access_token", "refresh_token", "password"}
SHELL_CHARS = set(";|&$`<>")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when the published files differ from the source entries",
    )
    args = parser.parse_args()
    entries = load_entries(SOURCE)
    for path in sorted(EXAMPLES.glob("*.json")):
        validate(json.loads(path.read_text()), path)
    files = render(entries)
    if args.check:
        return check(files)
    for relative, body in files.items():
        destination = ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body)
    print(f"published {len(entries)} entries")
    return 0


def load_entries(directory: Path) -> list[dict]:
    entries = []
    seen_ids: set[str] = set()
    seen_handles: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        entry = json.loads(path.read_text())
        validate(entry, path)
        if entry["id"] in seen_ids:
            fail(path, f"duplicate id {entry['id']}")
        if entry["handle"] in seen_handles:
            fail(path, f"duplicate handle {entry['handle']}")
        seen_ids.add(entry["id"])
        seen_handles.add(entry["handle"])
        entries.append(entry)
    return entries


def validate(entry: dict, path: Path) -> None:
    if not isinstance(entry, dict):
        fail(path, "entry must be an object")
    reject_secrets(entry, path)
    for field in ("id", "handle", "name", "description", "transport_type"):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            fail(path, f"{field} is required")
    if not SLUG.fullmatch(entry["id"]):
        fail(path, "id must be a lowercase slug")
    if not SLUG.fullmatch(entry["handle"]):
        fail(path, "handle must be a lowercase slug")
    if entry.get("official") is not False:
        fail(path, "official must be false")
    transport = entry["transport_type"]
    oauth_mode = entry.get("oauth_mode")
    requires_oauth = bool(entry.get("requires_oauth"))
    if oauth_mode not in (None, "byo", "dcr"):
        fail(path, "oauth_mode must be byo or dcr")
    if requires_oauth and oauth_mode not in ("byo", "dcr"):
        fail(path, "an OAuth entry must set oauth_mode to byo or dcr")
    if transport == "http":
        validate_http(entry, path)
    elif transport == "stdio":
        validate_stdio(entry, path)
    else:
        fail(path, "transport_type must be http or stdio")
    tags = entry.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        fail(path, "tags must be a list of strings")
    meta = entry.get("meta", {})
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        fail(path, "meta must be an object")


def validate_http(entry: dict, path: Path) -> None:
    host = entry.get("mcp_host")
    parsed = urlparse(host if isinstance(host, str) else "")
    if parsed.scheme != "https" or not parsed.netloc:
        fail(path, "mcp_host must be an https URL")


def validate_stdio(entry: dict, path: Path) -> None:
    if entry.get("requires_oauth") or entry.get("oauth_mode"):
        fail(path, "stdio entries do not use OAuth")
    meta = entry.get("meta") or {}
    command = meta.get("command")
    if not isinstance(command, str) or not command.strip():
        fail(path, "stdio entries require meta.command")
    program = Path(command).name
    if program in CONTAINER_COMMANDS:
        fail(path, f"{program} is not a catalog command")
    if any(char in command for char in SHELL_CHARS):
        fail(path, "meta.command must be a program name, not a shell line")
    args = meta.get("args", [])
    if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
        fail(path, "meta.args must be a list of strings")


def reject_secrets(value, path: Path) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_KEYS:
                fail(path, f"{key} does not belong in the catalog")
            if child == "managed-by-backend":
                fail(path, "hosted-broker entries are not part of this catalog")
            reject_secrets(child, path)
    elif isinstance(value, list):
        for child in value:
            reject_secrets(child, path)


def render(entries: list[dict]) -> dict[str, str]:
    count = len(entries)
    catalog = {
        "data": entries,
        "meta": {
            "total": count,
            "page": 1,
            "size": count or 1,
            "total_pages": 1,
        },
    }
    version = {
        "supported": True,
        "update_required": False,
        "update_available": False,
    }
    files = {
        "api/marketplace/catalog": dump(catalog),
        "api/version_check": dump(version),
    }
    for entry in entries:
        files[f"api/marketplace/servers/{entry['id']}"] = dump(entry)
    return files


def check(files: dict[str, str]) -> int:
    expected = {path: text for path, text in files.items()}
    published = {
        path.relative_to(ROOT).as_posix(): path.read_text()
        for path in API.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    }
    if published != expected:
        missing = sorted(set(expected) - set(published))
        unexpected = sorted(set(published) - set(expected))
        changed = sorted(
            path for path in set(expected) & set(published) if expected[path] != published[path]
        )
        print("published catalog is out of date", file=sys.stderr)
        if missing:
            print("missing: " + ", ".join(missing), file=sys.stderr)
        if unexpected:
            print("unexpected: " + ", ".join(unexpected), file=sys.stderr)
        if changed:
            print("changed: " + ", ".join(changed), file=sys.stderr)
        return 1
    print("published catalog matches the source entries")
    return 0


def dump(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def fail(path: Path, message: str) -> None:
    try:
        shown = path.resolve().relative_to(ROOT)
    except ValueError:
        shown = path
    raise SystemExit(f"{shown}: {message}")


if __name__ == "__main__":
    sys.exit(main())
