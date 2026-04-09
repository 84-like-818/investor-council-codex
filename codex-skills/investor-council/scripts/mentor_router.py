from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = SKILL_ROOT / 'assets' / 'mentor_registry.json'


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))


def _normalize(text: str) -> str:
    lowered = str(text or '').strip().lower()
    lowered = re.sub(r'[\s\-_/·.]+', '', lowered)
    return lowered


def ready_mentors(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [mentor for mentor in registry.get('mentors', []) if mentor.get('status') == 'ready']


def planned_mentors(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [mentor for mentor in registry.get('mentors', []) if mentor.get('status') != 'ready']


def detect_mentor(text: str, registry: dict[str, Any]) -> dict[str, Any] | None:
    norm_text = _normalize(text)
    if not norm_text:
        return None

    ready = ready_mentors(registry)
    choices = {str(index): mentor for index, mentor in enumerate(ready, start=1)}
    if norm_text in choices:
        return choices[norm_text]

    for mentor in registry.get('mentors', []):
        candidates = [mentor.get('id', ''), mentor.get('display_name_zh', ''), mentor.get('display_name_en', '')]
        candidates.extend(mentor.get('aliases', []) or [])
        for candidate in candidates:
            if candidate and _normalize(candidate) in norm_text:
                return mentor
    return None


def mentor_paths(mentor: dict[str, Any]) -> dict[str, str]:
    pack_path = SKILL_ROOT / 'mentors' / mentor['id']
    return {
        'pack_path': str(pack_path),
        'profile': str(pack_path / 'profile.json'),
        'persona': str(pack_path / 'persona.md'),
        'answer_contract': str(pack_path / 'answer-contract.md'),
        'avatar': str(pack_path / 'avatar.svg'),
    }


def to_markdown_list(registry: dict[str, Any]) -> str:
    lines = ['# 投资大师智能团', '', '## 可立即使用']
    for index, mentor in enumerate(ready_mentors(registry), start=1):
        lines.append(f"{index}. {mentor['display_name_zh']}：{mentor['selection_label']}")
    planned = planned_mentors(registry)
    if planned:
        lines.append('')
        lines.append('## 即将上线')
        for mentor in planned:
            lines.append(f"- {mentor['display_name_zh']}：{mentor['selection_label']}")
    default_id = registry.get('default_mentor')
    if default_id:
        lines.append('')
        lines.append(f"默认导师：{default_id}")
    return '\n'.join(lines)


def to_markdown_show(mentor: dict[str, Any]) -> str:
    paths = mentor_paths(mentor)
    lines = [
        '# Mentor',
        f"- id: {mentor['id']}",
        f"- 中文名: {mentor['display_name_zh']}",
        f"- 英文名: {mentor['display_name_en']}",
        f"- 状态: {mentor['status']}",
        f"- 标签: {mentor['selection_label']}",
        f"- memory namespace: {mentor['memory_namespace']}",
        f"- profile: {paths['profile']}",
        f"- persona: {paths['persona']}",
        f"- answer contract: {paths['answer_contract']}",
        f"- avatar: {paths['avatar']}",
    ]
    return '\n'.join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='List and resolve mentors for the investor council skill')
    sub = parser.add_subparsers(dest='command', required=True)

    list_parser = sub.add_parser('list')
    list_parser.add_argument('--format', choices=('json', 'markdown'), default='markdown')

    show_parser = sub.add_parser('show')
    show_parser.add_argument('--mentor-id', required=True)
    show_parser.add_argument('--format', choices=('json', 'markdown'), default='markdown')

    detect_parser = sub.add_parser('detect')
    detect_parser.add_argument('--text', required=True)
    detect_parser.add_argument('--format', choices=('json', 'markdown'), default='markdown')

    args = parser.parse_args()
    registry = load_registry()

    if args.command == 'list':
        if args.format == 'json':
            print(json.dumps(registry, ensure_ascii=False, indent=2))
        else:
            print(to_markdown_list(registry))
        return

    if args.command == 'show':
        mentor = next((item for item in registry['mentors'] if item['id'] == args.mentor_id), None)
        if not mentor:
            raise SystemExit(f'Unknown mentor id: {args.mentor_id}')
        payload = dict(mentor)
        payload['paths'] = mentor_paths(mentor)
        if args.format == 'json':
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(to_markdown_show(mentor))
        return

    if args.command == 'detect':
        mentor = detect_mentor(args.text, registry)
        if not mentor:
            payload = {'matched': False, 'mentor': None}
        else:
            payload = {'matched': True, 'mentor': mentor, 'paths': mentor_paths(mentor)}
        if args.format == 'json':
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if not payload['matched']:
                print('未匹配到投资人物。')
            else:
                print(to_markdown_show(mentor))


if __name__ == '__main__':
    main()