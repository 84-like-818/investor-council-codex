from __future__ import annotations

from datetime import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from investor_council_shell.bootstrap import product_home_health
from investor_council_shell.desktop import webview_runtime_status
from investor_council_shell.storage import load_status


ENTRY_SKILL_NAME = "investor-council"
ENTRY_PROMPT_PREFIX = "Use $investor-council。"
PRODUCT_TITLE = "投资大师智能团"


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


def skill_install_path() -> Path:
    return Path.home() / ".codex" / "skills" / ENTRY_SKILL_NAME


def auth_file_path() -> Path:
    return Path.home() / ".codex" / "auth.json"


def thread_title_for_mentor(mentor_name: str) -> str:
    return f"{mentor_name}｜{PRODUCT_TITLE}"


def _powershell(script: str, timeout: int = 12, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=timeout,
        input=input_text,
    )


def _powershell_json(script: str, timeout: int = 12) -> Any:
    completed = _powershell(script, timeout=timeout)
    if completed.returncode != 0:
        return None
    raw = (completed.stdout or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def codex_command() -> str | None:
    return shutil.which("codex.cmd") or shutil.which("codex")


def codex_logged_in() -> bool:
    command = codex_command()
    if command:
        try:
            completed = subprocess.run(
                [command, "login", "status"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=10,
            )
            output = f"{completed.stdout}\n{completed.stderr}".lower()
            if "logged in" in output or "chatgpt" in output:
                return True
        except Exception:
            pass

    path = auth_file_path()
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    tokens = payload.get("tokens") or {}
    return bool(tokens.get("refresh_token") or tokens.get("access_token") or payload.get("auth_mode"))


def skill_installed() -> bool:
    return (skill_install_path() / "SKILL.md").exists()


def _pywinauto():
    try:
        from pywinauto import Desktop, keyboard, mouse  # type: ignore

        return Desktop, keyboard, mouse
    except Exception:
        return None, None, None


def auto_injection_available() -> bool:
    desktop, keyboard, _mouse = _pywinauto()
    return desktop is not None and keyboard is not None


def _workspace_name_candidates() -> list[str]:
    raw_values = [
        str(os.environ.get("INVESTOR_COUNCIL_WORKSPACE_NAME") or "").strip(),
        Path.cwd().name,
        resource_root().name,
    ]
    blocked = {ENTRY_SKILL_NAME.casefold(), "investor_council_shell", "_internal"}
    seen: set[str] = set()
    candidates: list[str] = []
    for value in raw_values:
        if not value:
            continue
        lowered = value.casefold()
        if lowered in blocked or lowered.startswith("_mei"):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(value)
    return candidates


def _codex_process_info() -> dict[str, Any] | None:
    payload = _powershell_json(
        "@(Get-Process -Name Codex -ErrorAction SilentlyContinue | "
        "Where-Object { $_.MainWindowTitle -ne '' } | "
        "Sort-Object StartTime -Descending | "
        "Select-Object -First 1 -Property Id, MainWindowTitle, StartTime) | ConvertTo-Json -Compress"
    )
    return payload if isinstance(payload, dict) else None


def codex_running() -> bool:
    return bool(_codex_process_info())


def codex_restart_required() -> bool:
    status = load_status()
    skill_synced_at = str(status.get("skill_synced_at") or "").strip()
    if not skill_synced_at:
        return False

    process_info = _codex_process_info()
    if not process_info:
        return False

    start_raw = str(process_info.get("StartTime") or "").strip()
    if not start_raw:
        return False

    try:
        codex_started_at = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        skill_ready_at = datetime.fromisoformat(skill_synced_at)
    except Exception:
        return False

    return codex_started_at <= skill_ready_at


def _control_name(control: Any) -> str:
    try:
        return str(control.window_text() or "").strip()
    except Exception:
        try:
            return str(control.element_info.name or "").strip()
        except Exception:
            return ""


def _control_class_name(control: Any) -> str:
    try:
        return str(control.element_info.class_name or "")
    except Exception:
        return ""


def _control_type(control: Any) -> str:
    try:
        return str(control.element_info.control_type or "")
    except Exception:
        return ""


def _control_rect(control: Any) -> tuple[int, int, int, int]:
    try:
        rect = control.rectangle()
    except Exception:
        rect = control.element_info.rectangle
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def _rect_inside(parent: tuple[int, int, int, int], child: tuple[int, int, int, int]) -> bool:
    parent_left, parent_top, parent_right, parent_bottom = parent
    child_left, child_top, child_right, child_bottom = child
    return not (
        child_right <= parent_left
        or child_left >= parent_right
        or child_bottom <= parent_top
        or child_top >= parent_bottom
    )


def _rect_midpoint(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = rect
    return (left + right) // 2, (top + bottom) // 2


def _is_visible_enabled(control: Any) -> bool:
    try:
        return bool(control.is_visible() and control.is_enabled())
    except Exception:
        return False


def _click_control(control: Any) -> bool:
    if not _is_visible_enabled(control):
        return False

    for method_name in ("invoke", "click_input"):
        method = getattr(control, method_name, None)
        if not callable(method):
            continue
        try:
            method()
            return True
        except Exception:
            continue

    _desktop, _keyboard, mouse = _pywinauto()
    if mouse is None:
        return False
    try:
        mouse.click(coords=_rect_midpoint(_control_rect(control)))
        return True
    except Exception:
        return False


def _find_codex_window():
    Desktop, _keyboard, _mouse = _pywinauto()
    if Desktop is None:
        return None

    try:
        import win32gui  # type: ignore
    except Exception:
        return None

    candidates: list[tuple[int, Any]] = []

    def _collector(hwnd: int, _extra: Any) -> bool:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd).strip()
            if "Codex" not in title:
                return True
            window = Desktop(backend="uia").window(handle=hwnd)
            candidates.append((len(title), window))
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_collector, None)
    except Exception:
        return None

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _focus_existing_codex() -> bool:
    window = _find_codex_window()
    if window is not None:
        try:
            window.set_focus()
            return True
        except Exception:
            try:
                window.click_input()
                return True
            except Exception:
                pass

    try:
        completed = _powershell(
            "$shell = New-Object -ComObject WScript.Shell; "
            "if ($shell.AppActivate('Codex')) { '1' } else { '0' }",
            timeout=6,
        )
        return (completed.stdout or "").strip() == "1"
    except Exception:
        return False


def _resolve_launch_info() -> dict[str, str] | None:
    status = load_status()
    cached = status.get("codex_gui") or {}
    target = str(cached.get("target") or "").strip()
    launch_type = str(cached.get("launch_type") or "").strip()
    if target and launch_type:
        return {
            "launch_type": launch_type,
            "target": target,
            "source": str(cached.get("source") or "status.json"),
        }

    start_app = _powershell_json(
        "$app = Get-StartApps | "
        "Where-Object { $_.Name -like '*Codex*' -or $_.AppID -like '*Codex*' } | "
        "Select-Object -First 1 Name, AppID; "
        "if ($app) { $app | ConvertTo-Json -Compress }",
        timeout=8,
    )
    if isinstance(start_app, dict) and start_app.get("AppID"):
        return {"launch_type": "appid", "target": str(start_app["AppID"]), "source": "Get-StartApps"}

    package = _powershell_json(
        "$pkg = Get-AppxPackage | "
        "Where-Object { $_.PackageFamilyName -like 'OpenAI.Codex*' -or $_.Name -like '*Codex*' } | "
        "Select-Object -First 1 PackageFamilyName, InstallLocation; "
        "if ($pkg) { $pkg | ConvertTo-Json -Compress }",
        timeout=8,
    )
    if isinstance(package, dict):
        install_location = str(package.get("InstallLocation") or "").strip()
        if install_location:
            candidate = Path(install_location) / "app" / "Codex.exe"
            if candidate.exists():
                return {"launch_type": "exe", "target": str(candidate), "source": "Get-AppxPackage"}
        family = str(package.get("PackageFamilyName") or "").strip()
        if family:
            return {"launch_type": "shell", "target": f"shell:AppsFolder\\{family}!App", "source": "AppxPackageFallback"}

    return None


def _launch_codex() -> tuple[bool, str]:
    if _focus_existing_codex():
        return True, "已聚焦现有 Codex 窗口。"

    info = _resolve_launch_info()
    if not info:
        return False, "未检测到可启动的 Codex 桌面入口。"

    try:
        if info["launch_type"] == "exe":
            os.startfile(info["target"])
        elif info["launch_type"] == "appid":
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{info['target']}"])
        elif info["launch_type"] == "shell":
            subprocess.Popen(["explorer.exe", info["target"]])
        else:
            return False, "Codex 启动信息不可用。"
    except Exception as exc:
        return False, f"启动 Codex 失败：{exc}"

    for _ in range(20):
        time.sleep(0.4)
        if _focus_existing_codex():
            return True, "已启动并聚焦 Codex。"
    return False, "Codex 已尝试启动，但窗口还没有成功进入前台。"


def _copy_to_clipboard(text: str) -> bool:
    try:
        import win32clipboard  # type: ignore
        import win32con  # type: ignore

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception:
        try:
            completed = _powershell("Set-Clipboard -Value ([Console]::In.ReadToEnd())", timeout=8, input_text=text)
            return completed.returncode == 0
        except Exception:
            return False


def _sidebar_bounds(window: Any) -> tuple[int, int, int, int]:
    left, top, right, bottom = _control_rect(window)
    width = right - left
    sidebar_width = min(420, max(280, int(width * 0.28)))
    return left, top + 70, left + sidebar_width, bottom - 20


def _is_sidebar_candidate(window: Any, control: Any) -> bool:
    rect = _control_rect(control)
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    s_left, s_top, s_right, s_bottom = _sidebar_bounds(window)
    center_x, center_y = _rect_midpoint(rect)
    if center_x > s_right or center_y < s_top or center_y > s_bottom:
        return False
    if left > s_right:
        return False
    if width < 80 or width > 360:
        return False
    if height < 20 or height > 80:
        return False
    return True


def _button_candidates(window: Any, sidebar_only: bool = False) -> list[Any]:
    try:
        buttons = list(window.descendants(control_type="Button"))
    except Exception:
        return []
    visible = [button for button in buttons if _is_visible_enabled(button)]
    if not sidebar_only:
        return visible
    return [button for button in visible if _is_sidebar_candidate(window, button)]


def _thread_candidates(window: Any) -> list[Any]:
    controls: list[Any] = []
    for control_type in ("Button", "ListItem"):
        try:
            controls.extend(window.descendants(control_type=control_type))
        except Exception:
            continue
    return [control for control in controls if _is_visible_enabled(control) and _is_sidebar_candidate(window, control)]


def _find_matching_button(window: Any, predicate: Callable[[str, str], bool], sidebar_only: bool = False) -> Any | None:
    best: tuple[int, Any] | None = None
    for button in _button_candidates(window, sidebar_only=sidebar_only):
        name = _control_name(button)
        class_name = _control_class_name(button)
        if not predicate(name, class_name):
            continue
        left, top, right, bottom = _control_rect(button)
        height = max(1, bottom - top)
        score = max(0, right - left) - (top // 4) - (height // 2)
        if sidebar_only:
            score += 50
        if best is None or score > best[0]:
            best = (score, button)
    return None if best is None else best[1]


def _find_sidebar_reveal_button(window: Any) -> Any | None:
    labels = ("显示侧栏", "展开侧栏", "Show sidebar", "Open sidebar")
    return _find_matching_button(
        window,
        lambda name, _class_name: any(label.casefold() in name.casefold() for label in labels),
        sidebar_only=False,
    )


def _find_new_thread_button(window: Any) -> Any | None:
    workspace_names = _workspace_name_candidates()
    exact_labels = {f"在 {name} 中开始新线程" for name in workspace_names}
    exact_lower = {label.casefold() for label in exact_labels}
    english_exact = {f"start new thread in {name}".casefold() for name in workspace_names}
    labels = ("开始新线程", "新建线程", "new thread", "start new thread")

    exact_match = _find_matching_button(
        window,
        lambda name, _class_name: name.casefold() in exact_lower or name.casefold() in english_exact,
        sidebar_only=False,
    )
    if exact_match is not None:
        return exact_match

    sidebar_match = _find_matching_button(
        window,
        lambda name, _class_name: any(label in name.casefold() for label in labels) or "开始新线程" in name,
        sidebar_only=True,
    )
    if sidebar_match is not None:
        return sidebar_match

    fallback_candidates: list[tuple[int, Any]] = []
    for control_type in ("ListItem", "Text", "Group"):
        try:
            controls = list(window.descendants(control_type=control_type))
        except Exception:
            controls = []
        for control in controls:
            if not _is_visible_enabled(control):
                continue
            name = _control_name(control)
            if not name:
                continue
            lowered = name.casefold()
            if not (lowered in exact_lower or lowered in english_exact or any(label in lowered for label in labels) or "开始新线程" in name):
                continue
            score = 0
            if lowered in exact_lower or lowered in english_exact:
                score += 200
            if _is_sidebar_candidate(window, control):
                score += 90
            left, top, right, bottom = _control_rect(control)
            score += max(0, min(420, right - left)) // 10
            score -= top // 6
            fallback_candidates.append((score, control))

    if fallback_candidates:
        fallback_candidates.sort(key=lambda item: item[0], reverse=True)
        return fallback_candidates[0][1]

    return _find_matching_button(
        window,
        lambda name, _class_name: any(label in name.casefold() for label in labels) or "开始新线程" in name,
        sidebar_only=False,
    )
def _find_existing_mentor_thread(window: Any, thread_title: str, mentor_name: str) -> Any | None:
    title_lower = thread_title.casefold()
    mentor_lower = mentor_name.casefold()
    product_lower = PRODUCT_TITLE.casefold()
    window_left, window_top, _window_right, _window_bottom = _control_rect(window)
    candidates: list[tuple[int, Any]] = []

    for control in _thread_candidates(window):
        name = _control_name(control)
        if not name or len(name) > 80:
            continue
        lowered = name.casefold()
        if any(token in lowered for token in ("start new thread", "show sidebar", "pin thread", "archive thread")):
            continue
        if any(token in name for token in ("开始新线程", "显示侧栏", "展开侧栏", "归档线程")):
            continue

        score = 0
        if lowered == title_lower:
            score += 320
        elif lowered.startswith(title_lower):
            score += 250
        elif title_lower in lowered:
            score += 210
        if mentor_lower in lowered:
            score += 80
        if product_lower in lowered:
            score += 55
        if _control_type(control) == "ListItem":
            score += 25

        left, top, right, bottom = _control_rect(control)
        score += max(0, min(320, right - left)) // 14
        score += max(0, top - window_top - 110) // 20
        score -= max(0, left - window_left - 40) // 4

        if score > 0:
            candidates.append((score, control))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _prepare_thread_target(window: Any, thread_title: str, mentor_name: str, force_new_thread: bool = False) -> tuple[str, str]:
    if not force_new_thread:
        existing = _find_existing_mentor_thread(window, thread_title, mentor_name)
        if existing is None:
            reveal = _find_sidebar_reveal_button(window)
            if reveal is not None and _click_control(reveal):
                time.sleep(0.35)
                window = _find_codex_window() or window
                existing = _find_existing_mentor_thread(window, thread_title, mentor_name)

        if existing is not None and _click_control(existing):
            time.sleep(0.45)
            return "existing_thread", f"已回到「{thread_title}」对应的专属线程。"

    reveal = _find_sidebar_reveal_button(window)
    if reveal is not None and _click_control(reveal):
        time.sleep(0.35)
        window = _find_codex_window() or window

    new_thread = _find_new_thread_button(window)
    if new_thread is None:
        return "current_thread", "没有找到可点击的新线程入口，已改为继续当前会话。"

    if not _click_control(new_thread):
        return "current_thread", "新线程入口没有成功响应，已改为继续当前会话。"

    time.sleep(0.65)
    return "new_thread", f"已为「{thread_title}」新开一条专属线程。"
def _find_composer_region(window: Any) -> Any | None:
    window_rect = _control_rect(window)
    candidates: list[tuple[int, Any]] = []
    try:
        descendants = list(window.descendants())
    except Exception:
        descendants = []

    for control in descendants:
        if not _is_visible_enabled(control):
            continue
        rect = _control_rect(control)
        if not _rect_inside(window_rect, rect):
            continue
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        if width < 320 or height < 28:
            continue

        class_name = _control_class_name(control).casefold()
        control_type = _control_type(control)
        name = _control_name(control).casefold()
        score = 0

        if "prosemirror" in class_name:
            score += 160
        if "composer" in class_name or "composer" in name:
            score += 42
        if control_type == "Edit":
            score += 35
        if control_type == "Group":
            score += 15
        if top >= window_rect[3] - 220:
            score += 28
        if "terminal" in name or "xterm" in class_name:
            score -= 150

        if score > 0:
            candidates.append((score, control))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _find_send_button(window: Any) -> Any | None:
    window_rect = _control_rect(window)
    candidates: list[tuple[int, Any]] = []
    for button in _button_candidates(window):
        rect = _control_rect(button)
        if not _rect_inside(window_rect, rect):
            continue
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        class_name = _control_class_name(button).casefold()
        name = _control_name(button).casefold()
        score = 0

        if top >= window_rect[3] - 140:
            score += 18
        if right >= window_rect[2] - 900:
            score += 12
        if 20 <= width <= 90 and 20 <= height <= 60:
            score += 8
        if "size-token-button-composer" in class_name:
            score += 95
        if "bg-token-foreground" in class_name:
            score += 40
        if any(token in name for token in ("发送", "send", "run")):
            score += 60
        if score > 0:
            candidates.append((score, button))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], _control_rect(item[1])[2]), reverse=True)
    return candidates[0][1]


