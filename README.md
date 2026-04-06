# apidog-rescue

> Recover lost API collections from ApiDog's local data and export them to **Postman** or **Bruno** — no account required.

ApiDog stores a local cache of your projects even when cloud sync fails. This tool finds that cache, reconstructs your collections, and exports them in formats you can immediately import elsewhere.

---

## What it recovers

| Source | What's extracted |
|--------|-----------------|
| `data-storage-apiDetailTreeList.json` | Full project tree: folder structure, endpoint names, HTTP methods, URLs |
| `Collections/*.postman_collection/` | Local collections with full headers, query params, and request bodies |
| `IndexedDB/` (LevelDB) | Additional endpoints cached during recent sessions (best-effort) |
| `Local Storage/` + `IndexedDB/` (LevelDB) | Environments with all variables and initial values |

---

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager

```bash
# Install uv (one-liner, works on Mac/Linux/Windows)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## Quick start

```bash
git clone https://github.com/kytmanov/apidog-rescue.git
cd apidog-rescue

# Run — auto-detects ApiDog directory, exports to ./recovered/
uv run apidog-rescue
```

That's it. No `pip install`, no virtualenv setup — `uv` handles everything.

---

## Usage

```
uv run apidog-rescue [OPTIONS]

Options:
  --path DIR      Path to ApiDog data directory (auto-detected if omitted)
  --output DIR    Where to write recovered files  [default: ./recovered]
  --format        all | postman | bruno           [default: all]
  --list          Only list what was found; don't write files
  -h, --help      Show this message and exit
```

### Examples

```bash
# Just see what's recoverable without writing anything
uv run apidog-rescue --list

# Export only to Postman format
uv run apidog-rescue --format postman

# Export only to Bruno format
uv run apidog-rescue --format bruno

# Custom output directory
uv run apidog-rescue --output ~/Desktop/recovered-apis

# Manually specify ApiDog path (if auto-detection fails)
uv run apidog-rescue --path "/custom/path/to/apidog"
```

---

## Auto-detected ApiDog paths

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/apidog` |
| Windows | `%APPDATA%\apidog` |
| Linux | `~/.config/apidog` |

---

## Output structure

```
recovered/
├── postman/
│   ├── my_project.postman_collection.json
│   ├── my_local_collection.postman_collection.json
│   └── environment-123.postman_environment.json
└── bruno/
    ├── my_project/
    │   ├── bruno.json
    │   ├── environments/
    │   │   └── environment-123.bru
    │   ├── users/
    │   │   ├── get_user.bru
    │   │   └── create_user.bru
    │   └── orders/
    │       └── ...
    └── my_local_collection/
        ├── bruno.json
        ├── environments/
        │   └── environment-123.bru
        └── ...
```

### Importing into Postman

1. Open Postman → **Import**
2. **Upload Files** → select all files from `recovered/postman/` (collections + environment)
3. Done — the environment will be available in the environment switcher

### Importing into Bruno

1. Open Bruno → **Open Collection**
2. Navigate to `recovered/bruno/<collection-name>/`
3. Done — environments are already inside the collection folder and will appear automatically

---

## Limitations

- **Request bodies** are only recovered for endpoints stored in the local `Collections/` folder (ApiDog YAML format). Endpoints from the project tree JSON have method + URL only — bodies live in IndexedDB which requires a native LevelDB reader to fully decode.
- **Environment names** are not stored locally — exported environments are named by their internal ID. Rename them after import.
- **Cloud-only projects** (never opened locally) cannot be recovered. Contact ApiDog support for those.
- The IndexedDB extractor uses string-scanning heuristics — it may occasionally produce duplicate or partial entries.

---

## License

MIT
