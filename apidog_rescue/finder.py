"""Locate ApiDog data directory across operating systems."""

import platform
import sys
from pathlib import Path
from typing import Optional


CANDIDATE_PATHS: dict[str, list[Path]] = {
    "darwin": [
        Path.home() / "Library" / "Application Support" / "apidog",
        Path.home() / "Library" / "Application Support" / "Apidog",
    ],
    "win32": [
        Path.home() / "AppData" / "Roaming" / "apidog",
        Path.home() / "AppData" / "Local" / "apidog",
        Path.home() / "AppData" / "Roaming" / "Apidog",
        Path.home() / "AppData" / "Local" / "Apidog",
    ],
    "linux": [
        Path.home() / ".config" / "apidog",
        Path.home() / ".config" / "Apidog",
        Path.home() / "snap" / "apidog" / "current" / ".config" / "apidog",
    ],
}


def _is_valid_apidog_dir(path: Path) -> bool:
    """Check if a directory looks like ApiDog data."""
    if not path.is_dir():
        return False
    markers = [
        path / "data-storage-project.json",
        path / "data-storage-apiDetailTreeList.json",
        path / "IndexedDB",
        path / "Collections",
    ]
    return any(m.exists() for m in markers)


def find_apidog_dir(override: Optional[str] = None) -> Optional[Path]:
    """
    Return the ApiDog data directory.

    If *override* is given, use that path (and raise if invalid).
    Otherwise, try known OS-specific locations.
    """
    if override:
        p = Path(override).expanduser().resolve()
        if not _is_valid_apidog_dir(p):
            raise FileNotFoundError(
                f"Provided path does not look like an ApiDog data directory: {p}"
            )
        return p

    os_key = sys.platform  # darwin / win32 / linux
    candidates = CANDIDATE_PATHS.get(os_key, [])

    # Also try generic linux key on non-macOS / non-Windows
    if os_key not in ("darwin", "win32"):
        candidates = CANDIDATE_PATHS.get("linux", []) + candidates

    for path in candidates:
        if _is_valid_apidog_dir(path):
            return path

    return None
