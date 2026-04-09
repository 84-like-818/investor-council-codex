#!/usr/bin/env python3
from pathlib import Path
import argparse, re

def slugify(s: str) -> str:
    s = s.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "council"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--members", required=True, help="逗号分隔，例如 livermore,quality-investor,risk-manager")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    factory_root = Path(__file__).resolve().parent.parent
    slug = slugify(args.slug)
    members = [m.strip() for m in args.members.split(",") if m.strip()]

    members_block = "\n".join([f"- {m}" for m in members])
    member_reads = "\n".join([f"- .agents/skills/{m}/references/" for m in members])

    text = (factory_root / "templates" / "council-skill" / "SKILL.md.template").read_text(encoding="utf-8")
    text = text.replace("{{slug}}", slug).replace("{{members_block}}", members_block).replace("{{member_reads}}", member_reads)

    dst = repo_root / ".agents" / "skills" / slug
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "SKILL.md").write_text(text, encoding="utf-8")
    print(f"已创建 council skill: {dst / 'SKILL.md'}")

if __name__ == "__main__":
    main()
