from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from investor_council_shell import APP_NAME, APP_VERSION  # noqa: E402

RELEASE_CHANNEL = "GitHub Releases"
ICON_PATH = ROOT / "codex-skills" / "investor-council" / "assets" / "investor-council-desktop.ico"
SHELL_ENTRY = ROOT / "investor_council_shell" / "launcher.py"
INSTALLER_ENTRY = ROOT / "scripts" / "investor_council_setup.py"
LICENSE_DOC = ROOT / "LICENSE"
DISCLAIMER_DOC = ROOT / "免责声明-风险提示-中文.md"
PRIVACY_DOC = ROOT / "隐私说明-中文.md"
PREREQUISITES_DOC = ROOT / "使用前提-合规说明-中文.md"
QUICKSTART_DOC = ROOT / "docs" / "investor_council_release_quickstart_cn.md"
RELEASE_NOTES_DOC = ROOT / "docs" / "investor_council_release_notes_cn.md"
GITHUB_RELEASES_DOC = ROOT / "docs" / "investor_council_github_releases.md"
GITHUB_RELEASE_BODY_DOC = ROOT / "docs" / "investor_council_github_release_body_cn.md"
CODEX_BOOTSTRAP_DOC = ROOT / "docs" / "investor_council_codex_bootstrap_cn.md"
CODEX_BOOTSTRAP_PROMPT = ROOT / "docs" / "investor_council_codex_bootstrap_prompt.txt"
RELEASE_ROOT = ROOT / "dist" / "InvestorCouncilReleases"
BUILD_ROOT = ROOT / "build" / "InvestorCouncilRelease"
ADVANCED_PROMPT = "Use $investor-council。请先用中文让我选择一个投资人物，再进入对应助手。"
INSTALL_PROMPT = "请在当前工作区完成“投资大师智能团”的安装和首启：运行 `scripts\\bootstrap_investor_council_from_codex.ps1`，自动检查 Codex、同步 skill、创建桌面图标并启动产品；如果 Codex 未安装或未登录，就停在清晰的中文阻塞提示；不要删除仓库外任何非产品文件。"


