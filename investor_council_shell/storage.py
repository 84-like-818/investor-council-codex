from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_HOME_NAME = "InvestorCouncilCodex"
MAX_HANDOFF_HISTORY = 18


def product_home() -> Path:
    env_value = os.environ.get("INVESTOR_COUNCIL_HOME")
    if env_value:
        return Path(env_value)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / DEFAULT_HOME_NAME
    return Path.home() / DEFAULT_HOME_NAME


def ensure_product_home() -> Path:
    home = product_home()
    home.mkdir(parents=True, exist_ok=True)
    return home


def status_file() -> Path:
    return ensure_product_home() / "status.json"


def shell_status_file() -> Path:
    return ensure_product_home() / "shell_status.json"


def planned_interest_file() -> Path:
    return ensure_product_home() / "planned_interest.json"


def handoff_history_file() -> Path:
    return ensure_product_home() / "handoff_history.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_status() -> dict[str, Any]:
    return load_json(status_file(), {})


def load_shell_status() -> dict[str, Any]:
    return load_json(shell_status_file(), {})


def save_shell_status(payload: dict[str, Any]) -> None:
    save_json(shell_status_file(), payload)


def load_planned_interest() -> dict[str, bool]:
    raw = load_json(planned_interest_file(), {})
    if not isinstance(raw, dict):
        return {}
    return {str(key): bool(value) for key, value in raw.items()}


def save_planned_interest(payload: dict[str, bool]) -> None:
    save_json(planned_interest_file(), payload)


def load_handoff_history() -> list[dict[str, Any]]:
    raw = load_json(handoff_history_file(), [])
    if not isinstance(raw, list):
        return []
    history: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            history.append(item)
    return history


def save_handoff_history(payload: list[dict[str, Any]]) -> None:
    save_json(handoff_history_file(), payload[:MAX_HANDOFF_HISTORY])


def append_handoff_history(entry: dict[str, Any]) -> list[dict[str, Any]]:
    history = load_handoff_history()
    history.insert(0, entry)
    trimmed = history[:MAX_HANDOFF_HISTORY]
    save_handoff_history(trimmed)
    return trimmed
