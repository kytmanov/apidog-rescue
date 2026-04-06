"""Extract API data from ApiDog's local storage files."""

import json
import re
import struct
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Data models (plain dicts, no external deps)
# ---------------------------------------------------------------------------

def _api_item(name: str, method: str, url: str, folder_path: list[str]) -> dict:
    return {
        "name": name,
        "method": method.upper() if method else "GET",
        "url": url or "",
        "folder_path": folder_path,
        "headers": [],
        "query": [],
        "body": None,
    }


# ---------------------------------------------------------------------------
# Source 1: data-storage-apiDetailTreeList.json
# ---------------------------------------------------------------------------

def _walk_tree(nodes: list, folder_path: list[str], out: list) -> None:
    for node in nodes:
        ntype = node.get("type", "")
        name = node.get("name", "")
        children = node.get("children") or []

        if ntype == "apiDetailFolder":
            _walk_tree(children, folder_path + [name], out)

        elif ntype == "apiDetail":
            api = node.get("api") or {}
            out.append(_api_item(
                name=name,
                method=api.get("method", "GET"),
                url=api.get("path", ""),
                folder_path=folder_path,
            ))
            # Recurse in case there are nested apiDetail nodes (rare)
            _walk_tree(children, folder_path, out)


def extract_from_tree_json(apidog_dir: Path) -> dict[str, list[dict]]:
    """
    Parse data-storage-apiDetailTreeList.json.
    Returns {project_name: [api_item, ...]}
    """
    tree_file = apidog_dir / "data-storage-apiDetailTreeList.json"
    project_file = apidog_dir / "data-storage-project.json"

    if not tree_file.exists():
        return {}

    with open(tree_file, encoding="utf-8") as f:
        tree_data: dict = json.load(f)

    # Build id -> name map from project file
    project_names: dict[str, str] = {}
    if project_file.exists():
        with open(project_file, encoding="utf-8") as f:
            projects = json.load(f)
        for pid, pdata in projects.items():
            project_names[str(pid)] = pdata.get("name", f"project-{pid}")

    result: dict[str, list[dict]] = {}
    for proj_id, nodes in tree_data.items():
        proj_name = project_names.get(str(proj_id), f"project-{proj_id}")
        items: list[dict] = []
        _walk_tree(nodes, [], items)
        if items:
            result[proj_name] = items

    return result


# ---------------------------------------------------------------------------
# Source 2: Collections/*.postman_collection  (ApiDog YAML format)
# ---------------------------------------------------------------------------

def _parse_yaml_collection(collection_dir: Path) -> list[dict]:
    """Parse a directory of ApiDog .http.yaml files into api_item dicts."""
    items: list[dict] = []
    for yaml_file in sorted(collection_dir.glob("*.http.yaml")):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                continue

            params = data.get("parameters") or {}
            headers = [
                {"name": h["name"], "value": h.get("value", "")}
                for h in (params.get("header") or [])
                if isinstance(h, dict) and h.get("name")
            ]
            query = [
                {"name": q["name"], "value": q.get("value", "")}
                for q in (params.get("query") or [])
                if isinstance(q, dict) and q.get("name")
            ]

            # Body
            body_raw = data.get("body") or data.get("requestBody")
            body = None
            if isinstance(body_raw, dict):
                body = body_raw
            elif isinstance(body_raw, str) and body_raw.strip():
                body = {"type": "raw", "content": body_raw}

            item = _api_item(
                name=data.get("name") or yaml_file.stem,
                method=data.get("method", "GET"),
                url=data.get("url", ""),
                folder_path=[],
            )
            item["headers"] = headers
            item["query"] = query
            item["body"] = body
            items.append(item)

        except Exception:
            continue

    return items


