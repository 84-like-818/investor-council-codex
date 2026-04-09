from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new harvesting project scaffold.")
    parser.add_argument("--project", required=True, help="Project slug, e.g. bernard-baruch")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_root = root / "projects" / args.project
    if project_root.exists():
        raise SystemExit(f"Project already exists: {project_root}")

    for rel in [
        "manifests",
        "data/acquired",
        "data/landing_pages",
        "data/incoming_manual",
        "data/local_library",
        "reports",
        "state",
    ]:
        (project_root / rel).mkdir(parents=True, exist_ok=True)

    shutil.copy(root / "templates" / "seeds_master.template.csv", project_root / "manifests" / "seeds_master.csv")
    (project_root / "README.md").write_text(
        f"# {args.project} project\n\nEdit manifests/seeds_master.csv and run the pipeline.\n",
        encoding="utf-8",
    )
    print(f"Created project scaffold at: {project_root}")


if __name__ == "__main__":
    main()