def _inject_prompt(prompt: str, mentor_name: str, force_new_thread: bool = False) -> tuple[bool, str, str]:
    _desktop, keyboard, _mouse = _pywinauto()
    thread_title = thread_title_for_mentor(mentor_name)

    if keyboard is None:
        return False, "当前环境不支持自动注入，已回退为剪贴板发送。", "blocked"

    window = _find_codex_window()
    if window is None:
        return False, "没有找到 Codex 主窗口，已回退为剪贴板发送。", "blocked"

    try:
        try:
            window.set_focus()
        except Exception:
            try:
                window.click_input()
            except Exception:
                pass

        thread_action, thread_message = _prepare_thread_target(window, thread_title, mentor_name, force_new_thread=force_new_thread)
        window = _find_codex_window() or window

        composer = None
        for _ in range(10):
            composer = _find_composer_region(window)
            if composer is not None:
                break
            time.sleep(0.2)
            window = _find_codex_window() or window

        if composer is None:
            return False, f"{thread_message} 但没有找到 Codex 输入框。", thread_action

        try:
            composer.set_focus()
        except Exception:
            _click_control(composer)
        time.sleep(0.1)

        keyboard.send_keys("^a{BACKSPACE}", pause=0.01)
        time.sleep(0.05)
        keyboard.send_keys("^v", pause=0.01)
        time.sleep(0.18)

        send_button = _find_send_button(window)
        if send_button is not None and _click_control(send_button):
            return True, f"{thread_message} 已自动把问题发送到 Codex。", thread_action

        keyboard.send_keys("{ENTER}", pause=0.01)
        return True, f"{thread_message} 已自动把问题发送到 Codex。", thread_action
    except Exception as exc:
        return False, f"自动注入过程中出现异常：{exc}", "blocked"


