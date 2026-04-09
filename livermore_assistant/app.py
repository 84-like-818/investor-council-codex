from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer
from typing import Any
from urllib.parse import quote, urlparse

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from livermore_assistant.market_data import MarketDataClient


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


RESOURCE_ROOT = _resource_root()
APP_ROOT = RESOURCE_ROOT / "livermore_assistant"
WEB_ROOT = APP_ROOT / "web"
DATA_ROOT = RESOURCE_ROOT / "jesse-livermore"
AVATAR_PATH = WEB_ROOT / "assets" / "livermore-avatar.svg"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "how",
    "i", "if", "in", "into", "is", "it", "of", "on", "or", "that", "the", "their",
    "this", "to", "was", "we", "with", "you", "your",
    "我", "我们", "你", "你们", "的", "了", "和", "是", "在", "就", "都", "而", "及", "与", "或",
    "一个", "没有", "现在", "市场", "自己", "今天", "明天", "昨天",
}

STATE_LABELS = [
    (("高位", "high", "extended"), "高位区域"),
    (("震荡", "横盘", "range", "chop"), "震荡区间"),
    (("分化", "rotation", "divergence"), "龙头分化"),
    (("放量", "volume surge"), "量能放大"),
    (("缩量", "thin volume"), "量能收缩"),
    (("强势", "breakout", "momentum"), "趋势强化"),
    (("回调", "pullback", "retracement"), "回调观察期"),
    (("波动", "volatile", "volatility"), "高波动"),
]


@dataclass
class Snippet:
    title: str
    source_name: str
    text: str
    path: str
    url: str
    role: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9']+|[\u4e00-\u9fff]{1,6}", lowered)
    return [token for token in tokens if token not in STOPWORDS]


def _split_chunks(text: str, size: int = 900) -> list[str]:
    cleaned = _normalize(text)
    if not cleaned:
        return []
    if len(cleaned) <= size:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + size)
        segment = cleaned[start:end]
        if end < len(cleaned):
            pivot = max(segment.rfind(". "), segment.rfind("。"), segment.rfind("? "), segment.rfind("! "))
            if pivot > size // 2:
                end = start + pivot + 1
                segment = cleaned[start:end]
        chunks.append(segment)
        start = max(end, start + 1)
    return chunks


def _load_curated_sources() -> list[dict[str, str]]:
    with (DATA_ROOT / "curated_sources.csv").open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _load_dossier() -> dict[str, Any]:
    return json.loads(_read_text(DATA_ROOT / "dossier.json"))


def _load_distilled_profile() -> str:
    return _read_text(DATA_ROOT / "distilled_profile.md")


def _build_snippets(curated_rows: list[dict[str, str]], dossier: dict[str, Any]) -> list[Snippet]:
    snippets: list[Snippet] = []
    dossier_by_path = {
        str(record.get("saved_text_path") or ""): record
        for record in dossier.get("records", [])
    }
    for row in curated_rows:
        rel_path = (row.get("saved_text_path") or "").strip()
        if not rel_path:
            continue
        full_path = DATA_ROOT / rel_path
        if not full_path.exists():
            continue
        record = dossier_by_path.get(rel_path, {})
        raw_text = _read_text(full_path)
        for chunk in _split_chunks(raw_text):
            snippets.append(
                Snippet(
                    title=row.get("canonical_topic") or row.get("title") or "Untitled",
                    source_name=row.get("source_name") or record.get("source_name") or "Local corpus",
                    text=chunk,
                    path=str(full_path.relative_to(RESOURCE_ROOT)),
                    url=row.get("url") or record.get("url") or "",
                    role=row.get("source_role") or row.get("distill_tier") or "",
                )
            )
    return snippets


def _score_snippet(snippet: Snippet, query_tokens: list[str]) -> float:
    if not query_tokens:
        return 0.0
    haystack = f"{snippet.title} {snippet.role} {snippet.text}".lower()
    hits = sum(1 for token in query_tokens if token in haystack)
    role_bonus = 1.2 if snippet.role in {"core_trading_text", "core_narrative_proxy"} else 0.0
    return hits * 2.0 + role_bonus


def _extract_position(text: str) -> str:
    match = re.search(r"(\d{1,3})\s*[%％]", text)
    return f"{match.group(1)}%仓位" if match else ""