def extract_from_collections_dir(apidog_dir: Path) -> dict[str, list[dict]]:
    """
    Walk Collections/ and parse each *.postman_collection directory.
    Returns {collection_name: [api_item, ...]}
    """
    collections_dir = apidog_dir / "Collections"
    if not collections_dir.exists():
        return {}

    result: dict[str, list[dict]] = {}
    for entry in sorted(collections_dir.iterdir()):
        if entry.is_dir():
            items = _parse_yaml_collection(entry)
            if items:
                # Strip ".postman_collection" suffix for display
                name = entry.name.replace(".postman_collection", "").strip()
                result[name] = items

    return result


# ---------------------------------------------------------------------------
# Source 3: IndexedDB LevelDB (best-effort string extraction)
# ---------------------------------------------------------------------------

_JSON_RE = re.compile(
    r'\{"(?:url|method|path)"[^{}]{5,2000}?\}'  # starts with url/method/path key
    r'|'
    r'\{[^{}]{5,2000}?"(?:url|method)"[^{}]{0,500}?\}',  # contains url or method key
)


def _extract_strings_from_binary(data: bytes, min_len: int = 20) -> list[str]:
    """Extract contiguous printable ASCII / UTF-8 strings from binary data."""
    results = []
    buf: list[int] = []
    for byte in data:
        if 0x20 <= byte <= 0x7E:
            buf.append(byte)
        else:
            if len(buf) >= min_len:
                results.append(bytes(buf).decode("ascii", errors="ignore"))
            buf = []
    if len(buf) >= min_len:
        results.append(bytes(buf).decode("ascii", errors="ignore"))
    return results


def extract_from_indexeddb(apidog_dir: Path) -> list[dict]:
    """
    Best-effort extraction from IndexedDB LevelDB files.
    Returns a flat list of api_item dicts (no folder info).
    """
    idb_dir = apidog_dir / "IndexedDB"
    if not idb_dir.exists():
        return []

    seen_urls: set[str] = set()
    items: list[dict] = []

    for ldb_file in sorted(idb_dir.rglob("*.ldb")):
        try:
            raw = ldb_file.read_bytes()
        except OSError:
            continue

        strings = _extract_strings_from_binary(raw)
        full_text = "\n".join(strings)

        for m in _JSON_RE.finditer(full_text):
            fragment = m.group(0)
            try:
                obj = json.loads(fragment)
            except json.JSONDecodeError:
                continue

            url = obj.get("url") or obj.get("path") or ""
            method = obj.get("method") or "GET"
            name = obj.get("name") or url.rstrip("/").split("/")[-1] or "unknown"

            if not url or url in seen_urls:
                continue
            if not url.startswith("http"):
                continue

            seen_urls.add(url)

            item = _api_item(name=name, method=method, url=url, folder_path=["(from cache)"])

            # Pull headers / query if present
            params = obj.get("parameters") or obj.get("commonParameters") or {}
            if isinstance(params, dict):
                item["headers"] = [
                    {"name": h["name"], "value": h.get("value", "")}
                    for h in (params.get("header") or [])
                    if isinstance(h, dict) and h.get("name")
                ]
                item["query"] = [
                    {"name": q["name"], "value": q.get("value", "")}
                    for q in (params.get("query") or [])
                    if isinstance(q, dict) and q.get("name")
                ]

            items.append(item)

    return items


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def extract_all(apidog_dir: Path) -> dict[str, list[dict]]:
    """
    Run all extractors and merge results.
    Returns {collection_name: [api_item, ...]}
    """
    result: dict[str, list[dict]] = {}

    result.update(extract_from_tree_json(apidog_dir))
    result.update(extract_from_collections_dir(apidog_dir))

    idb_items = extract_from_indexeddb(apidog_dir)
    if idb_items:
        # Only include IDB items that aren't already captured by name+url
        existing_urls: set[str] = {
            item["url"]
            for items in result.values()
            for item in items
        }
        new_items = [i for i in idb_items if i["url"] not in existing_urls]
        if new_items:
            result["(IndexedDB cache)"] = new_items

    return result
