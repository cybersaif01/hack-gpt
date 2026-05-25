"""
Configuration management for Hack-GPT
Stores API keys and settings in ~/.hackgpt/config.json

Security notes:
- Config file is chmod 600 on Linux/macOS (owner-read-write only)
- Only allowlisted keys may be set via CLI to prevent injection
- Loaded config is schema-validated to block type confusion attacks
"""

import os
import stat
import json
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".hackgpt"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "gpt-4o",
    "api_base": "https://api.openai.com/v1",
    "workspace_dir": str(Path.home() / "hackgpt-workspace"),
    "auto_execute": True,
    "max_tokens": 4096,
    "temperature": 0.2,
    "shell": "auto",          # auto | bash | powershell | cmd
    "confirm_destructive": True,
    "save_history": True,
}

# Only these keys may be set via `hackgpt --config set`
ALLOWED_CONFIG_KEYS = set(DEFAULT_CONFIG.keys())

# Expected types for schema validation
CONFIG_SCHEMA = {
    "api_key": str,
    "model": str,
    "api_base": str,
    "workspace_dir": str,
    "auto_execute": bool,
    "max_tokens": int,
    "temperature": float,
    "shell": str,
    "confirm_destructive": bool,
    "save_history": bool,
}

ALLOWED_SHELLS = {"auto", "bash", "zsh", "fish", "powershell", "cmd"}

# ── Provider presets ──────────────────────────────────────────────────────────
# Each preset sets api_base + model in one shot.
# The key name is what users type: hackgpt --provider gemini
PROVIDER_PRESETS = {
    "gemini": {
        "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model":    "gemini-2.0-flash",
        "label":    "Google Gemini (AI Studio)",
        "key_hint": "Get key at: https://aistudio.google.com/app/apikey",
    },
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "model":    "gpt-4o",
        "label":    "OpenAI",
        "key_hint": "Get key at: https://platform.openai.com/account/api-keys",
    },
    "groq": {
        "api_base": "https://api.groq.com/openai/v1",
        "model":    "llama-3.3-70b-versatile",
        "label":    "Groq (ultra-fast, free tier)",
        "key_hint": "Get key at: https://console.groq.com/keys",
    },
    "ollama": {
        "api_base": "http://localhost:11434/v1",
        "model":    "llama3.2",
        "label":    "Ollama (local, no API key needed)",
        "key_hint": "Run: ollama pull llama3.2",
    },
    "mistral": {
        "api_base": "https://api.mistral.ai/v1",
        "model":    "mistral-large-latest",
        "label":    "Mistral AI",
        "key_hint": "Get key at: https://console.mistral.ai/api-keys",
    },
}


def apply_provider_preset(provider: str, api_key: str = None) -> dict:
    """
    Apply a provider preset to config and optionally set the API key.
    Returns the updated config dict.
    """
    provider = provider.lower().strip()
    if provider not in PROVIDER_PRESETS:
        available = ", ".join(PROVIDER_PRESETS.keys())
        raise ValueError(f"Unknown provider '{provider}'. Available: {available}")

    preset = PROVIDER_PRESETS[provider]
    cfg = load_config()
    cfg["api_base"] = preset["api_base"]
    cfg["model"] = preset["model"]
    if api_key:
        cfg["api_key"] = api_key
    elif provider == "ollama":
        cfg["api_key"] = "ollama"  # Ollama accepts any non-empty key
    cfg = _validate_config(cfg)
    save_config(cfg)
    return cfg


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Restrict directory permissions on Unix
    if sys.platform != "win32":
        os.chmod(CONFIG_DIR, stat.S_IRWXU)  # 700: owner only


def _restrict_file_permissions(path: Path):
    """Set config file to owner-read-write only on Unix (chmod 600)."""
    if sys.platform != "win32":
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 600
        except OSError:
            pass  # Best effort


def _validate_config(cfg: dict) -> dict:
    """Strip unknown keys and coerce types. Raises ValueError on bad values."""
    validated = {}
    for key, expected_type in CONFIG_SCHEMA.items():
        val = cfg.get(key, DEFAULT_CONFIG[key])
        # Type coercion
        try:
            if expected_type == bool and isinstance(val, str):
                val = val.lower() in ("true", "1", "yes")
            elif expected_type == int:
                val = int(val)
            elif expected_type == float:
                val = float(val)
            elif expected_type == str:
                val = str(val)
        except (ValueError, TypeError):
            val = DEFAULT_CONFIG[key]
        # Range checks
        if key == "max_tokens" and not (256 <= int(val) <= 32768):
            val = DEFAULT_CONFIG[key]
        if key == "temperature" and not (0.0 <= float(val) <= 2.0):
            val = DEFAULT_CONFIG[key]
        if key == "shell" and str(val) not in ALLOWED_SHELLS:
            val = "auto"
        if key == "api_base" and not str(val).startswith(("http://", "https://")):
            val = DEFAULT_CONFIG[key]
        validated[key] = val
    return validated


def load_config() -> dict:
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            if not isinstance(saved, dict):
                saved = {}
        except (json.JSONDecodeError, OSError):
            saved = {}
        cfg = {**DEFAULT_CONFIG, **saved}
    else:
        cfg = DEFAULT_CONFIG.copy()

    cfg = _validate_config(cfg)

    # Override with env vars (always trusted over file)
    if os.environ.get("OPENAI_API_KEY"):
        cfg["api_key"] = os.environ["OPENAI_API_KEY"]
    if os.environ.get("HACKGPT_API_KEY"):
        cfg["api_key"] = os.environ["HACKGPT_API_KEY"]
    if os.environ.get("HACKGPT_MODEL"):
        cfg["model"] = os.environ["HACKGPT_MODEL"]
    if os.environ.get("HACKGPT_API_BASE"):
        base = os.environ["HACKGPT_API_BASE"]
        if base.startswith(("http://", "https://")):
            cfg["api_base"] = base
    return cfg


def save_config(cfg: dict):
    ensure_config_dir()
    # Only save known keys
    safe_cfg = {k: v for k, v in cfg.items() if k in ALLOWED_CONFIG_KEYS}
    with open(CONFIG_FILE, "w") as f:
        json.dump(safe_cfg, f, indent=2)
    _restrict_file_permissions(CONFIG_FILE)


def get_config_value(key: str):
    return load_config().get(key)


def set_config_value(key: str, value):
    """Set a config value. Only allowlisted keys accepted."""
    if key not in ALLOWED_CONFIG_KEYS:
        raise ValueError(
            f"Unknown config key: '{key}'\n"
            f"Allowed keys: {', '.join(sorted(ALLOWED_CONFIG_KEYS))}"
        )
    cfg = load_config()
    cfg[key] = value
    # Re-validate before saving
    cfg = _validate_config(cfg)
    save_config(cfg)
