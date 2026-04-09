from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / 'dist' / 'InvestorCouncilReleases'
CUSTOMER_ROOT = ROOT / 'dist' / 'InvestorCouncilCustomerDrop'
APP_NAME = '投资大师智能团'

INSTALLER_SOURCE_NAME = f'{APP_NAME}-Setup.exe'
CUSTOMER_INSTALLER_NAME = f'双击安装-{APP_NAME}.exe'
CUSTOMER_README_NAME = '先看这里-内部交付说明.txt'
CUSTOMER_ZIP_NAME = '内部辅助交付包-投资大师智能团.zip'

README_TEXT = '''投资大师智能团 内部辅助交付说明

这份目录仅供运营、支持或测试团队做内部辅助交付使用。

对外公开发布时，GitHub Releases 仍然是唯一权威发布源。
默认推荐普通用户直接下载：
- 投资大师智能团-Setup.exe

如果你确实要把这份目录发给测试人员，请提醒对方：
1. 先安装并登录 Codex Windows app
2. 再双击“{installer_name}”
3. 安装完成后，双击桌面上的“投资大师智能团”
4. 如果首页出现阻塞提示，按产品提示完成修复

注意：
- 这不是公开发布主路径。
- 以后更新时，应优先让用户下载新的 GitHub Release。
- 产品不会删除仓库外任何非产品文件。
'''


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description='Prepare the internal helper delivery bundle for 投资大师智能团')
    parser.add_argument('--version', required=True)
    args = parser.parse_args()

    version = str(args.version).strip()
    release_dir = RELEASE_ROOT / version
    if not release_dir.exists():
        raise SystemExit(f'找不到 release 目录：{release_dir}')

    installer = release_dir / INSTALLER_SOURCE_NAME
    if not installer.exists():
        raise SystemExit(f'找不到安装包：{installer}')

    customer_dir = CUSTOMER_ROOT / version
    reset_dir(customer_dir)

    shutil.copy2(installer, customer_dir / CUSTOMER_INSTALLER_NAME)
    (customer_dir / CUSTOMER_README_NAME).write_text(
        README_TEXT.format(installer_name=CUSTOMER_INSTALLER_NAME),
        encoding='utf-8',
    )

    zip_path = customer_dir / CUSTOMER_ZIP_NAME
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file_path in customer_dir.iterdir():
            if file_path.is_file() and file_path.name != CUSTOMER_ZIP_NAME:
                archive.write(file_path, arcname=file_path.name)

    print(customer_dir)
    print(zip_path)


if __name__ == '__main__':
    main()
