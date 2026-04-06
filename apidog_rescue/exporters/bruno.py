"""Export api_item dicts to Bruno collection format (.bru files)."""

import json
import re
from pathlib import Path


_SAFE_RE = re.compile(r'[^\w\s-]')
_SPACE_RE = re.compile(r'\s+')

_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def _safe_dirname(name: str) -> str:
    name = _SAFE_RE.sub("", name)
    name = _SPACE_RE.sub("_", name.strip())
    return name or "unnamed"


def _bru_content(item: dict, seq: int) -> str:
    method = item["method"].lower()
    if method not in _HTTP_METHODS:
        method = "get"

    lines: list[str] = []

    # meta block
    lines += [
        "meta {",
        f"  name: {item['name']}",
        "  type: http",
        f"  seq: {seq}",
        "}",
        "",
    ]

    # method + url block
    lines += [
        f"{method} {{",
        f"  url: {item['url']}",
        "}}",
        "",
    ]

    # headers block
    headers = item.get("headers") or []
    if headers:
        lines.append("headers {")
        for h in headers:
            lines.append(f"  {h['name']}: {h.get('value', '')}")
        lines += ["}", ""]

    # query block
    query = item.get("query") or []
    if query:
        lines.append("query {")
        for q in query:
            lines.append(f"  {q['name']}: {q.get('value', '')}")
        lines += ["}", ""]

    # body block
    body = item.get("body")
    if body:
        btype = body.get("type", "raw")
        content = body.get("content") or body.get("raw") or ""
        if isinstance(content, (dict, list)):
            content = json.dumps(content, indent=2)

        if btype in ("json", "raw") and content:
            lines += [
                "body:json {",
                content,
                "}",
                "",
            ]
        elif btype in ("formdata", "urlencoded"):
            tag = "body:form-urlencoded" if btype == "urlencoded" else "body:multipart-form"
            lines.append(f"{tag} {{")
            for field in (body.get("fields") or []):
                lines.append(f"  {field.get('name', '')}: {field.get('value', '')}")
            lines += ["}", ""]

    return "\n".join(lines)


def export_bruno(
    collection_name: str,
    api_items: list[dict],
    output_dir: Path,
) -> Path:
    """
    Write a Bruno collection directory with nested .bru files.
    Returns the root collection directory path.
    """
    safe_name = _safe_dirname(collection_name)
    coll_dir = output_dir / safe_name
    coll_dir.mkdir(parents=True, exist_ok=True)

    # bruno.json at root
    bruno_json = {
        "version": "1",
        "name": collection_name,
        "type": "collection",
        "ignore": [],
    }
    (coll_dir / "bruno.json").write_text(
        json.dumps(bruno_json, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Group items by folder_path
    folders: dict[tuple, list] = {}
    for item in api_items:
        key = tuple(item.get("folder_path") or [])
        folders.setdefault(key, []).append(item)

    # Ensure nested bruno.json for sub-folders
    seen_dirs: set[Path] = {coll_dir}

    def ensure_dir(path_parts: tuple) -> Path:
        d = coll_dir
        for part in path_parts:
            d = d / _safe_dirname(part)
            if d not in seen_dirs:
                d.mkdir(parents=True, exist_ok=True)
                seen_dirs.add(d)
        return d

    for path_parts, items in folders.items():
        folder_dir = ensure_dir(path_parts)
        seq = 1
        name_counts: dict[str, int] = {}
        for item in items:
            base = _safe_dirname(item["name"]) or "request"
            name_counts[base] = name_counts.get(base, 0) + 1
            suffix = f"_{name_counts[base]}" if name_counts[base] > 1 else ""
            bru_path = folder_dir / f"{base}{suffix}.bru"
            bru_path.write_text(_bru_content(item, seq), encoding="utf-8")
            seq += 1

    return coll_dir