def _detect_state(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for keywords, label in STATE_LABELS:
        if any(keyword in lowered for keyword in keywords):
            found.append(label)
    return found[:4]


def _avatar_data_uri() -> str:
    svg = _read_text(AVATAR_PATH)
    return "data:image/svg+xml;utf8," + quote(svg)


def _format_number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "--"
    return f"{value:.{digits}f}"


def _format_signed(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "--"
    return f"{value:+.{digits}f}"


class LivermoreBrain:
    def __init__(self) -> None:
        self.curated_rows = _load_curated_sources()
        self.dossier = _load_dossier()
        self.profile_md = _load_distilled_profile()
        self.snippets = _build_snippets(self.curated_rows, self.dossier)
        self.market_data = MarketDataClient()
        self.avatar_uri = _avatar_data_uri()

    def bootstrap(self) -> dict[str, Any]:
        return {
            "brand": "利弗莫尔市场助手",
            "headline": "像老交易员一样读趋势、读仓位、读节奏",
            "subline": "输入你的市场背景、持仓和犹豫点，系统会结合实时 A 股快照与利弗莫尔框架，用中文给出判断。",
            "avatar_path": self.avatar_uri,
            "disclaimer": "仅供研究、训练与复盘使用，不构成任何投资建议。",
            "capability_tags": ["实时 A 股指数", "A 股个股快照", "中文对话", "利弗莫尔框架"],
            "starter_prompts": [
                "先写当前市场结构，例如高位震荡、量能收缩、龙头分化。",
                "再写你的仓位和标的，例如我有 30% 仓位，持有光电股份。",
                "最后写你最纠结的决定，例如该追强、减仓，还是等回调确认。",
            ],
        }

    def market_overview(self) -> dict[str, Any]:
        return self.market_data.get_market_overview()

    def answer(self, message: str, market_notes: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        history = history or []
        combined = "\n".join([market_notes, message] + [item.get("content", "") for item in history[-4:]]).strip()
        query_tokens = _tokenize(combined)
        top_snippets = self._select_snippets(query_tokens)
        overview = self.market_data.get_market_overview()
        stock_snapshot = self.market_data.get_stock_snapshot(combined)

        states = _detect_state(combined)
        position = _extract_position(combined)
        conclusion = self._build_conclusion(combined, stock_snapshot, overview, states)
        market_context = self._build_market_context(overview, stock_snapshot)
        lenses = self._pick_lenses(combined, stock_snapshot, top_snippets)
        action_points = self._build_action_points(combined, stock_snapshot, position)

        answer: list[str] = []
        if market_notes.strip():
            answer.append(f"你给的市场背景是：{_normalize(market_notes)}")

        if overview.get("available"):
            answer.append("实时盘面快照：" + market_context)
        else:
            answer.append("实时行情这会儿没有成功刷新，我先按你给出的市场背景和 Livermore 框架来判断。")

        answer.append("先说结论：" + conclusion)
        answer.append("按 Livermore 的思路，这次真正该盯的是：\n" + "\n".join(f"- {item}" for item in lenses))
        answer.append("你下一步更该执行的动作点是：\n" + "\n".join(f"- {item}" for item in action_points))
        return {"answer": "\n\n".join(answer)}

    def _select_snippets(self, query_tokens: list[str]) -> list[Snippet]:
        ranked = sorted(self.snippets, key=lambda item: _score_snippet(item, query_tokens), reverse=True)
        return [item for item in ranked[:3] if _score_snippet(item, query_tokens) > 0]

    def _build_market_context(self, overview: dict[str, Any], stock_snapshot: dict[str, Any] | None) -> str:
        index_bits = []
        for item in overview.get("indices", []):
            index_bits.append(
                f"{item['name']} {_format_number(item['price'])} 点，{_format_signed(item['pct'])}%"
            )
        stock_bit = ""
        if stock_snapshot and stock_snapshot.get("available"):
            industry = stock_snapshot.get("industry") or "未分类"
            stock_bit = (
                f"；{stock_snapshot['name']}（{stock_snapshot['code']}）最新 {_format_number(stock_snapshot.get('latest'))}，"
                f"涨跌幅 {_format_signed(stock_snapshot.get('pct'))}% ，行业 {industry}"
            )
        prefix = "；".join(index_bits) if index_bits else "当前只拿到部分行情数据"
        updated_at = overview.get("updated_at") or "刚刚"
        return f"{prefix}{stock_bit}。刷新时间 {updated_at}。"

    def _build_conclusion(
        self,
        text: str,
        stock_snapshot: dict[str, Any] | None,
        overview: dict[str, Any],
        states: list[str],
    ) -> str:
        has_split = "分化" in text
        has_pullback = "回调" in text or "震荡" in text
        has_position = bool(_extract_position(text))
        if stock_snapshot and stock_snapshot.get("available"):
            pct = stock_snapshot.get("pct")
            if pct is not None and pct <= -2 and has_position:
                return f"{stock_snapshot['name']} 当下已经明显走弱，这时候最重要的是先保护判断力和本金，而不是替持仓找理由。"
            if pct is not None and pct >= 2 and has_split:
                return f"{stock_snapshot['name']} 仍然有相对强度，但处在高位分化环境时，先守住主动权，再等市场二次确认，比直接追击更像 Livermore。"
        if has_split and has_position:
            return "如果指数高位、龙头分化，而你手里已经有仓位，Livermore 更可能先做持仓管理，而不是继续盲目追强。"
        if has_pullback:
            return "他不会因为害怕踏空就提前下注，只有回调后重新转强，才值得让仓位重新发力。"
        if states:
            return f"眼下更重要的是确认{'、'.join(states)}会不会发展成真正趋势，而不是先用观点代替价格。"
        if overview.get("available"):
            return "先让市场自己说话：如果指数与龙头一起配合，再谈出手；如果市场自己都没给方向，就先保留火力。"
        return "Livermore 的第一反应通常不是预测涨跌，而是先确认自己该不该出手、该不该加码。"

    def _pick_lenses(
        self,
        text: str,
        stock_snapshot: dict[str, Any] | None,
        top_snippets: list[Snippet],
    ) -> list[str]:
        lenses: list[str] = []
        knowledge_lens = self._knowledge_lens(top_snippets)
        if knowledge_lens:
            lenses.append(knowledge_lens)

        lowered = text.lower()
        if "追强" in text or "龙头" in text or "momentum" in lowered:
            lenses.append("强者只能在继续证明自己强的时候买，不在想象里买。")
        if "震荡" in text or "横盘" in text or "range" in lowered:
            lenses.append("震荡市最容易把人磨成频繁操作，Livermore 会先等方向，而不是先等借口。")
        if "回调" in text or "pullback" in lowered:
            lenses.append("回调不是自动变成机会，只有回调后重新转强，才值得重新下注。")
        if stock_snapshot and stock_snapshot.get("available") and stock_snapshot.get("turnover") is not None:
            lenses.append(
                f"你盯的这只股当前换手约 {_format_number(stock_snapshot.get('turnover'))}% ，先看资金是否继续认可，而不是只看自己想不想拿。"
            )
        if not lenses:
            lenses.append("先看价格有没有站在你这边，再决定要不要站在价格这边。")
        return lenses[:3]

    def _build_action_points(
        self,
        text: str,
        stock_snapshot: dict[str, Any] | None,
        position: str,
    ) -> list[str]:
        items: list[str] = []
        if stock_snapshot and stock_snapshot.get("available"):
            items.append(
                f"先盯 {stock_snapshot['name']} 开盘后 30 到 60 分钟的强弱延续，尤其是是否重新站回今开价 {_format_number(stock_snapshot.get('open'))} 附近。"
            )
            if stock_snapshot.get("high") is not None and stock_snapshot.get("low") is not None:
                items.append(
                    f"今天的日内区间大致在 {_format_number(stock_snapshot.get('low'))} 到 {_format_number(stock_snapshot.get('high'))}，明天先看价格靠近哪一边，而不是先下结论。"
                )
        else:
            items.append("先看你手里个股与板块龙头是不是同步，别只盯指数点位。")
        if "分化" in text:
            items.append("如果龙头继续强、跟风掉队，说明资金在收缩战线，这种时候更适合聚焦而不是摊开。")
        if "震荡" in text or "横盘" in text:
            items.append("如果价格还在区间里来回，先把试错成本压小，不要在区间中间做重仓判断。")
        if position:
            items.append(f"你现在已经有 {position}，下一步更像是管理仓位质量，而不是证明自己观点正确。")
        else:
            items.append("如果你还没定义失效条件，下一步不是找理由持有，而是先定哪里算错。")
        items.append("只有当价格、量能和相对强弱一起继续改善时，Livermore 才会考虑让利润头寸说话。")
        return items[:4]

    def _knowledge_lens(self, top_snippets: list[Snippet]) -> str:
        if not top_snippets:
            return ""
        corpus = " ".join(item.text[:420].lower() for item in top_snippets)
        if "least resistance" in corpus or "line of least resistance" in corpus:
            return "先找市场的最小阻力方向，再决定该不该跟，而不是先决定立场再去找证据。"
        if "sit tight" in corpus or "big money" in corpus:
            return "真正的大钱通常来自拿住对的趋势，不来自每一段波动都参与。"
        if "cut losses" in corpus or "loss" in corpus:
            return "错了就快认，风险控制比预测更先发生。"
        return "先等市场证明，再让仓位上场，这比抢着表达观点更重要。"


class Handler(BaseHTTPRequestHandler):
    brain = LivermoreBrain()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            self._send_json(self.brain.bootstrap())
            return
        if parsed.path == "/api/market/overview":
            self._send_json(self.brain.market_overview())
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
        if urlparse(self.path).path != "/api/chat":
            self.send_error(404, "Not found")
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        payload = json.loads(body or "{}")
        result = self.brain.answer(
            message=str(payload.get("message") or ""),
            market_notes=str(payload.get("market_notes") or ""),
            history=payload.get("history") or [],
        )
        self._send_json(result)

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


def run_server(host: str = "127.0.0.1", port: int = 8766) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Livermore assistant running at http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Livermore product server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()

    if args.open_browser:
        Timer(1.2, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()


