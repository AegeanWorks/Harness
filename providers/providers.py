"""Provider registry: OpenAI-compatible endpoints, config entry not code change.

v1 supports OpenAI-compatible Chat Completions ONLY (https or loopback).
A new provider costs one JSON object in providers.json. Keys live in env.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


def providers_path(root: Path | None = None) -> Path:
    base = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    return base / "providers.json"


def load_registry(root: Path | None = None) -> Dict[str, Any]:
    """The parsed providers.json (raises ValueError with Why/Fix context)."""
    path = providers_path(root)
    try:
        with open(str(path), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError("providers.json missing\nWhy: %s\nFix: restore it" % exc) from None
    except (OSError, ValueError) as exc:
        raise ValueError("providers.json unreadable: %s" % str(exc)[:160]) from None
    if not isinstance(data, dict) or not isinstance(data.get("providers"), list):
        raise ValueError("providers.json needs {providers: [...]}")
    return data


def validate_entry(entry: Dict[str, Any]) -> str | None:
    """None when valid, else the refusal reason (never logs a key)."""
    if not isinstance(entry, dict):
        return "provider entry is not an object"
    for key in ("name", "base_url", "api_key_env"):
        if not str(entry.get(key, "")):
            return "provider entry missing " + key
    base = str(entry.get("base_url", ""))
    ok_loop = base.startswith("http://127.0.0.1") or base.startswith("http://localhost")
    if not (base.startswith("https://") or base == "http://127.0.0.1"
            or base == "http://localhost" or ok_loop):
        return "base_url must be https:// or http://127.0.0.1"
    if not str(entry.get("chat_path", "/chat/completions")).startswith("/"):
        return "chat_path must start with /"
    return None


def list_providers(root: Path | None = None) -> List[Dict[str, Any]]:
    """Validated provider entries in file order."""
    data = load_registry(root)
    out = []
    for entry in data["providers"]:
        reason = validate_entry(entry) if isinstance(entry, dict) else "not an object"
        if reason is not None:
            raise ValueError("bad provider %r: %s" % (entry if isinstance(entry, dict) else entry, reason))
        out.append(entry)
    return out


def get_provider(name: str, root: Path | None = None) -> Dict[str, Any]:
    for entry in list_providers(root):
        if str(entry.get("name")) == name:
            return entry
    raise ValueError("unknown provider %r" % name)


def key_status(entry: Dict[str, Any]) -> str:
    """SET/MISSING dot source, never the value."""
    env_name = str(entry.get("api_key_env", ""))
    return "SET" if env_name and os.getenv(env_name) else "MISSING"


def active_name(root: Path | None = None) -> str:
    base = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    local = base / "config.local.json"
    if local.is_file():
        try:
            with open(str(local), "r", encoding="utf-8") as handle:
                data = json.load(handle)
            name = str(data.get("active_provider", ""))
            if name:
                return name
        except (OSError, ValueError):  # hygiene: allow [silent-except] unreadable local config falls back to default
            pass
    try:
        data = load_registry(root)
        default = str(data.get("default_provider", ""))
        if default:
            return default
    except ValueError:  # hygiene: allow [silent-except] missing registry falls back to openai-compat
        pass
    return "openai-compat"
