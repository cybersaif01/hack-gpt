"""
History management for Hack-GPT sessions.
Saves and loads conversation history per session.
"""

import json
from pathlib import Path
from datetime import datetime
from hackgpt.config import load_config

HISTORY_DIR = Path.home() / ".hackgpt" / "history"


def ensure_history_dir():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def get_history_file(session_id: str) -> Path:
    ensure_history_dir()
    return HISTORY_DIR / f"{session_id}.json"


def load_history(session_id: str) -> list:
    f = get_history_file(session_id)
    if f.exists():
        with open(f, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return []


def save_history(session_id: str, messages: list):
    f = get_history_file(session_id)
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(messages, fp, indent=2)


def append_message(session_id: str, role: str, content: str):
    msgs = load_history(session_id)
    msgs.append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    })
    save_history(session_id, msgs)


def clear_history(session_id: str):
    f = get_history_file(session_id)
    if f.exists():
        f.unlink()


def list_sessions() -> list:
    ensure_history_dir()
    return [f.stem for f in HISTORY_DIR.glob("*.json")]


def get_api_messages(session_id: str) -> list:
    """Return history in OpenAI API format (role + content only)."""
    raw = load_history(session_id)
    return [{"role": m["role"], "content": m["content"]} for m in raw]
