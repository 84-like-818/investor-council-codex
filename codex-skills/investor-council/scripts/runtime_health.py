from __future__ import annotations

import json
import os
import platform
from pathlib import Path

from market_data_client import MarketDataClient
from mentor_router import load_registry, ready_mentors
from session_memory import product_home


def health(product_home_override: str = '') -> dict:
    registry = load_registry()
    client = MarketDataClient()
    auth_path = Path.home() / '.codex' / 'auth.json'
    app_home = product_home(product_home_override)
    return {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'registry_path': str((Path(__file__).resolve().parents[1] / 'assets' / 'mentor_registry.json')),
        'ready_mentor_count': len(ready_mentors(registry)),
        'market_client_available': client.available(),
        'memory_root': str(app_home / 'memory'),
        'auth_file_present': auth_path.exists(),
        'local_app_data': os.environ.get('LOCALAPPDATA', ''),
    }


def to_markdown(payload: dict) -> str:
    lines = ['# Runtime Health']
    for key, value in payload.items():
        lines.append(f'- {key}: {value}')
    return '\n'.join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Show local runtime health for investor council skill')
    parser.add_argument('--product-home', default='')
    parser.add_argument('--format', choices=('json', 'markdown'), default='markdown')
    args = parser.parse_args()

    payload = health(args.product_home)
    if args.format == 'json':
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(payload))


if __name__ == '__main__':
    main()