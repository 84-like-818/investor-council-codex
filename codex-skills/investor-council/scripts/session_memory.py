from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from market_data_client import MarketDataClient

MAX_RECENT = 8
DEFAULT_HOME_NAME = 'InvestorCouncilCodex'


def product_home(override: str = '') -> Path:
    if override:
        return Path(override)
    env_value = os.environ.get('INVESTOR_COUNCIL_HOME')
    if env_value:
        return Path(env_value)
    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        return Path(local_app_data) / DEFAULT_HOME_NAME
    return Path.home() / DEFAULT_HOME_NAME


def memory_file_for_mentor(mentor_id: str, override_home: str = '') -> Path:
    return product_home(override_home) / 'memory' / f'{mentor_id}.json'


def _ensure_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(default_memory(), ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def default_memory() -> dict[str, Any]:
    return {
        'last_stock': {},
        'last_position': {},
        'watchlist': [],
        'last_market_notes': '',
        'recent_questions': [],
        'last_answer_summary': '',
        'updated_at': '',
    }


def load_memory(path: Path) -> dict[str, Any]:
    path = _ensure_path(path)
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default_memory()


def save_memory(path: Path, payload: dict[str, Any]) -> None:
    path = _ensure_path(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def update_memory(path: Path, user_message: str, market_notes: str = '', assistant_summary: str = '') -> dict[str, Any]:
    memory = load_memory(path)
    combined = '\n'.join(part for part in (market_notes, user_message) if part.strip())

    client = MarketDataClient()
    resolved = client.resolve_stock(combined)
    if resolved:
        stock_packet = client.get_stock_snapshot(resolved.get('code') or resolved.get('name') or '') or {}
        memory['last_stock'] = {
            'code': resolved.get('code') or '',
            'name': stock_packet.get('name') or resolved.get('name') or '',
            'industry': stock_packet.get('industry') or '',
        }

    position_match = re.search(r'(\d{1,3})\s*[%％]', combined)
    if position_match:
        pct = int(position_match.group(1))
        memory['last_position'] = {
            'pct': pct,
            'text': f'{pct}%仓位',
        }

    if market_notes.strip():
        memory['last_market_notes'] = market_notes.strip()

    if user_message.strip():
        recent_questions = memory.get('recent_questions') or []
        recent_questions.append(user_message.strip())
        memory['recent_questions'] = recent_questions[-MAX_RECENT:]

    if assistant_summary.strip():
        memory['last_answer_summary'] = assistant_summary.strip()[:280]

    memory['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    save_memory(path, memory)
    return memory


def render_markdown(memory: dict[str, Any], mentor_id: str) -> str:
    lines = ['# Session Memory', f'- Mentor: {mentor_id}']
    stock = memory.get('last_stock') or {}
    if stock.get('name'):
        lines.append(f"- Last stock: {stock.get('name')} ({stock.get('code') or '--'})")
    position = memory.get('last_position') or {}
    if position.get('text'):
        lines.append(f"- Last position: {position.get('text')}")
    if memory.get('last_market_notes'):
        lines.append(f"- Last market notes: {memory['last_market_notes']}")
    if memory.get('last_answer_summary'):
        lines.append(f"- Last answer summary: {memory['last_answer_summary']}")
    questions = memory.get('recent_questions') or []
    if questions:
        lines.append('## Recent Questions')
        for item in questions[-5:]:
            lines.append(f'- {item}')
    return '\n'.join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Read or update per-mentor session memory for investor council')
    sub = parser.add_subparsers(dest='command', required=True)

    show = sub.add_parser('show')
    show.add_argument('--mentor-id', required=True)
    show.add_argument('--product-home', default='')
    show.add_argument('--format', choices=('json', 'markdown'), default='markdown')

    update = sub.add_parser('update')
    update.add_argument('--mentor-id', required=True)
    update.add_argument('--product-home', default='')
    update.add_argument('--user-message', required=True)
    update.add_argument('--market-notes', default='')
    update.add_argument('--assistant-summary', default='')
    update.add_argument('--format', choices=('json', 'markdown'), default='markdown')

    clear = sub.add_parser('clear')
    clear.add_argument('--mentor-id', required=True)
    clear.add_argument('--product-home', default='')

    args = parser.parse_args()
    memory_file = memory_file_for_mentor(args.mentor_id, getattr(args, 'product_home', ''))

    if args.command == 'show':
        payload = load_memory(memory_file)
        print(render_markdown(payload, args.mentor_id) if args.format == 'markdown' else json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if args.command == 'update':
        payload = update_memory(memory_file, args.user_message, getattr(args, 'market_notes', ''), getattr(args, 'assistant_summary', ''))
        print(render_markdown(payload, args.mentor_id) if args.format == 'markdown' else json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if args.command == 'clear':
        save_memory(memory_file, default_memory())
        print(f'Cleared session memory for {args.mentor_id}.')


if __name__ == '__main__':
    main()