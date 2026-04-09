from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "投资大师智能团"
APP_EXE_NAME = "InvestorCouncilCN.exe"
PRODUCT_HOME_NAME = "InvestorCouncilCodex"


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


def payload_root() -> Path:
    return resource_root() / "payload"


def app_home() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / PRODUCT_HOME_NAME
    return Path.home() / PRODUCT_HOME_NAME


def installed_app_dir() -> Path:
    return app_home() / "App"


def installed_docs_dir() -> Path:
    return app_home() / "docs"


def installed_executable() -> Path:
    return installed_app_dir() / APP_EXE_NAME


def desktop_shortcut_path() -> Path:
    return Path.home() / "Desktop" / f"{APP_NAME}.lnk"


def show_message(title: str, message: str, style: int = 0x40) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, title, style)


def copy_payload_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def create_desktop_shortcut(target: Path) -> Path:
    shortcut_path = desktop_shortcut_path()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pythoncom  # type: ignore
        from win32com.client import Dispatch  # type: ignore

        pythoncom.CoInitialize()
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = str(target)
        shortcut.WorkingDirectory = str(target.parent)
        shortcut.IconLocation = str(target)
        shortcut.Save()
    except Exception as exc:
        raise RuntimeError(f"桌面图标创建失败：{exc}") from exc
    return shortcut_path


def install() -> tuple[Path, Path]:
    payload = payload_root()
    app_source = payload / "app"
    docs_source = payload / "docs"
    if not app_source.exists():
        raise RuntimeError("安装包内没有找到应用主程序。")

    app_dir = installed_app_dir()
    docs_dir = installed_docs_dir()
    copy_payload_tree(app_source, app_dir)
    if docs_source.exists():
        copy_payload_tree(docs_source, docs_dir)

    exe_path = installed_executable()
    if not exe_path.exists():
        raise RuntimeError("应用主程序复制后仍未找到。")

    shortcut = create_desktop_shortcut(exe_path)
    return exe_path, shortcut


def launch(executable: Path) -> None:
    try:
        subprocess.Popen([str(executable)], close_fds=True)
    except Exception as exc:
        raise RuntimeError(f"应用已安装，但启动失败：{exc}") from exc


def main() -> None:
    try:
        exe_path, shortcut = install()
        launch(exe_path)
        show_message(
            APP_NAME,
            f"安装完成。\n\n桌面入口：{shortcut}\n\n如果 Codex 尚未安装或未登录，应用会在首屏直接提示你继续配置。",
            0x40,
        )
    except Exception as exc:
        show_message(APP_NAME, f"安装没有完成。\n\n{exc}", 0x10)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
