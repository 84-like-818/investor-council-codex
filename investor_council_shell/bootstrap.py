from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from investor_council_shell import APP_NAME, APP_VERSION
from investor_council_shell.storage import ensure_product_home, status_file


ENTRY_SKILL_NAME = "investor-council"
SHORTCUT_NAME = APP_NAME


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


def skills_home() -> Path:
    return Path.home() / ".codex" / "skills"


def skill_source() -> Path:
    return resource_root() / "codex-skills" / ENTRY_SKILL_NAME


def skill_install_path() -> Path:
    return skills_home() / ENTRY_SKILL_NAME


def registry_source_path() -> Path:
    return resource_root() / "config" / "mentor_registry.json"


def registry_mirror_path() -> Path:
    return skill_source() / "assets" / "mentor_registry.json"


def desktop_shortcut_path() -> Path:
    return Path.home() / "Desktop" / f"{SHORTCUT_NAME}.lnk"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _tree_fingerprint(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(file_path.relative_to(path)).replace('\\', '/').encode('utf-8'))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _copytree_incremental(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing source path: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _is_product_shortcut(path: Path) -> bool:
    if not path.exists():
        return False
    return path.name in {f"{SHORTCUT_NAME}.lnk", "Investor Council.lnk"}


def _write_probe(path: Path) -> tuple[bool, str]:
    probe_path = path / ".write_probe"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_path.write_text("ok", encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def product_home_health() -> dict[str, Any]:
    home = ensure_product_home()
    writable, error = _write_probe(home)
    return {"path": str(home), "writable": writable, "error": error}


def sync_registry_mirror() -> dict[str, Any]:
    source = registry_source_path()
    target = registry_mirror_path()
    if not source.exists():
        return {"ok": False, "message": "未找到导师注册表源文件。", "path": str(source)}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        _write_json(target, payload)
        return {"ok": True, "message": "导师注册表镜像已同步。", "path": str(target)}
    except Exception as exc:
        return {"ok": False, "message": f"导师注册表镜像同步失败：{exc}", "path": str(target)}


def sync_skill_to_user() -> dict[str, Any]:
    source = skill_source()
    destination = skill_install_path()
    if not source.exists():
        return {"ok": False, "message": "?????? skill?", "path": str(source), "changed": False, "fingerprint": ""}

    source_fingerprint = _tree_fingerprint(source)
    destination_fingerprint = _tree_fingerprint(destination)
    changed = source_fingerprint != destination_fingerprint

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if changed:
            _copytree_incremental(source, destination)
            destination_fingerprint = _tree_fingerprint(destination)
            return {
                "ok": True,
                "message": "??? skill ???????",
                "path": str(destination),
                "changed": True,
                "fingerprint": destination_fingerprint,
            }
        return {
            "ok": True,
            "message": "??? skill ???????",
            "path": str(destination),
            "changed": False,
            "fingerprint": destination_fingerprint,
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": f"??? skill ?????{exc}",
            "path": str(destination),
            "changed": False,
            "fingerprint": destination_fingerprint,
        }


def _shortcut_target() -> tuple[str, str, str]:
    root = resource_root()
    icon_path = root / "codex-skills" / ENTRY_SKILL_NAME / "assets" / "investor-council-desktop.ico"
    if getattr(sys, "frozen", False):
        target = str(Path(sys.executable).resolve())
        return target, "", str(icon_path if icon_path.exists() else Path(sys.executable).resolve())

    launcher_vbs = root / "scripts" / "launch_investor_council_shell.vbs"
    if launcher_vbs.exists():
        wscript = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe"
        target = str(wscript if wscript.exists() else "wscript.exe")
        args = f'"{launcher_vbs}"'
        icon = str(icon_path if icon_path.exists() else root / "START_INVESTOR_COUNCIL.cmd")
        return target, args, icon

    target = str(Path(sys.executable).resolve())
    args = "-m investor_council_shell.launcher"
    return target, args, str(icon_path if icon_path.exists() else Path(sys.executable).resolve())


def ensure_desktop_shortcut(force: bool = False) -> dict[str, Any]:
    shortcut_path = desktop_shortcut_path()
    if shortcut_path.exists() and not force and _is_product_shortcut(shortcut_path):
        return {"ok": True, "message": "桌面入口已存在。", "path": str(shortcut_path)}

    try:
        import pythoncom  # type: ignore
        from win32com.client import Dispatch  # type: ignore

        pythoncom.CoInitialize()
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        target, arguments, icon = _shortcut_target()
        shortcut.TargetPath = target
        shortcut.Arguments = arguments
        shortcut.WorkingDirectory = str(Path(target).resolve().parent if Path(target).exists() else ensure_product_home())
        if icon:
            shortcut.IconLocation = icon
        shortcut.Save()
        return {"ok": True, "message": "桌面入口已创建。", "path": str(shortcut_path)}
    except Exception as exc:
        return {"ok": False, "message": f"桌面入口创建失败：{exc}", "path": str(shortcut_path)}


def save_runtime_status(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    previous = _read_json(status_file())
    payload = {
        "bundle_display_name": APP_NAME,
        "app_version": APP_VERSION,
        "installed_skill_path": str(skill_install_path()),
        "desktop_shortcut": str(desktop_shortcut_path()),
        "python_executable": sys.executable,
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "updated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "skill_synced_at": previous.get("skill_synced_at", ""),
        "skill_fingerprint": previous.get("skill_fingerprint", ""),
        "skill_sync_changed": bool(previous.get("skill_sync_changed", False)),
    }
    if extra:
        payload.update(extra)
    _write_json(status_file(), payload)
    return payload


def prepare_runtime(create_shortcut: bool = False, force_shortcut: bool = False) -> dict[str, Any]:
    previous_status = _read_json(status_file())
    registry_result = sync_registry_mirror()
    skill_result = sync_skill_to_user()
    product_home_result = product_home_health()
    shortcut_result = {"ok": True, "message": "????????????", "path": str(desktop_shortcut_path())}
    if create_shortcut:
        shortcut_result = ensure_desktop_shortcut(force=force_shortcut)

    skill_synced_at = str(previous_status.get("skill_synced_at") or "")
    skill_fingerprint = str(previous_status.get("skill_fingerprint") or "")
    if skill_result.get("ok") and skill_result.get("fingerprint"):
        skill_fingerprint = str(skill_result.get("fingerprint") or "")
    if skill_result.get("ok") and skill_result.get("changed"):
        skill_synced_at = __import__("datetime").datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    save_runtime_status(
        {
            "registry_sync_ok": registry_result["ok"],
            "skill_sync_ok": skill_result["ok"],
            "skill_sync_changed": bool(skill_result.get("changed")),
            "skill_fingerprint": skill_fingerprint,
            "skill_synced_at": skill_synced_at,
            "product_home": product_home_result["path"],
            "desktop_shortcut_ok": shortcut_result["ok"],
        }
    )

    return {
        "ok": bool(registry_result["ok"] and skill_result["ok"] and product_home_result["writable"]),
        "registry": registry_result,
        "skill": skill_result,
        "product_home": product_home_result,
        "shortcut": shortcut_result,
    }
