#!/usr/bin/env python3
from pathlib import Path
import argparse, datetime, shutil, re

def slugify(s: str) -> str:
    s = s.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "session"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--source", required=True, help="一轮讨论整理后的 markdown 文件")
    parser.add_argument("--title", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    src = Path(args.source).resolve()
    skill_root = repo_root / ".agents" / "skills" / args.slug / "data" / "session_distillates"
    skill_root.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        raise SystemExit(f"找不到源文件: {src}")

    date = datetime.date.today().isoformat()
    title = slugify(args.title or src.stem)
    dst = skill_root / f"{date}-{title}.md"
    shutil.copyfile(src, dst)

    print(f"已导入: {dst}")
    print("建议你接着让 Codex 执行：")
    print("请读取这个 session_distillate，并更新 doctrine / anti-patterns / modern-translation / evals，但只保留可复用结论。")

if __name__ == "__main__":
    main()
