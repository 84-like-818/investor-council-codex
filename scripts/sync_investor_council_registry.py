from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "config" / "mentor_registry.json"
TARGET_PATH = ROOT / "codex-skills" / "investor-council" / "assets" / "mentor_registry.json"


def load_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_registry(payload: dict) -> None:
    required_top = {
        "bundle_name",
        "bundle_display_name",
        "entry_skill_name",
        "ui_strategy",
        "default_mentor",
        "bootstrap_prompt",
        "requires",
        "mentors",
    }
    missing = required_top - set(payload)
    if missing:
        raise ValueError(f"registry top-level missing keys: {sorted(missing)}")

    if not isinstance(payload.get("mentors"), list) or not payload["mentors"]:
        raise ValueError("registry.mentors must be a non-empty list")

    required_mentor = {
        "id",
        "display_name_zh",
        "display_name_en",
        "status",
        "selection_label",
        "mentor_pack_path",
        "avatar",
        "memory_namespace",
    }
    for mentor in payload["mentors"]:
        missing_mentor = required_mentor - set(mentor)
        if missing_mentor:
            raise ValueError(
                f"mentor {mentor.get('id', '<unknown>')} missing keys: {sorted(missing_mentor)}"
            )


def sync_registry(source: Path, target: Path) -> None:
    payload = load_registry(source)
    validate_registry(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync the canonical investor council mentor registry into the skill asset mirror."
    )
    parser.add_argument("--source", default=str(SOURCE_PATH))
    parser.add_argument("--target", default=str(TARGET_PATH))
    args = parser.parse_args()

    source = Path(args.source).resolve()
    target = Path(args.target).resolve()
    sync_registry(source, target)
    print(f"Synced mentor registry to {target}")


if __name__ == "__main__":
    main()
