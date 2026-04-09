from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_harvester.collector import run_collection  # noqa: E402
from research_harvester.reporting import generate_reports  # noqa: E402
from research_harvester.scanner import scan_local_files  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full acquisition pipeline.")
    parser.add_argument("--project", required=True, help="Project name under projects/")
    parser.add_argument("--root", default=str(ROOT), help="Repository root")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if artifacts already exist")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N enabled seeds")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_root = root / "projects" / args.project
    if not project_root.exists():
        raise SystemExit(f"Project not found: {project_root}")

    summary = run_collection(project_root=project_root, force=args.force, limit=args.limit)
    scan_local_files(project_root)
    report_paths = generate_reports(project_root)

    print("\n=== Pipeline finished ===")
    print(f"Project: {args.project}")
    print(
        "Collected:",
        f"{summary.get('downloaded', 0)} downloaded,",
        f"{summary.get('html_content', 0)} html_content,",
        f"{summary.get('landing_only', 0)} landing_only,",
        f"{summary.get('skipped', 0)} skipped",
    )
    print(f"Errors: {summary.get('errors', 0)}")
    print("Reports:")
    for name, path in report_paths.items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    main()
