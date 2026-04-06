"""Export api_item dicts and environments to Postman format."""

import json
import uuid
from pathlib import Path
from typing import Any


def _parse_url(raw: str, query_params: list[dict]) -> dict:
    url = raw.strip()
    protocol = ""
    host: list[str] = []
    path_parts: list[str] = []

    if "://" in url:
        protocol, rest = url.split("://", 1)
        slash_idx = rest.find("/")
        if slash_idx == -1:
            host = rest.split(".")
        else:
            host = rest[:slash_idx].split(".")
            path_parts = [p for p in rest[slash_idx:].split("/") if p]

    query = [
        {"key": q["name"], "value": q.get("value", ""), "disabled": False}
        for q in query_params
    ]

    return {
        "raw": url,
        "protocol": protocol,
        "host": host,
        "path": path_parts,
        "query": query,
    }


def _build_request(item: dict) -> dict:
    req: dict[str, Any] = {
        "method": item["method"].upper(),
        "header": [
            {"key": h["name"], "value": h.get("value", ""), "type": "text"}
            for h in (item.get("headers") or [])
        ],
        "url": _parse_url(item["url"], item.get("query") or []),
    }

    body = item.get("body")
    if body:
        btype = body.get("type", "raw")
        if btype in ("json", "raw"):
            content = body.get("content") or body.get("raw") or ""
            if isinstance(content, (dict, list)):
                content = json.dumps(content, indent=2)
            req["body"] = {
                "mode": "raw",
                "raw": content,
                "options": {"raw": {"language": "json"}},
            }
        elif btype == "formdata":
            req["body"] = {
                "mode": "formdata",
                "formdata": [
                    {"key": f.get("name", ""), "value": f.get("value", ""), "type": "text"}
                    for f in (body.get("fields") or [])
                ],
            }
        elif btype == "urlencoded":
            req["body"] = {
                "mode": "urlencoded",
                "urlencoded": [
                    {"key": f.get("name", ""), "value": f.get("value", ""), "type": "text"}
                    for f in (body.get("fields") or [])
                ],
            }

    return req


def _items_to_postman(api_items: list[dict]) -> list[dict]:
    """Convert flat api_item list into Postman nested folder structure."""
    root: list = []
    folder_map: dict[tuple, list] = {}

    def get_folder(path_parts: list[str]) -> list:
        if not path_parts:
            return root
        key = tuple(path_parts)
        if key not in folder_map:
            parent = get_folder(path_parts[:-1])
            folder_obj: dict = {
                "name": path_parts[-1],
                "item": [],
            }
            parent.append(folder_obj)
            folder_map[key] = folder_obj["item"]
        return folder_map[key]

    for item in api_items:
        folder = get_folder(item.get("folder_path") or [])
        folder.append({
            "name": item["name"],
            "request": _build_request(item),
            "response": [],
        })

    return root


def export_postman(
    collection_name: str,
    api_items: list[dict],
    output_dir: Path,
) -> Path:
    """Write a Postman v2.1 collection JSON file. Returns the output path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    collection = {
        "info": {
            "name": collection_name,
            "_postman_id": str(uuid.uuid4()),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": _items_to_postman(api_items),
    }

    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in collection_name)
    out_path = output_dir / f"{safe_name}.postman_collection.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(collection, f, indent=2, ensure_ascii=False)

    return out_path


def export_environment_postman(env: dict, output_dir: Path) -> Path:
    """
    Write a Postman environment JSON file from an ApiDog environment dict.
    Uses initialValue as the value (current session values are often empty/expired).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    env_id = env.get("id", "unknown")
    variables = env.get("variables") or []

    values = []
    for var in variables:
        name = var.get("name", "")
        # Prefer initialValue when value is empty (tokens expire; initial values are stable config)
        value = var.get("value") or var.get("initialValue") or ""
        secret = var.get("securityType") == "secret"
        values.append({
            "key": name,
            "value": value,
            "enabled": True,
            "type": "secret" if secret else "default",
        })

    postman_env = {
        "id": str(uuid.uuid4()),
        "name": f"environment-{env_id}",
        "values": values,
        "_postman_variable_scope": "environment",
    }

    out_path = output_dir / f"environment-{env_id}.postman_environment.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(postman_env, f, indent=2, ensure_ascii=False)

    return out_path
