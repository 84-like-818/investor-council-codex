from __future__ import annotations

import argparse
import sys
import time
from threading import Thread
from urllib.request import urlopen

from investor_council_shell.app import run_server
from investor_council_shell.bootstrap import prepare_runtime
from investor_council_shell.desktop import open_window, show_error


def _wait_until_ready(url: str, timeout_seconds: float = 12.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1.2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the investor council shell window")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8776)
    parser.add_argument("--no-window", action="store_true")
    args = parser.parse_args()

    bootstrap_result = prepare_runtime(create_shortcut=getattr(sys, "frozen", False))
    if not bootstrap_result.get("ok"):
        # Keep the shell app usable even when runtime prep is partial; the UI will surface the exact blockers.
        pass

    if args.no_window:
        run_server(host=args.host, port=args.port)
        return

    server_thread = Thread(target=run_server, kwargs={"host": args.host, "port": args.port}, daemon=True)
    server_thread.start()
    base_url = f"http://{args.host}:{args.port}"
    if not _wait_until_ready(base_url):
        show_error("投资大师智能团本地服务没有成功启动，请重试一次。")
        raise SystemExit(1)

    try:
        open_window(base_url)
    except Exception as exc:
        show_error(f"投资大师智能团窗口启动失败。\n\n{exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