def _normalize_text_field(value: str, fallback: str = "未提供") -> str:
    text = " ".join(str(value or "").strip().split())
    return text if text else fallback


def _normalize_position(value: str) -> str:
    return _normalize_text_field(value, "未提供")


def _display_prompt(mentor_name: str, market_notes: str, position: str, symbol: str, question: str) -> str:
    market_notes = _normalize_text_field(market_notes)
    position = _normalize_position(position)
    symbol = _normalize_text_field(symbol)
    question = _normalize_text_field(question, "请给我一个可执行的判断。")
    return "\n".join(
        [
            f"人物：{mentor_name}",
            f"市场背景：{market_notes}",
            f"当前仓位：{position}",
            f"讨论标的：{symbol}",
            f"本轮问题：{question}",
        ]
    )


def _codex_installed() -> bool:
    return bool(codex_command() or _resolve_launch_info() or auth_file_path().exists())


def _market_runtime_status() -> dict[str, Any]:
    scripts_root = resource_root() / "codex-skills" / ENTRY_SKILL_NAME / "scripts"
    if not scripts_root.exists():
        return {"ok": False, "warn": False, "message": "未找到市场数据脚本。"}

    script_path = str(scripts_root)
    added = False
    if script_path not in sys.path:
        sys.path.insert(0, script_path)
        added = True
    try:
        from market_data_client import MarketDataClient  # type: ignore

        client = MarketDataClient()
        if not client.available():
            return {"ok": False, "warn": False, "message": "实时行情依赖没有准备好。"}
        overview = client.get_market_overview()
        if overview.get("available"):
            return {"ok": True, "warn": False, "message": "实时行情快照已可用。"}
        return {"ok": False, "warn": True, "message": str(overview.get("message") or "实时行情快照暂时不可用。")}
    except Exception as exc:
        return {"ok": False, "warn": False, "message": f"市场数据初始化失败：{exc}"}
    finally:
        if added:
            try:
                sys.path.remove(script_path)
            except ValueError:
                pass


