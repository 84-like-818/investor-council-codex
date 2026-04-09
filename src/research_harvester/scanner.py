from __future__ import annotations

import csv
import difflib
from pathlib import Path

from .collector import load_manifest
from .db import CatalogDB
from .utils import normalize_text, sha256_file, utc_now_iso

IGNORED_FILE_NAMES = {
    "readme.txt",
    "thumbs.db",
    ".ds_store",
}


def _score_match(file_name: str, title: str) -> float:
    a = normalize_text(file_name)
    b = normalize_text(title)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.99
    return difflib.SequenceMatcher(None, a, b).ratio()


def scan_local_files(project_root: Path) -> None:
    manifest_path = project_root / "manifests" / "seeds_master.csv"
    seeds = [seed for seed in load_manifest(manifest_path) if seed.enabled]
    db = CatalogDB(project_root / "state" / "acquisition.db")

    local_roots = [
        project_root / "data" / "incoming_manual",
        project_root / "data" / "local_library",
    ]
    rows: list[dict[str, object]] = []

    for base in local_roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.name.lower() in IGNORED_FILE_NAMES:
                continue
            best_source_id = None
            best_score = 0.0
            for seed in seeds:
                score = _score_match(path.stem, seed.title)
                if score > best_score:
                    best_source_id = seed.source_id
                    best_score = score
            rows.append(
                {
                    "project": project_root.name,
                    "relative_path": str(path.relative_to(project_root)),
                    "file_name": path.name,
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                    "matched_source_id": best_source_id if best_score >= 0.74 else None,
                    "match_score": best_score,
                    "note": "scanned_local_file",
                    "created_at": utc_now_iso(),
                }
            )

    db.replace_local_items(project_root.name, rows)
    db.close()
