from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from market_data_client import MarketDataClient

SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEMORY_FILE = SKILL_ROOT / 'assets' / 'memory' / 'current_session.json'
ACTION_KEYWORDS = (
    '怎么操作',
    '怎么办',
    '持有',
    '减仓',
    '加仓',
    '等确认',
    '追强',
    '止损',
    '计划',
)
LEADER_KEYWORDS = (
    '龙头',
    '板块',
    '最强',
    '领涨',
)


def _ensure_memory_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_memory(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _normalize_text(*parts: str) -> str:
    return '\n'.join(part.strip() for part in parts if part and part.strip())


def _infer_question_type(query: str) -> str:
    if any(keyword in query for keyword in LEADER_KEYWORDS):
        return 'board_leader'
    if any(keyword in query for keyword in ACTION_KEYWORDS):
        return 'action_plan'
    if '?' in query or '？' in query:
        return 'follow_up'
    return 'market_discussion'


def _detect_position(text: str, memory: dict[str, Any]) -> dict[str, Any] | None:
    match = re.search(r'(\d{1,3})\s*[%％]', text)
    if match:
        pct = int(match.group(1))
        return {'pct': pct, 'text': f'{pct}%仓位'}
    stored = memory.get('last_position') or {}
    if stored.get('pct') is not None:
        return stored
    return None


def _resolve_stock(client: MarketDataClient, combined_text: str, memory: dict[str, Any]) -> dict[str, Any] | None:
    resolved = client.resolve_stock(combined_text)
    if resolved:
        return resolved
    last_stock = memory.get('last_stock') or {}
    if last_stock.get('code'):
        return {'code': str(last_stock['code']), 'name': str(last_stock.get('name') or last_stock['code'])}
    return None


def _get_stock_packet(client: MarketDataClient, stock_ref: dict[str, Any] | None) -> dict[str, Any] | None:
    if not stock_ref:
        return None
    return client.get_stock_snapshot(stock_ref.get('code') or stock_ref.get('name') or '')


def _best_board_hint(client: MarketDataClient, stock_packet: dict[str, Any] | None) -> dict[str, Any]:
    if not stock_packet or not stock_packet.get('industry'):
        return {'available': False, 'message': '个股行业信息暂不可用。'}
    return client.get_industry_board(str(stock_packet['industry']))


def _collect_gaps(overview: dict[str, Any], stock: dict[str, Any] | None, board: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not overview.get('available'):
        gaps.append('指数快照未刷新成功')
    if not stock:
        gaps.append('未识别到用户当前讨论的个股')
    elif not stock.get('available'):
        gaps.append('个股盘口快照未刷新成功')
    elif stock.get('quote_available') is False:
        gaps.append('个股盘口快照未刷新成功')
    if not board.get('available'):
        gaps.append(board.get('message') or '行业板块强弱未刷新成功')
    return gaps


def build_brief(query: str, market_notes: str, memory_file: Path) -> dict[str, Any]:
    client = MarketDataClient()
    memory = _load_memory(memory_file)
    combined = _normalize_text(market_notes, query, json.dumps(memory.get('last_stock') or {}, ensure_ascii=False))

    overview = client.get_market_overview()
    stock_ref = _resolve_stock(client, combined, memory)
    stock_packet = _get_stock_packet(client, stock_ref)
    board_packet = _best_board_hint(client, stock_packet)
    position = _detect_position(combined, memory)

    return {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'question_type': _infer_question_type(query),
        'market_overview': overview,
        'stock': stock_packet,
        'board': board_packet,
        'position': position,
        'memory_echo': {
            'last_stock': memory.get('last_stock'),
            'last_position': memory.get('last_position'),
            'last_market_notes': memory.get('last_market_notes'),
            'recent_questions': (memory.get('recent_questions') or [])[-3:],
        },
        'gaps': _collect_gaps(overview, stock_packet, board_packet),
    }


def _to_markdown(brief: dict[str, Any]) -> str:
    lines = ['# Market Brief']
    lines.append(f"- Generated: {brief['generated_at']}")
    lines.append(f"- Question type: {brief['question_type']}")
    position = brief.get('position') or {}
    if position.get('text'):
        lines.append(f"- Position: {position['text']}")

    overview = brief.get('market_overview') or {}
    lines.append('## Indices')
    if overview.get('available'):
        for item in overview.get('indices', []):
            lines.append(f"- {item['name']}: {item.get('price')} ({item.get('pct')}%)")
    else:
        lines.append(f"- Unavailable: {overview.get('message') or 'unknown'}")

    stock = brief.get('stock') or {}
    lines.append('## Stock')
    if stock.get('available'):
        lines.append(
            f"- {stock.get('name')} ({stock.get('code')}), latest {stock.get('latest')}, pct {stock.get('pct')}%, industry {stock.get('industry') or '--'}"
        )
        if stock.get('quote_available') is False:
            lines.append('- Quote status: partial info only')
    else:
        lines.append('- No resolved stock snapshot')

    board = brief.get('board') or {}
    lines.append('## Board')
    if board.get('available'):
        lines.append(f"- {board.get('board_name')}: {board.get('pct')}%, leader {board.get('leader')} ({board.get('leader_pct')}%)")
    else:
        lines.append(f"- Unavailable: {board.get('message') or 'unknown'}")

    gaps = brief.get('gaps') or []
    if gaps:
        lines.append('## Gaps')
        for item in gaps:
            lines.append(f'- {item}')
    return '\n'.join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Build a live market brief for the Livermore Codex skill')
    parser.add_argument('--query', required=True)
    parser.add_argument('--market-notes', default='')
    parser.add_argument('--memory-file', default=str(DEFAULT_MEMORY_FILE))
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    args = parser.parse_args()

    memory_file = _ensure_memory_path(Path(args.memory_file))
    brief = build_brief(args.query, args.market_notes, memory_file)

    if args.format == 'markdown':
        print(_to_markdown(brief))
    else:
        print(json.dumps(brief, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