def _runtime_checks() -> list[dict[str, Any]]:
    product_home = product_home_health()
    webview = webview_runtime_status()
    market = _market_runtime_status()
    codex_ready = _codex_installed()
    checks = [
        {
            "id": "codex_app",
            "label": "Codex 桌面端",
            "ok": codex_ready,
            "warn": False,
            "message": "已检测到 Codex。" if codex_ready else "未检测到 Codex Windows app。",
            "action": "请先安装 Codex Windows app。",
        },
        {
            "id": "codex_login",
            "label": "Codex 登录状态",
            "ok": codex_logged_in(),
            "warn": False,
            "message": "已登录 Codex。" if codex_logged_in() else "Codex 尚未登录。",
            "action": "请先打开 Codex 完成登录。",
        },
        {
            "id": "skill_sync",
            "label": "总入口 skill",
            "ok": skill_installed(),
            "warn": False,
            "message": "投资大师智能团入口已就绪。" if skill_installed() else "总入口 skill 尚未安装。",
            "action": "点击“一键修复”重新同步 skill。",
        },
        {
            "id": "product_home",
            "label": "产品状态目录",
            "ok": bool(product_home.get("writable")),
            "warn": False,
            "message": "产品目录可正常写入。" if product_home.get("writable") else f"产品目录不可写：{product_home.get('error') or 'unknown'}",
            "action": "请检查本机权限，确保 LocalAppData 可写。",
        },
        {
            "id": "webview",
            "label": "独立窗口运行时",
            "ok": bool(webview.get("ok")),
            "warn": False,
            "message": str(webview.get("message") or ""),
            "action": "请确认 pywebview 和 Edge WebView2 运行时可用。",
        },
        {
            "id": "market_data",
            "label": "实时市场数据",
            "ok": bool(market.get("ok")),
            "warn": bool(market.get("warn")),
            "message": str(market.get("message") or ""),
            "action": "网络异常时仍可继续对话，但会明确提示实时数据缺口。",
        },
        {
            "id": "auto_injection",
            "label": "Codex 自动交接",
            "ok": auto_injection_available(),
            "warn": not auto_injection_available(),
            "message": "可自动粘贴并发送到 Codex。" if auto_injection_available() else "当前环境不支持自动注入，将回退为剪贴板。",
            "action": "如果自动交接失败，产品会保留剪贴板并把 Codex 拉到前台。",
        },
    ]
    return checks


