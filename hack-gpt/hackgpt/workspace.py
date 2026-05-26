"""
Workspace manager: creates and organizes pentest workspace directories.
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from hackgpt.config import load_config


WORKSPACE_STRUCTURE = [
    "recon",
    "scans",
    "web",
    "smb",
    "creds",
    "screenshots",
    "loot",
    "exploits",
    "reports",
    "logs",
    "notes",
]


def sanitize_target_name(target: str) -> str:
    """
    Convert target IP/domain to a safe directory name.
    Strips any path traversal sequences and limits length.
    """
    # Remove any path separator or traversal characters
    name = re.sub(r"[^\w.\-]", "_", target).strip("_")
    # Block traversal patterns that survived the above
    name = name.replace("..", "__")
    # Limit length to avoid filesystem issues
    name = name[:64]
    if not name:
        name = "unknown_target"
    return name


def _safe_workspace_path(base: Path, target_name: str) -> Path:
    """
    Resolve workspace path and verify it stays inside base dir.
    Raises ValueError on path traversal attempts.
    """
    candidate = (base / target_name).resolve()
    base_resolved = base.resolve()
    if not str(candidate).startswith(str(base_resolved)):
        raise ValueError(
            f"Path traversal blocked: '{target_name}' would escape workspace root."
        )
    return candidate


def create_workspace(target: str) -> str:
    """Create workspace structure for a target. Returns workspace path."""
    cfg = load_config()
    base = Path(cfg["workspace_dir"])
    target_name = sanitize_target_name(target)
    workspace = _safe_workspace_path(base, target_name)

    for folder in WORKSPACE_STRUCTURE:
        (workspace / folder).mkdir(parents=True, exist_ok=True)

    # Create session metadata
    meta_file = workspace / "session.json"
    if not meta_file.exists():
        meta = {
            "target": target,
            "created": datetime.utcnow().isoformat(),
            "sessions": [],
            "findings": [],
            "open_ports": [],
            "services": {},
        }
        with open(meta_file, "w") as f:
            json.dump(meta, f, indent=2)

    return str(workspace)


def get_workspace(target: str) -> str:
    """Get workspace path for a target (creates if missing)."""
    return create_workspace(target)


def workspace_path(target: str, subfolder: str, filename: str = "") -> str:
    """Return a full path inside the workspace."""
    ws = get_workspace(target)
    p = Path(ws) / subfolder
    p.mkdir(parents=True, exist_ok=True)
    if filename:
        return str(p / filename)
    return str(p)


def save_finding(target: str, finding: dict):
    """Append a finding to the session metadata."""
    ws = get_workspace(target)
    meta_file = Path(ws) / "session.json"
    with open(meta_file, "r") as f:
        meta = json.load(f)
    meta["findings"].append({**finding, "timestamp": datetime.utcnow().isoformat()})
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)


def save_note(target: str, note: str, filename: str = "notes.md"):
    """Append a note to notes folder."""
    p = Path(workspace_path(target, "notes", filename))
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"\n\n## {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        f.write(note + "\n")


def get_workspace_summary(target: str) -> dict:
    """Return metadata summary for a target workspace."""
    ws = get_workspace(target)
    meta_file = Path(ws) / "session.json"
    if meta_file.exists():
        with open(meta_file, "r") as f:
            return json.load(f)
    return {}


def list_workspaces() -> list:
    """List all existing workspace targets."""
    cfg = load_config()
    base = Path(cfg["workspace_dir"])
    if not base.exists():
        return []
    return [
        d.name for d in base.iterdir()
        if d.is_dir() and (d / "session.json").exists()
    ]
