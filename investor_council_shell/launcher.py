from __future__ import annotations

import ctypes
import subprocess
import time

from investor_council_shell import APP_NAME
from investor_council_shell.app import run_server
from investor_council_shell.bootstrap import prepare_runtime
from investor_council_shell.desktop import open_window, show_error

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = 'Local\\InvestorCouncilCodexLauncher'
APP_TITLE_ZH = '\u6295\u8d44\u5927\u5e08\u667a\u80fd\u56e2'


def _wait_until_ready(url: str, timeout_seconds: float = 12.0) -> bool:
    from urllib.request import urlopen

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1.2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def _focus_existing_window() -> bool:
    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"if ($shell.AppActivate('{APP_TITLE_ZH}')) {{ '1' }} "
        "elseif ($shell.AppActivate('Investor Council')) { '1' } else { '0' }"
    )
    try:
        completed = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=6,
        )
        return (completed.stdout or '').strip() == '1'
    except Exception:
        return False


class _SingleInstanceGuard:
    def __init__(self, name: str) -> None:
        self._handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
        self.already_running = ctypes.GetLastError() == ERROR_ALREADY_EXISTS

    def close(self) -> None:
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


def main() -> None:
    import argparse
    import sys
    from threading import Thread

    parser = argparse.ArgumentParser(description='Launch the investor council shell window')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8776)
    parser.add_argument('--no-window', action='store_true')
    args = parser.parse_args()

    guard = _SingleInstanceGuard(MUTEX_NAME)
    if guard.already_running:
        _focus_existing_window()
        show_error('\u6295\u8d44\u5927\u5e08\u667a\u80fd\u56e2\u5df2\u7ecf\u5728\u8fd0\u884c\uff0c\u8bf7\u5148\u67e5\u770b\u4efb\u52a1\u680f\u6216\u5df2\u6253\u5f00\u7684\u7a97\u53e3\u3002')
        raise SystemExit(0)

    try:
        bootstrap_result = prepare_runtime(create_shortcut=getattr(sys, 'frozen', False))
        if not bootstrap_result.get('ok'):
            pass

        if args.no_window:
            run_server(host=args.host, port=args.port)
            return

        server_thread = Thread(target=run_server, kwargs={'host': args.host, 'port': args.port}, daemon=True)
        server_thread.start()
        base_url = f'http://{args.host}:{args.port}'
        if not _wait_until_ready(base_url):
            show_error('\u6295\u8d44\u5927\u5e08\u667a\u80fd\u56e2\u672c\u5730\u670d\u52a1\u6ca1\u6709\u6210\u529f\u542f\u52a8\uff0c\u8bf7\u91cd\u8bd5\u4e00\u6b21\u3002')
            raise SystemExit(1)

        try:
            open_window(base_url)
        except Exception as exc:
            show_error(f'\u6295\u8d44\u5927\u5e08\u667a\u80fd\u56e2\u7a97\u53e3\u542f\u52a8\u5931\u8d25\u3002\\n\\n{exc}')
            raise SystemExit(1) from exc
    finally:
        guard.close()


if __name__ == '__main__':
    main()