def build_prompt(
    mentor_name: str,
    market_notes: str,
    position: str,
    symbol: str,
    question: str,
) -> str:
    market_notes = _normalize_text_field(market_notes)
    position = _normalize_position(position)
    symbol = _normalize_text_field(symbol)
    question = _normalize_text_field(question, "请结合当前市场和我的仓位，给我一个可执行的交易建议。")
    thread_title = thread_title_for_mentor(mentor_name)

    return "\n".join(
        [
            ENTRY_PROMPT_PREFIX,
            f"请直接进入「{mentor_name}」助手，不用重新让我选择人物。",
            f"讨论人物：{mentor_name}",
            f"线程标识：{thread_title}",
            f"市场背景：{market_notes}",
            f"当前仓位：{position}",
            f"讨论标的：{symbol}",
            f"我的问题：{question}",
            "请用中文回答，先给结论，再给明日计划、失效条件，并用一句该人物风格的话收束。",
        ]
    )


def runtime_status() -> dict[str, Any]:
    launch_info = _resolve_launch_info()
    checks = _runtime_checks()
    check_map = {item["id"]: item for item in checks}
    codex_installed = bool(check_map["codex_app"]["ok"])
    logged_in = bool(check_map["codex_login"]["ok"])
    skill_ready = bool(check_map["skill_sync"]["ok"])
    product_home_ok = bool(check_map["product_home"]["ok"])
    webview_ready = bool(check_map["webview"]["ok"])
    restart_required = codex_restart_required()

    blocking_message = ""
    blocking_action = ""
    if not webview_ready:
        blocking_message = str(check_map["webview"]["message"])
        blocking_action = str(check_map["webview"]["action"])
    elif not codex_installed:
        blocking_message = "当前机器还没有安装 Codex Windows app，所以暂时不能把问题交接进去。"
        blocking_action = str(check_map["codex_app"]["action"])
    elif not logged_in:
        blocking_message = "已经检测到 Codex，但还没有登录；登录后就能直接继续对话。"
        blocking_action = str(check_map["codex_login"]["action"])
    elif not skill_ready:
        blocking_message = "总入口 skill 还没有同步完成，请先执行一次修复。"
        blocking_action = str(check_map["skill_sync"]["action"])
    elif not product_home_ok:
        blocking_message = str(check_map["product_home"]["message"])
        blocking_action = str(check_map["product_home"]["action"])

    return {
        "codex_installed": codex_installed,
        "codex_logged_in": logged_in,
        "codex_running": codex_running(),
        "codex_restart_required": restart_required,
        "skill_installed": skill_ready,
        "auto_injection_available": auto_injection_available(),
        "codex_launch_ready": bool(launch_info),
        "launch_source": (launch_info or {}).get("source", ""),
        "launch_type": (launch_info or {}).get("launch_type", ""),
        "thread_policy": "mentor_dedicated_threads",
        "product_home_writable": product_home_ok,
        "webview_ready": webview_ready,
        "market_data_ready": bool(check_map["market_data"]["ok"]),
        "market_data_warn": bool(check_map["market_data"].get("warn")),
        "blocking": bool(blocking_message),
        "blocking_message": blocking_message,
        "blocking_action": blocking_action,
        "ready_for_handoff": bool(codex_installed and logged_in and skill_ready and product_home_ok and webview_ready and not restart_required),
        "repair_available": True,
        "checks": checks,
    }


