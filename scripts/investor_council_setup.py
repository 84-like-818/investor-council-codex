from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP_NAME = '\u6295\u8d44\u5927\u5e08\u667a\u80fd\u56e2'
APP_EXE_NAME = 'InvestorCouncilCN.exe'
PRODUCT_HOME_NAME = 'InvestorCouncilCodex'


def resource_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


def payload_root() -> Path:
    return resource_root() / 'payload'


def app_home() -> Path:
    local_appdata = os.environ.get('LOCALAPPDATA')
    if local_appdata:
        return Path(local_appdata) / PRODUCT_HOME_NAME
    return Path.home() / PRODUCT_HOME_NAME


def installed_app_dir() -> Path:
    return app_home() / 'App'


def installed_docs_dir() -> Path:
    return app_home() / 'docs'


def installed_executable() -> Path:
    return installed_app_dir() / APP_EXE_NAME


def desktop_shortcut_path() -> Path:
    return Path.home() / 'Desktop' / f'{APP_NAME}.lnk'


def show_message(title: str, message: str, style: int = 0x40) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, title, style)


def _process_ids_by_image(image_name: str) -> list[int]:
    try:
        completed = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {image_name}', '/FO', 'CSV', '/NH'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=10,
        )
    except Exception:
        return []

    pids: list[int] = []
    for raw_line in (completed.stdout or '').splitlines():
        line = raw_line.strip().strip('"')
        if not line or 'No tasks are running' in line:
            continue
        parts = [part.strip('"') for part in raw_line.split(',')]
        if len(parts) < 2:
            continue
        try:
            pids.append(int(parts[1]))
        except ValueError:
            continue
    return pids


def ensure_app_not_running() -> None:
    pids = _process_ids_by_image(APP_EXE_NAME)
    if not pids:
        return

    subprocess.run(
        ['taskkill', '/IM', APP_EXE_NAME, '/F', '/T'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        timeout=15,
    )

    deadline = time.time() + 8.0
    while time.time() < deadline:
        if not _process_ids_by_image(APP_EXE_NAME):
            return
        time.sleep(0.35)

    raise RuntimeError('\u68c0\u6d4b\u5230\u65e7\u7248\u6295\u8d44\u5927\u5e08\u667a\u80fd\u56e2\u4ecd\u5728\u540e\u53f0\u8fd0\u884c\uff0c\u5b89\u88c5\u524d\u8bf7\u5148\u5173\u95ed\u5b83\u3002')


def copy_payload_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.rglob('*'):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                shutil.copy2(item, target)
                break
            except PermissionError:
                if attempt == 0:
                    ensure_app_not_running()
                if attempt >= 2:
                    raise RuntimeError(f'\u65e0\u6cd5\u66f4\u65b0\u6587\u4ef6\uff1a{target}\u3002\u8bf7\u5148\u5173\u95ed\u6b63\u5728\u8fd0\u884c\u7684\u6295\u8d44\u5927\u5e08\u667a\u80fd\u56e2\u540e\u91cd\u8bd5\u3002')
                time.sleep(0.5)


def create_desktop_shortcut(target: Path) -> Path:
    shortcut_path = desktop_shortcut_path()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pythoncom  # type: ignore
        from win32com.client import Dispatch  # type: ignore

        pythoncom.CoInitialize()
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = str(target)
        shortcut.WorkingDirectory = str(target.parent)
        shortcut.IconLocation = str(target)
        shortcut.Save()
    except Exception as exc:
        raise RuntimeError(f'\u684c\u9762\u56fe\u6807\u521b\u5efa\u5931\u8d25\uff1a{exc}') from exc
    return shortcut_path


def install() -> tuple[Path, Path]:
    payload = payload_root()
    app_source = payload / 'app'
    docs_source = payload / 'docs'
    if not app_source.exists():
        raise RuntimeError('\u5b89\u88c5\u5305\u5185\u6ca1\u6709\u627e\u5230\u5e94\u7528\u4e3b\u7a0b\u5e8f\u3002')

    ensure_app_not_running()

    app_dir = installed_app_dir()
    docs_dir = installed_docs_dir()
    copy_payload_tree(app_source, app_dir)
    if docs_source.exists():
        copy_payload_tree(docs_source, docs_dir)

    exe_path = installed_executable()
    if not exe_path.exists():
        raise RuntimeError('\u5e94\u7528\u4e3b\u7a0b\u5e8f\u590d\u5236\u540e\u4ecd\u672a\u627e\u5230\u3002')

    shortcut = create_desktop_shortcut(exe_path)
    return exe_path, shortcut


def launch(executable: Path) -> None:
    try:
        subprocess.Popen([str(executable)], close_fds=True)
    except Exception as exc:
        raise RuntimeError(f'\u5e94\u7528\u5df2\u5b89\u88c5\uff0c\u4f46\u542f\u52a8\u5931\u8d25\uff1a{exc}') from exc


def main() -> None:
    try:
        exe_path, shortcut = install()
        launch(exe_path)
        show_message(
            APP_NAME,
            f'\u5b89\u88c5\u5b8c\u6210\u3002\\n\\n\u684c\u9762\u5165\u53e3\uff1a{shortcut}\\n\\n\u5982\u679c Codex \u5c1a\u672a\u5b89\u88c5\u6216\u672a\u767b\u5f55\uff0c\u5e94\u7528\u4f1a\u5728\u9996\u5c4f\u76f4\u63a5\u63d0\u793a\u4f60\u7ee7\u7eed\u914d\u7f6e\u3002',
            0x40,
        )
    except Exception as exc:
        show_message(APP_NAME, f'\u5b89\u88c5\u6ca1\u6709\u5b8c\u6210\u3002\\n\\n{exc}', 0x10)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