DOC_EXPORTS = {
    "LICENSE": LICENSE_DOC,
    "免责声明-风险提示-中文.md": DISCLAIMER_DOC,
    "隐私说明-中文.md": PRIVACY_DOC,
    "使用前提-合规说明-中文.md": PREREQUISITES_DOC,
    "快速开始-中文.md": QUICKSTART_DOC,
    "发布说明-中文.md": RELEASE_NOTES_DOC,
    "GitHub-Releases-发版流程-中文.md": GITHUB_RELEASES_DOC,
    "GitHub-Releases-正文模板-中文.md": GITHUB_RELEASE_BODY_DOC,
    "Codex一句Prompt自举-中文.md": CODEX_BOOTSTRAP_DOC,
    "Codex一句Prompt-复制版.txt": CODEX_BOOTSTRAP_PROMPT,
}


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_release_docs(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for export_name, source in DOC_EXPORTS.items():
        shutil.copy2(source, target_dir / export_name)
    write_text(target_dir / "高级用户-Codex自修复提示词.txt", ADVANCED_PROMPT + "\n")
    write_text(target_dir / "高级用户-Codex一键安装提示词.txt", INSTALL_PROMPT + "\n")


def pyinstaller_data_arg(source: Path, destination: str) -> str:
    return f"{source};{destination}"


def build_shell_executable(shell_dist: Path, shell_build: Path) -> Path:
    pyinstaller_run(
        [
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name=InvestorCouncilCN",
            f"--icon={ICON_PATH}",
            f"--distpath={shell_dist}",
            f"--workpath={shell_build}",
            f"--specpath={shell_build}",
            f"--paths={ROOT}",
            f"--add-data={pyinstaller_data_arg(ROOT / 'investor_council_shell' / 'web', 'investor_council_shell/web')}",
            f"--add-data={pyinstaller_data_arg(ROOT / 'codex-skills' / 'investor-council', 'codex-skills/investor-council')}",
            f"--add-data={pyinstaller_data_arg(ROOT / 'config' / 'mentor_registry.json', 'config')}",
            "--collect-all=akshare",
            "--collect-all=pandas",
            "--collect-all=curl_cffi",
            "--collect-all=lxml",
            "--collect-all=jsonpath",
            "--collect-all=py_mini_racer",
            "--collect-submodules=webview",
            "--collect-submodules=pywinauto",
            "--hidden-import=pythoncom",
            "--hidden-import=pywintypes",
            "--hidden-import=win32clipboard",
            "--hidden-import=win32con",
            "--hidden-import=win32gui",
            "--hidden-import=win32com",
            "--hidden-import=win32com.client",
            str(SHELL_ENTRY),
        ]
    )
    exe = shell_dist / "InvestorCouncilCN.exe"
    if not exe.exists():
        raise RuntimeError("主程序打包完成后没有找到 InvestorCouncilCN.exe")
    return exe


def build_installer_executable(payload_dir: Path, installer_dist: Path, installer_build: Path) -> Path:
    pyinstaller_run(
        [
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name=InvestorCouncilSetup",
            f"--icon={ICON_PATH}",
            f"--distpath={installer_dist}",
            f"--workpath={installer_build}",
            f"--specpath={installer_build}",
            f"--paths={ROOT}",
            f"--add-data={pyinstaller_data_arg(payload_dir, 'payload')}",
            "--hidden-import=pythoncom",
            "--hidden-import=pywintypes",
            "--hidden-import=win32com",
            "--hidden-import=win32com.client",
            str(INSTALLER_ENTRY),
        ]
    )
    exe = installer_dist / "InvestorCouncilSetup.exe"
    if not exe.exists():
        raise RuntimeError("安装器打包完成后没有找到 InvestorCouncilSetup.exe")
    return exe


def make_portable_bundle(shell_exe: Path, release_dir: Path) -> Path:
    portable_root = release_dir / f"{APP_NAME}-Portable"
    portable_app_dir = portable_root / "app"
    portable_docs_dir = portable_root / "docs"
    reset_dir(portable_root)
    portable_app_dir.mkdir(parents=True, exist_ok=True)
    portable_docs_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(shell_exe, portable_app_dir / "InvestorCouncilCN.exe")
    write_text(
        portable_root / "启动投资大师智能团.cmd",
        '@echo off\r\nsetlocal\r\nstart "" "%~dp0app\\InvestorCouncilCN.exe"\r\n',
    )
    copy_release_docs(portable_docs_dir)

    zip_path = release_dir / f"{APP_NAME}-Portable.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file_path in portable_root.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, arcname=str(file_path.relative_to(release_dir)))
    return zip_path


def build_installer_payload(shell_exe: Path, staging_dir: Path) -> Path:
    payload_dir = staging_dir / "installer-payload"
    app_dir = payload_dir / "app"
    docs_dir = payload_dir / "docs"
    reset_dir(payload_dir)
    app_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(shell_exe, app_dir / "InvestorCouncilCN.exe")
    copy_release_docs(docs_dir)
    return payload_dir


def write_release_manifest(release_dir: Path, version: str, setup_path: Path, portable_zip: Path) -> None:
    manifest = {
        "name": APP_NAME,
        "version": version,
        "channel": RELEASE_CHANNEL,
        "requires": {
            "os": "Windows 11 x64",
            "codex_app": True,
            "user_login": True,
        },
        "artifacts": {
            "setup": setup_path.name,
            "portable": portable_zip.name,
            "checksums": "SHA256SUMS.txt",
            "license": "LICENSE",
            "quickstart": "快速开始-中文.md",
            "release_notes": "发布说明-中文.md",
            "risk_notice": "免责声明-风险提示-中文.md",
            "privacy_notice": "隐私说明-中文.md",
            "prerequisites": "使用前提-合规说明-中文.md",
            "github_releases": "GitHub-Releases-发版流程-中文.md",
            "github_release_body": "GitHub-Releases-正文模板-中文.md",
            "codex_bootstrap": "Codex一句Prompt自举-中文.md",
            "codex_bootstrap_prompt": "Codex一句Prompt-复制版.txt",
            "codex_install_prompt": "高级用户-Codex一键安装提示词.txt",
            "codex_repair_prompt": "高级用户-Codex自修复提示词.txt",
        },
    }
    write_text(release_dir / "release-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def write_checksums(release_dir: Path, paths: list[Path]) -> Path:
    checksum_path = release_dir / "SHA256SUMS.txt"
    lines = [f"{file_sha256(path)} *{path.name}" for path in paths]
    write_text(checksum_path, "\n".join(lines) + "\n")
    return checksum_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the release artifacts for 投资大师智能团")
    parser.add_argument("--version", default=APP_VERSION)
    args = parser.parse_args()

    version = str(args.version).strip() or APP_VERSION
    release_dir = RELEASE_ROOT / version
    shell_dist = BUILD_ROOT / "shell-dist"
    shell_build = BUILD_ROOT / "shell-build"
    installer_dist = BUILD_ROOT / "installer-dist"
    installer_build = BUILD_ROOT / "installer-build"
    staging_dir = BUILD_ROOT / "staging"

    reset_dir(release_dir)
    reset_dir(shell_dist)
    reset_dir(shell_build)
    reset_dir(installer_dist)
    reset_dir(installer_build)
    reset_dir(staging_dir)

    shell_exe = build_shell_executable(shell_dist, shell_build)
    portable_zip = make_portable_bundle(shell_exe, release_dir)
    payload_dir = build_installer_payload(shell_exe, staging_dir)
    installer_exe = build_installer_executable(payload_dir, installer_dist, installer_build)

    final_setup = release_dir / f"{APP_NAME}-Setup.exe"
    shutil.copy2(installer_exe, final_setup)
    copy_release_docs(release_dir)
    write_release_manifest(release_dir, version, final_setup, portable_zip)
    checksum_path = write_checksums(release_dir, [final_setup, portable_zip])

    print(
        json.dumps(
            {
                "release_dir": str(release_dir),
                "setup": str(final_setup),
                "portable": str(portable_zip),
                "checksums": str(checksum_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