def perform_handoff(
    mentor_name: str,
    market_notes: str,
    position: str,
    symbol: str,
    question: str,
    force_new_thread: bool = False,
) -> dict[str, Any]:
    thread_title = thread_title_for_mentor(mentor_name)
    prompt = build_prompt(mentor_name, market_notes, position, symbol, question)
    result: dict[str, Any] = {
        "ok": False,
        "mode": "blocked",
        "message": "",
        "prompt": prompt,
        "display_prompt": _display_prompt(mentor_name, market_notes, position, symbol, question),
        "mentor_name": mentor_name,
        "market_notes": market_notes,
        "position": position,
        "symbol": symbol,
        "question": question,
        "thread_title": thread_title,
        "thread_action": "blocked",
        "thread_strategy": "优先回到已有人物专属线程，找不到再新建。" if not force_new_thread else "本次明确要求新开该人物线程。",
    }

    if not skill_installed():
        result["message"] = "总入口 skill 还没有安装完成，请先运行启动器完成初始化。"
        return result

    if not _codex_installed():
        result["message"] = "当前机器还没有检测到 Codex Windows app，请先安装并登录 Codex。"
        return result

    if not codex_logged_in():
        result["message"] = "检测到 Codex 尚未登录，请先登录后再开始对话。"
        return result

    copied = _copy_to_clipboard(prompt)
    if not copied:
        result["message"] = "提示词没有成功复制到剪贴板，请稍后重试。"
        return result

    launched, launch_message = _launch_codex()
    if auto_injection_available() and launched:
        injected, inject_message, thread_action = _inject_prompt(prompt, mentor_name, force_new_thread=force_new_thread)
        result["thread_action"] = thread_action
        if injected:
            result.update({"ok": True, "mode": "auto_sent", "message": inject_message})
            return result
        result.update(
            {
                "ok": True,
                "mode": "clipboard_fallback",
                "message": f"{inject_message} 已把 Codex 拉到前台，并保留剪贴板内容，请手动粘贴发送。",
            }
        )
        return result

    if launched:
        result.update(
            {
                "ok": True,
                "mode": "clipboard_fallback",
                "message": f"{launch_message} 当前环境没有自动注入能力，已复制提示词，请在 Codex 中手动粘贴发送。",
            }
        )
        return result

    result.update(
        {
            "ok": True,
            "mode": "clipboard_only",
            "message": f"{launch_message} 提示词已经复制到剪贴板，请先打开 Codex 再手动粘贴发送。",
        }
    )
    return result

