from __future__ import annotations

import ctypes

from investor_council_shell import APP_NAME


def show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
    except Exception:
        print(message)


def webview_runtime_status() -> dict[str, object]:
    try:
        import webview  # type: ignore

        version = getattr(webview, "__version__", "") or "unknown"
        return {"ok": True, "message": f"pywebview 已就绪（{version}）。"}
    except Exception as exc:
        return {"ok": False, "message": f"缺少壳应用窗口依赖：{exc}"}


def open_window(url: str) -> None:
    try:
        import webview
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("缺少 pywebview 依赖，暂时无法打开独立窗口。") from exc

    webview.create_window(
        APP_NAME,
        url=url,
        width=1480,
        height=980,
        min_size=(1180, 820),
        background_color="#ede4d6",
        text_select=True,
    )
    webview.start(gui="edgechromium", debug=False, http_server=False)
