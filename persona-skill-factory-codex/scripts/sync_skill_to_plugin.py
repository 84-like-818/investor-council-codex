#!/usr/bin/env python3
from pathlib import Path
import argparse, shutil

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    slug = args.slug.strip().lower()
    plugin_name = f"{slug}-assistant"

    src = repo_root / ".agents" / "skills" / slug
    dst = repo_root / "plugins" / plugin_name / "skills" / slug

    if not src.exists():
        raise SystemExit(f"找不到 skill: {src}")

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"已同步到 plugin: {dst}")

if __name__ == "__main__":
    main()
