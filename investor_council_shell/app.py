from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from investor_council_shell import APP_NAME, APP_VERSION
from investor_council_shell.bootstrap import prepare_runtime
from investor_council_shell.codex_bridge import perform_handoff, resource_root, runtime_status, thread_title_for_mentor
from investor_council_shell.storage import (
    append_handoff_history,
    load_handoff_history,
    load_planned_interest,
    save_planned_interest,
)


RESOURCE_ROOT = resource_root()
APP_ROOT = RESOURCE_ROOT / "investor_council_shell"
WEB_ROOT = APP_ROOT / "web"
CONFIG_ROOT = RESOURCE_ROOT / "config"
SKILL_ROOT = RESOURCE_ROOT / "codex-skills" / "investor-council"
REGISTRY_PATH = CONFIG_ROOT / "mentor_registry.json"
BRAND_PATH = SKILL_ROOT / "assets" / "investor-council-brand.svg"


class InvestorCouncilBackend:
    def __init__(self) -> None:
        self.registry = self._load_registry()
        self.default_mentor = str(self.registry.get("default_mentor") or "livermore")
        self.brand_icon = self._data_uri(BRAND_PATH)

    def bootstrap(self) -> dict[str, Any]:
        mentors = self._mentors_payload()
        history = self._recent_handoffs()
        runtime = runtime_status()
        return {
            "brand": APP_NAME,
            "version": APP_VERSION,
            "headline": "把传奇投资人的长期资料、关键案例与方法论，蒸馏成一个可以每天对话的中文思维成长助手。",
            "subline": "进入利弗莫尔、巴菲特等传奇人物的专属线程，把市场、仓位与问题交给他们的长期框架，让每一次讨论都成为一次认知升级。",
            "brand_icon": self.brand_icon,
            "default_mentor": self.default_mentor,
            "runtime": runtime,
            "mentor_counts": {"ready": len(mentors["ready"]), "planned": len(mentors["planned"])},
            "thread_policy": {
                "title": "人物专属线程",
                "copy": "默认会优先回到该人物自己的 Codex 线程；只有你明确要求时，才会强制新开。",
            },
            "latest_handoff": self._latest_successful_handoff(history),
            "recent_handoffs": history,
            "distribution": {
                "channel": "GitHub Releases",
                "notes": "公开发布请优先使用 GitHub Releases；普通用户默认下载 Setup.exe，高级用户才使用 Portable 或 Codex 一句 prompt。",
            },
            "notice_center": self._notice_center(),
        }

    def mentors(self) -> dict[str, Any]:
        return self._mentors_payload()

    def mentor_detail(self, mentor_id: str) -> dict[str, Any] | None:
        mentor = self._mentor_by_id(mentor_id)
        if not mentor:
            return None
        pack_dir = SKILL_ROOT / "mentors" / mentor_id
        profile = self._load_json(pack_dir / "profile.json", {})
        persona = self._read_text(pack_dir / "persona.md")
        answer_contract = self._read_text(pack_dir / "answer-contract.md")
        interest = load_planned_interest().get(mentor_id, False)
        display_name_zh = mentor.get("display_name_zh", mentor_id)
        return {
            "id": mentor_id,
            "display_name_zh": display_name_zh,
            "display_name_en": mentor.get("display_name_en", mentor_id),
            "status": mentor.get("status", "planned"),
            "selection_label": mentor.get("selection_label", ""),
            "summary": profile.get("summary") or "",
            "style": profile.get("style") or "",
            "memory_namespace": mentor.get("memory_namespace") or profile.get("memory_namespace") or mentor_id,
            "avatar_path": self._avatar_uri(mentor),
            "persona_preview": profile.get("persona_preview") or self._markdown_preview(persona),
            "answer_contract_preview": profile.get("answer_contract_preview") or self._markdown_preview(answer_contract),
            "interested": interest,
            "thread_title": thread_title_for_mentor(str(display_name_zh)),
        }

    def runtime(self) -> dict[str, Any]:
        return runtime_status()

    def history(self) -> dict[str, Any]:
        history = self._recent_handoffs()
        return {"latest_handoff": self._latest_successful_handoff(history), "recent_handoffs": history}

    def repair_runtime(self) -> dict[str, Any]:
        repair_result = prepare_runtime(create_shortcut=True, force_shortcut=True)
        history = self._recent_handoffs()
        return {
            "repair": repair_result,
            "runtime": runtime_status(),
            "latest_handoff": self._latest_successful_handoff(history),
            "recent_handoffs": history,
        }

    def update_planned_interest(self, mentor_id: str, interested: bool) -> dict[str, Any] | None:
        mentor = self._mentor_by_id(mentor_id)
        if not mentor or mentor.get("status") == "ready":
            return None
        interest_map = load_planned_interest()
        interest_map[mentor_id] = interested
        save_planned_interest(interest_map)
        return self.mentor_detail(mentor_id)

    def handoff(self, payload: dict[str, Any]) -> dict[str, Any]:
        mentor_id = str(payload.get("mentor_id") or "").strip()
        mentor = self._mentor_by_id(mentor_id)
        if not mentor:
            return {"ok": False, "mode": "blocked", "message": "未找到要进入的投资人物。", "display_prompt": ""}
        if mentor.get("status") != "ready":
            return {"ok": False, "mode": "blocked", "message": "该人物还在筹备中，暂时不能直接开始对话。", "display_prompt": ""}

        mentor_name = str(mentor.get("display_name_zh") or mentor_id)
        market_notes = str(payload.get("market_notes") or "")
        position = str(payload.get("position") or "")
        symbol = str(payload.get("symbol") or "")
        question = str(payload.get("question") or "")
        force_new_thread = bool(payload.get("force_new_thread"))
        result = perform_handoff(
            mentor_name=mentor_name,
            market_notes=market_notes,
            position=position,
            symbol=symbol,
            question=question,
            force_new_thread=force_new_thread,
        )
        entry = self._build_handoff_entry(
            mentor_id=mentor_id,
            mentor_name=mentor_name,
            market_notes=market_notes,
            position=position,
            symbol=symbol,
            question=question,
            force_new_thread=force_new_thread,
            result=result,
        )
        history = append_handoff_history(entry)
        public_result = self._public_handoff_result(result)
        public_result["latest_handoff"] = self._latest_successful_handoff(history)
        public_result["recent_handoffs"] = history[:8]
        return public_result

    def _build_handoff_entry(
        self,
        mentor_id: str,
        mentor_name: str,
        market_notes: str,
        position: str,
        symbol: str,
        question: str,
        force_new_thread: bool,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        sent_at = datetime.now(timezone.utc).astimezone()
        delivery_ok = bool(result.get("ok")) and str(result.get("mode") or "") in {"auto_sent", "clipboard_fallback", "clipboard_only"}
        thread_title = str(result.get("thread_title") or thread_title_for_mentor(mentor_name))
        return {
            "id": sent_at.strftime("%Y%m%d%H%M%S%f"),
            "mentor_id": mentor_id,
            "mentor_name": mentor_name,
            "thread_title": thread_title,
            "thread_action": str(result.get("thread_action") or "blocked"),
            "thread_strategy": str(result.get("thread_strategy") or ""),
            "mode": str(result.get("mode") or "blocked"),
            "delivery_ok": delivery_ok,
            "message": str(result.get("message") or ""),
            "display_prompt": self._display_prompt(mentor_name, market_notes, position, symbol, question),
            "market_notes": market_notes,
            "position": position,
            "symbol": symbol,
            "question": question,
            "force_new_thread": force_new_thread,
            "sent_at": sent_at.isoformat(),
            "sent_at_label": sent_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _public_handoff_result(self, result: dict[str, Any]) -> dict[str, Any]:
        public_result = dict(result)
        public_result.pop("prompt", None)
        if not public_result.get("display_prompt"):
            public_result["display_prompt"] = self._display_prompt(
                mentor_name=str(public_result.get("mentor_name") or "投资人物"),
                market_notes=str(public_result.get("market_notes") or ""),
                position=str(public_result.get("position") or ""),
                symbol=str(public_result.get("symbol") or ""),
                question=str(public_result.get("question") or ""),
            )
        return public_result

    def _display_prompt(self, mentor_name: str, market_notes: str, position: str, symbol: str, question: str) -> str:
        def normalize(value: str, fallback: str = "未提供") -> str:
            text = " ".join(str(value or "").strip().split())
            return text if text else fallback

        return "\n".join(
            [
                f"人物：{mentor_name}",
                f"市场背景：{normalize(market_notes)}",
                f"当前仓位：{normalize(position)}",
                f"讨论标的：{normalize(symbol)}",
                f"本轮问题：{normalize(question, '请给我一个可执行的判断。')}",
            ]
        )

    def _sanitize_history_item(self, item: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(item)
        sanitized.pop("prompt", None)
        if not sanitized.get("display_prompt"):
            sanitized["display_prompt"] = self._display_prompt(
                mentor_name=str(sanitized.get("mentor_name") or "投资人物"),
                market_notes=str(sanitized.get("market_notes") or ""),
                position=str(sanitized.get("position") or ""),
                symbol=str(sanitized.get("symbol") or ""),
                question=str(sanitized.get("question") or ""),
            )
        return sanitized

    @staticmethod
    def _latest_successful_handoff(history: list[dict[str, Any]]) -> dict[str, Any] | None:
        return next((item for item in history if item.get("delivery_ok")), None)

    def _recent_handoffs(self) -> list[dict[str, Any]]:
        return [self._sanitize_history_item(item) for item in load_handoff_history()[:8]]

    def _mentors_payload(self) -> dict[str, list[dict[str, Any]]]:
        interest_map = load_planned_interest()
        ready: list[dict[str, Any]] = []
        planned: list[dict[str, Any]] = []
        for mentor in self.registry.get("mentors", []):
            card = self._mentor_card(mentor, interest_map)
            if mentor.get("status") == "ready":
                ready.append(card)
            else:
                planned.append(card)
        return {"ready": ready, "planned": planned}

    def _mentor_card(self, mentor: dict[str, Any], interest_map: dict[str, bool]) -> dict[str, Any]:
        mentor_id = str(mentor.get("id") or "")
        pack_dir = SKILL_ROOT / "mentors" / mentor_id
        profile = self._load_json(pack_dir / "profile.json", {})
        display_name_zh = mentor.get("display_name_zh", mentor_id)
        return {
            "id": mentor_id,
            "display_name_zh": display_name_zh,
            "display_name_en": mentor.get("display_name_en", mentor_id),
            "status": mentor.get("status", "planned"),
            "selection_label": mentor.get("selection_label", ""),
            "summary": profile.get("summary") or "",
            "style": profile.get("style") or "",
            "avatar_path": self._avatar_uri(mentor),
            "interested": interest_map.get(mentor_id, False),
            "thread_title": thread_title_for_mentor(str(display_name_zh)),
        }

    def _mentor_by_id(self, mentor_id: str) -> dict[str, Any] | None:
        return next((item for item in self.registry.get("mentors", []) if item.get("id") == mentor_id), None)

    @staticmethod
    def _notice_center() -> dict[str, Any]:
        return {
            "prerequisites": {
                "title": "使用前提",
                "summary": "这是一个 Codex 原生产品壳。你需要自己安装并登录 Codex Windows app，并使用自己的 Codex / ChatGPT 权限。",
                "bullets": [
                    "默认支持 Windows 11 x64。",
                    "普通用户默认走 GitHub Releases -> Setup.exe。",
                    "Portable.zip 和 Codex 一句 prompt 只作为备用或高级路径。",
                ],
            },
            "risk": {
                "title": "免责声明",
                "summary": "本产品用于教育、研究和信息整理，不构成投资建议、收益承诺、招揽或代客理财服务。",
                "bullets": [
                    "任何买卖决策都应由你独立判断并自行承担风险。",
                    "实时行情可能延迟、缺失或失败，产品不会伪造实时事实。",
                    "人物视角和案例资料用于帮助你理解框架，不等于对未来结果的保证。",
                ],
            },
            "privacy": {
                "title": "隐私说明",
                "summary": "当前版本默认不采集远程遥测，但会在本地保存必要状态，并可能访问公开第三方行情接口。",
                "bullets": [
                    "本地会保存人物记忆、最近交接记录和状态文件。",
                    "Codex 登录与权限属于你自己的 OpenAI / Codex 环境。",
                    "产品不会删除仓库外任何非产品文件。",
                ],
            },
        }

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    @staticmethod
    def _load_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _load_registry(self) -> dict[str, Any]:
        return self._load_json(REGISTRY_PATH, {"mentors": []})

    def _avatar_uri(self, mentor: dict[str, Any]) -> str:
        rel_path = str(mentor.get("avatar") or "")
        if not rel_path:
            return self.brand_icon
        avatar_path = RESOURCE_ROOT / rel_path
        if not avatar_path.exists():
            avatar_path = SKILL_ROOT / "mentors" / str(mentor.get("id") or "") / "avatar.svg"
        return self._data_uri(avatar_path) if avatar_path.exists() else self.brand_icon

    @staticmethod
    def _data_uri(path: Path) -> str:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return ""
        return "data:image/svg+xml;utf8," + quote(content)

    @staticmethod
    def _markdown_preview(text: str) -> str:
        lines: list[str] = []
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            stripped = re.sub(r"^#{1,6}\\s*", "", stripped)
            stripped = re.sub(r"^[-*]\\s*", "• ", stripped)
            stripped = stripped.replace("`", "")
            lines.append(stripped)
        return "\n".join(lines[:14])


class Handler(BaseHTTPRequestHandler):
    backend = InvestorCouncilBackend()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            self._send_json(self.backend.bootstrap())
            return
        if parsed.path == "/api/mentors":
            self._send_json(self.backend.mentors())
            return
        if parsed.path == "/api/runtime":
            self._send_json(self.backend.runtime())
            return
        if parsed.path == "/api/history":
            self._send_json(self.backend.history())
            return
        if parsed.path.startswith("/api/mentors/"):
            mentor_id = parsed.path.rsplit("/", 1)[-1]
            payload = self.backend.mentor_detail(mentor_id)
            if not payload:
                self.send_error(404, "Not found")
                return
            self._send_json(payload)
            return
        if parsed.path == "/" or parsed.path == "/index.html":
            self._serve_file(WEB_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/styles.css":
            self._serve_file(WEB_ROOT / "styles.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self._serve_file(WEB_ROOT / "app.js", "application/javascript; charset=utf-8")
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        payload = json.loads(body or "{}")

        if parsed.path == "/api/planned-interest":
            detail = self.backend.update_planned_interest(
                mentor_id=str(payload.get("mentor_id") or ""),
                interested=bool(payload.get("interested")),
            )
            if not detail:
                self.send_error(400, "Invalid mentor")
                return
            self._send_json(detail)
            return

        if parsed.path == "/api/handoff":
            self._send_json(self.backend.handoff(payload))
            return

        if parsed.path == "/api/repair":
            self._send_json(self.backend.repair_runtime())
            return

        self.send_error(404, "Not found")

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404, "Missing asset")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_server(host: str = "127.0.0.1", port: int = 8776) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Investor council shell running at http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the investor council shell backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8776)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()


