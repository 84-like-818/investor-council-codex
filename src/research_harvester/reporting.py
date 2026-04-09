from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from .collector import load_manifest
from .db import CatalogDB
from .utils import ensure_dir


PRIORITY_ORDER = {
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
    "P5": 5,
    "P6": 6,
    "P7": 7,
    "P8": 8,
    "P9": 9,
}

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".epub",
    ".mobi",
    ".azw",
    ".azw3",
    ".zip",
    ".doc",
    ".docx",
    ".rtf",
}

METADATA_EXTENSIONS = {
    ".json",
    ".xml",
    ".csv",
}

SOURCE_PREFIXES = (
    "Project Gutenberg ",
    "Open Library ",
    "Google Books ",
    "Google Play ",
    "Wikimedia Commons ",
    "Chronicling America ",
    "Library of Congress ",
    "LOC ",
    "TIME ",
    "Internet Archive ",
    "HathiTrust ",
    "WorldCat ",
)

KNOWN_TITLE_PATTERNS = (
    ("reminiscences of a stock operator", "Reminiscences of a Stock Operator"),
    ("how to trade in stocks", "How to Trade In Stocks"),
    ("studies in tape reading", "Studies in Tape Reading"),
    ("jesse livermore s methods of trading in stocks", "Jesse Livermore's Methods of Trading in Stocks"),
    ("jesse livermore's methods of trading in stocks", "Jesse Livermore's Methods of Trading in Stocks"),
    ("fourth down", "Fourth Down"),
    ("boy plunger", "Boy Plunger"),
    ("press photo of jesse livermore in 1940", "Press photo of Jesse Livermore in 1940"),
    ("bismarck tribune", "Bismarck Tribune"),
    ("jesse livermore jr", "Jesse Livermore Jr"),
)


def _priority_key(priority: str) -> tuple[int, str]:
    cleaned = (priority or "").strip().upper()
    return PRIORITY_ORDER.get(cleaned, 99), cleaned


def _looks_like_url(value: str) -> bool:
    parsed = urlparse((value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = (value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _compact_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _phrase_key(value: str) -> str:
    lowered = unquote(value or "").lower()
    lowered = lowered.replace("_", " ")
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    return _compact_spaces(lowered)


def _load_source_rows(
    db: CatalogDB,
    project: str,
    source_id: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    artifact_rows = [
        dict(row)
        for row in db.query(
            """
            SELECT kind, local_path, note, mime_type, created_at
            FROM artifacts
            WHERE project = ? AND source_id = ?
            ORDER BY artifact_id DESC
            """,
            (project, source_id),
        )
    ]
    local_rows = [
        dict(row)
        for row in db.query(
            """
            SELECT relative_path, match_score
            FROM local_items
            WHERE project = ? AND matched_source_id = ?
            ORDER BY match_score DESC, local_item_id DESC
            """,
            (project, source_id),
        )
    ]
    lead_rows = [
        dict(row)
        for row in db.query(
            """
            SELECT url, relation, status, note, created_at
            FROM leads
            WHERE project = ? AND source_id = ?
            ORDER BY lead_id DESC
            """,
            (project, source_id),
        )
    ]
    error_rows = [
        dict(row)
        for row in db.query(
            """
            SELECT message, stage, created_at
            FROM errors
            WHERE project = ? AND source_id = ?
            ORDER BY error_id DESC
            """,
            (project, source_id),
        )
    ]
    return artifact_rows, local_rows, lead_rows, error_rows


def _best_status_for_source(
    artifact_rows: list[dict[str, object]],
    local_rows: list[dict[str, object]],
    lead_rows: list[dict[str, object]],
    error_rows: list[dict[str, object]],
) -> tuple[str, str]:
    materialized_rows = [
        row
        for row in artifact_rows
        if row.get("kind") == "html_content"
        or (
            row.get("kind") == "download"
            and not str(row.get("mime_type") or "").lower().startswith("text/html")
        )
    ]
    if materialized_rows:
        best = materialized_rows[0]
        return "HAVE", str(best.get("local_path") or best.get("note") or "")
    if local_rows:
        best = local_rows[0]
        return "HAVE_LOCAL", str(best.get("relative_path") or "")
    if artifact_rows or lead_rows:
        clue = ""
        if artifact_rows:
            best = artifact_rows[0]
            clue = str(best.get("local_path") or best.get("note") or "")
        elif lead_rows:
            best = lead_rows[0]
            clue = str(best.get("url") or "")
        return "LEAD_ONLY", clue
    if error_rows:
        err = error_rows[0]
        return "MISSING", f"{err.get('stage', '')}:{err.get('message', '')}"
    return "UNSEEN", ""


def _latest_error(error_rows: list[dict[str, object]]) -> str:
    if not error_rows:
        return ""
    latest = error_rows[0]
    return f"{latest.get('stage', '')}:{latest.get('message', '')}"


def _manual_urls(row: dict[str, str], lead_rows: list[dict[str, object]], clue: str) -> list[str]:
    candidates = [row.get("url", ""), row.get("landing_url", "")]
    candidates.extend(str(lead.get("url") or "") for lead in lead_rows)
    if _looks_like_url(clue):
        candidates.append(clue)
    return _dedupe(candidates)


def _next_action(row: dict[str, str], status: str, clue: str) -> str:
    manual_action = row.get("manual_action", "").strip()
    access_mode = (row.get("access_mode") or "").strip()
    if status in {"HAVE", "HAVE_LOCAL"}:
        return "Already acquired"
    if manual_action:
        return manual_action
    if status == "LEAD_ONLY":
        return "Review lead_queue.csv and saved landing pages for candidate links"
    if access_mode in {"restricted", "preview"}:
        return "Sign in / borrow / purchase manually, then drop the file into incoming_manual/"
    if access_mode == "landing":
        return "Inspect the landing page and follow candidate download links"
    if _looks_like_url(clue):
        return f"Open the saved clue URL manually: {clue}"
    return "Check whether the URL is stale and update the manifest"


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_manual_markdown(project_root: Path, manual_rows: list[dict[str, object]]) -> Path:
    path = project_root / "reports" / "manual_work_queue.md"
    drop_dir = project_root / "data" / "incoming_manual"
    lines = [
        f"# Manual work queue for {project_root.name}",
        "",
        "Drop completed files into:",
        f"`{drop_dir}`",
        "",
    ]

    if not manual_rows:
        lines.extend(["No missing items were found.", ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    current_priority = None
    for row in manual_rows:
        priority = str(row.get("priority") or "Unprioritized")
        if priority != current_priority:
            if current_priority is not None:
                lines.append("")
            lines.append(f"## {priority}")
            lines.append("")
            current_priority = priority
        lines.append(f"- [ ] {row['source_id']} | {row['title']}")
        lines.append(f"  Status: {row['status']}")
        if row.get("manual_url"):
            lines.append(f"  Open first: {row['manual_url']}")
        if row.get("alternate_url"):
            lines.append(f"  Backup link: {row['alternate_url']}")
        if row.get("last_error"):
            lines.append(f"  Last error: {row['last_error']}")
        if row.get("best_clue"):
            lines.append(f"  Best clue: {row['best_clue']}")
        lines.append(f"  Next action: {row['next_action']}")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_titles_only(
    project_root: Path,
    rows: list[dict[str, object]],
    filename: str = "manual_titles_only.txt",
) -> Path:
    path = project_root / "reports" / filename
    titles: list[str] = []
    seen: set[str] = set()
    for row in rows:
        title = str(row.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        titles.append(title)
    path.write_text("\n".join(titles) + ("\n" if titles else ""), encoding="utf-8")
    return path


def _extract_title_from_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if not parts:
        return ""

    slug = ""
    if "about" in parts:
        index = parts.index("about")
        if index + 1 < len(parts):
            slug = parts[index + 1]
    elif "details" in parts:
        index = parts.index("details")
        if index + 1 < len(parts):
            slug = parts[index + 1]
    elif parts[0] in {"books", "works"} and len(parts) >= 3:
        slug = parts[2]
    elif parts[0] == "wiki" and len(parts) >= 2:
        slug = parts[1].split(":", 1)[-1]
    elif len(parts) >= 1:
        slug = parts[-1]

    slug = slug.strip()
    if not slug:
        return ""

    if slug.lower().endswith((".html", ".htm")):
        slug = Path(slug).stem
    elif slug.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp")):
        slug = Path(slug).stem

    return _compact_spaces(slug.replace("_", " "))


def _match_known_title(*candidates: str) -> str:
    for candidate in candidates:
        key = _phrase_key(candidate)
        if not key:
            continue
        for pattern, canonical in KNOWN_TITLE_PATTERNS:
            if pattern in key:
                return canonical
    return ""


def _cleanup_search_title(value: str) -> str:
    cleaned = (value or "").strip()
    for prefix in SOURCE_PREFIXES:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):]
            break

    patterns = [
        r"\bpart\s+\d+\b",
        r"\bwork\s+page\b",
        r"\bmain\s+page\b",
        r"\bebook\s+page\b",
        r"\baudiobook\s+page\b",
        r"\bfull\s+text\b",
        r"\bold\s+html\s+mirror\b",
        r"\bhtml\s+zip\b",
        r"\bfull\s+photo\b",
        r"\bcropped\s+photo\b",
        r"\billustrated\s+edition\b",
        r"\bannotated\s+edition\b",
        r"\bfacsimile\b",
        r"\bedition\b",
        r"\bpage\s+mentioning\b.*$",
        r"\b\d{4}\b",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+'s\b", "'s", cleaned)
    cleaned = _compact_spaces(cleaned)
    return cleaned.strip(" -_,")


def _search_title(row: dict[str, str]) -> str:
    url_title = _extract_title_from_url(row.get("url", "") or row.get("landing_url", ""))
    known = _match_known_title(url_title, row.get("title", ""))
    if known:
        return known

    cleaned_url_title = _cleanup_search_title(url_title)
    if cleaned_url_title:
        return cleaned_url_title

    cleaned_title = _cleanup_search_title(row.get("title", ""))
    return cleaned_title or (row.get("title", "") or "").strip()


def _write_search_titles_only(project_root: Path, rows: list[dict[str, object]]) -> Path:
    path = project_root / "reports" / "strict_search_titles_only.txt"
    titles: list[str] = []
    seen: set[str] = set()
    for row in rows:
        title = str(row.get("search_title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        titles.append(title)
    path.write_text("\n".join(titles) + ("\n" if titles else ""), encoding="utf-8")
    return path


def _artifact_class(row: dict[str, object]) -> str:
    kind = str(row.get("kind") or "")
    mime = str(row.get("mime_type") or "").split(";")[0].strip().lower()
    local_path = str(row.get("local_path") or "")
    suffix = Path(local_path).suffix.lower()

    if kind == "html_content":
        return "html_content"
    if kind == "landing_page":
        return "landing_page"
    if kind == "error_page":
        return "error_page"
    if kind != "download":
        return "other"

    if mime.startswith("text/html"):
        return "html_download"
    if mime.startswith("image/"):
        return "image"
    if mime in {"application/json", "text/csv", "application/xml", "text/xml"} or suffix in METADATA_EXTENSIONS:
        return "metadata"
    if (
        mime.startswith("text/plain")
        or mime.startswith("application/pdf")
        or mime.startswith("application/zip")
        or "epub" in mime
        or "mobipocket" in mime
        or suffix in DOCUMENT_EXTENSIONS
    ):
        return "document"
    return "binary"


def _is_discovery_noise(row: dict[str, str]) -> bool:
    source_type = (row.get("source_type") or "").strip().lower()
    category = (row.get("category") or "").strip().lower()
    title = (row.get("title") or "").strip().lower()
    if source_type == "search" or category == "search":
        return True
    if "category:" in title:
        return True
    if category == "image" and " category" in title:
        return True
    return False


def _needs_image_asset(row: dict[str, str]) -> bool:
    title = (row.get("title") or "").strip().lower()
    return (row.get("category") or "").strip().lower() == "image" and "category" not in title


def _expects_non_html_file(row: dict[str, str]) -> bool:
    expected = {part.strip().lower() for part in (row.get("expected_formats") or "").split(",") if part.strip()}
    return bool(expected.intersection({"pdf", "txt", "epub", "mobi", "zip", "jpg", "jpeg", "png", "gif", "webp", "tif", "tiff"}))


def _source_has_fulltext_artifact(row: dict[str, str], artifact_rows: list[dict[str, object]]) -> bool:
    classes = [_artifact_class(artifact) for artifact in artifact_rows]
    source_type = (row.get("source_type") or "").strip().lower()

    if _needs_image_asset(row):
        return "image" in classes

    if source_type == "catalog":
        return "document" in classes

    if source_type == "article":
        return "document" in classes or "html_content" in classes

    if source_type == "direct_file":
        expected = (row.get("expected_formats") or "").strip().lower()
        if expected == "html":
            return "html_content" in classes or "document" in classes
        return "document" in classes or "html_content" in classes

    if source_type == "landing_page":
        if _expects_non_html_file(row):
            return "document" in classes or "image" in classes
        return "html_content" in classes

    return "document" in classes or "html_content" in classes


def _strict_missing_reason(row: dict[str, str], artifact_rows: list[dict[str, object]]) -> str:
    classes = {_artifact_class(artifact) for artifact in artifact_rows}
    source_type = (row.get("source_type") or "").strip().lower()

    if not artifact_rows:
        return "No artifact captured at all"
    if _needs_image_asset(row):
        if "html_download" in classes or "landing_page" in classes:
            return "Only image page HTML was captured; original image file is still missing"
        return "No original image file was captured"
    if source_type == "catalog":
        if "html_content" in classes or "landing_page" in classes:
            return "Only catalog / preview / metadata pages were captured; full file is still missing"
        if "metadata" in classes:
            return "Only metadata or cover assets were captured; full file is still missing"
        return "No full-text file was captured from the catalog source"
    if source_type == "article":
        return "Article landing pages or error pages were captured, but not the complete article text/file"
    if source_type == "direct_file":
        return "Expected direct full-text file was not captured"
    if "metadata" in classes:
        return "Only metadata-like files were captured"
    return "Only clues / landing pages were captured; no complete full-text file yet"


def _current_state_label(artifact_rows: list[dict[str, object]]) -> str:
    classes = {_artifact_class(artifact) for artifact in artifact_rows}
    if not classes:
        return "no_artifact"
    ordered = [
        "document",
        "image",
        "html_content",
        "metadata",
        "landing_page",
        "html_download",
        "error_page",
        "other",
        "binary",
    ]
    present = [label for label in ordered if label in classes]
    return ",".join(present) if present else "other"


def _write_strict_markdown(project_root: Path, strict_rows: list[dict[str, object]]) -> Path:
    path = project_root / "reports" / "strict_fulltext_missing.md"
    lines = [
        f"# Strict full-text missing list for {project_root.name}",
        "",
        "Only sources that should resolve to a real full text / full file are included here.",
        "Search pages, category pages, and discovery-only noise are excluded.",
        "",
    ]

    if not strict_rows:
        lines.extend(["No strict full-text gaps were found.", ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    current_priority = None
    for row in strict_rows:
        priority = str(row.get("priority") or "Unprioritized")
        if priority != current_priority:
            if current_priority is not None:
                lines.append("")
            lines.append(f"## {priority}")
            lines.append("")
            current_priority = priority
        lines.append(f"- [ ] {row['source_id']} | {row['title']}")
        if row.get("search_title"):
            lines.append(f"  Search title: {row['search_title']}")
        lines.append(f"  Current state: {row['current_state']}")
        lines.append(f"  Why still missing: {row['why_missing']}")
        if row.get("manual_url"):
            lines.append(f"  Primary link: {row['manual_url']}")
        if row.get("alternate_url"):
            lines.append(f"  Backup link: {row['alternate_url']}")
        if row.get("best_clue"):
            lines.append(f"  Best clue: {row['best_clue']}")
        if row.get("last_error"):
            lines.append(f"  Last error: {row['last_error']}")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def generate_reports(project_root: Path) -> dict[str, str]:
    project = project_root.name
    manifest_path = project_root / "manifests" / "seeds_master.csv"
    reports_dir = ensure_dir(project_root / "reports")
    db = CatalogDB(project_root / "state" / "acquisition.db")
    seeds = [seed.raw for seed in load_manifest(manifest_path)]

    master_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []
    manual_rows: list[dict[str, object]] = []
    strict_rows: list[dict[str, object]] = []

    for row in seeds:
        if (row.get("enabled") or "1").lower() in {"0", "false", "no"}:
            continue

        source_id = row["source_id"]
        artifact_rows, local_rows, lead_rows, error_rows = _load_source_rows(db, project, source_id)
        status, clue = _best_status_for_source(artifact_rows, local_rows, lead_rows, error_rows)
        manual_urls = _manual_urls(row, lead_rows, clue)
        primary_manual_url = manual_urls[0] if manual_urls else ""
        alternate_manual_url = manual_urls[1] if len(manual_urls) > 1 else ""
        latest_error = _latest_error(error_rows)

        master = {
            "source_id": source_id,
            "title": row.get("title", ""),
            "priority": row.get("priority", ""),
            "category": row.get("category", ""),
            "access_mode": row.get("access_mode", ""),
            "license": row.get("license", ""),
            "status": status,
            "best_clue": clue,
            "manual_url": primary_manual_url,
            "alternate_url": alternate_manual_url,
            "last_error": latest_error,
            "lead_count": len(lead_rows),
            "error_count": len(error_rows),
            "url": row.get("url", ""),
            "landing_url": row.get("landing_url", ""),
            "expected_formats": row.get("expected_formats", ""),
            "manual_action": row.get("manual_action", ""),
            "notes": row.get("notes", ""),
        }
        master_rows.append(master)

        if status not in {"HAVE", "HAVE_LOCAL"}:
            next_action = _next_action(row, status, clue)
            missing_item = {**master, "next_action": next_action}
            missing_rows.append(missing_item)
            manual_rows.append(
                {
                    "source_id": source_id,
                    "title": row.get("title", ""),
                    "priority": row.get("priority", ""),
                    "status": status,
                    "manual_url": primary_manual_url,
                    "alternate_url": alternate_manual_url,
                    "url": row.get("url", ""),
                    "landing_url": row.get("landing_url", ""),
                    "best_clue": clue,
                    "last_error": latest_error,
                    "expected_formats": row.get("expected_formats", ""),
                    "manual_action": row.get("manual_action", ""),
                    "next_action": next_action,
                    "drop_folder": str(project_root / "data" / "incoming_manual"),
                }
            )

        if not _is_discovery_noise(row) and not _source_has_fulltext_artifact(row, artifact_rows):
            strict_rows.append(
                {
                    "source_id": source_id,
                    "title": row.get("title", ""),
                    "search_title": _search_title(row),
                    "priority": row.get("priority", ""),
                    "category": row.get("category", ""),
                    "source_type": row.get("source_type", ""),
                    "access_mode": row.get("access_mode", ""),
                    "license": row.get("license", ""),
                    "current_state": _current_state_label(artifact_rows),
                    "why_missing": _strict_missing_reason(row, artifact_rows),
                    "manual_url": primary_manual_url,
                    "alternate_url": alternate_manual_url,
                    "best_clue": clue,
                    "last_error": latest_error,
                    "expected_formats": row.get("expected_formats", ""),
                    "manual_action": row.get("manual_action", ""),
                    "drop_folder": str(project_root / "data" / "incoming_manual"),
                }
            )

    master_path = reports_dir / "master_index.csv"
    _write_csv(
        master_path,
        master_rows,
        [
            "source_id",
            "title",
            "priority",
            "category",
            "access_mode",
            "license",
            "status",
            "best_clue",
            "manual_url",
            "alternate_url",
            "last_error",
            "lead_count",
            "error_count",
            "url",
            "landing_url",
            "expected_formats",
            "manual_action",
            "notes",
        ],
    )

    missing_rows.sort(key=lambda row: (_priority_key(str(row.get("priority", ""))), str(row.get("status", "")), str(row.get("source_id", ""))))
    missing_path = reports_dir / "missing_sources.csv"
    _write_csv(
        missing_path,
        missing_rows,
        [
            "source_id",
            "title",
            "priority",
            "category",
            "access_mode",
            "license",
            "status",
            "best_clue",
            "manual_url",
            "alternate_url",
            "last_error",
            "lead_count",
            "error_count",
            "url",
            "landing_url",
            "expected_formats",
            "manual_action",
            "notes",
            "next_action",
        ],
    )

    lead_rows = [
        dict(row)
        for row in db.query(
            """
            SELECT source_id, url, relation, status, title, note, created_at
            FROM leads
            WHERE project = ?
            ORDER BY lead_id DESC
            """,
            (project,),
        )
    ]
    lead_path = reports_dir / "lead_queue.csv"
    _write_csv(
        lead_path,
        lead_rows,
        ["source_id", "url", "relation", "status", "title", "note", "created_at"],
    )

    holdings_rows = [
        dict(row)
        for row in db.query(
            """
            SELECT source_id, kind, status, source_url, local_path, mime_type, sha256, size_bytes, title, note, created_at
            FROM artifacts
            WHERE project = ?
            ORDER BY artifact_id DESC
            """,
            (project,),
        )
    ]
    holdings_path = reports_dir / "holdings_catalog.csv"
    _write_csv(
        holdings_path,
        holdings_rows,
        [
            "source_id",
            "kind",
            "status",
            "source_url",
            "local_path",
            "mime_type",
            "sha256",
            "size_bytes",
            "title",
            "note",
            "created_at",
        ],
    )

    unmatched_rows = [
        dict(row)
        for row in db.query(
            """
            SELECT relative_path, file_name, sha256, size_bytes, matched_source_id, match_score, note, created_at
            FROM local_items
            WHERE project = ? AND (matched_source_id IS NULL OR matched_source_id = '')
            ORDER BY local_item_id DESC
            """,
            (project,),
        )
    ]
    unmatched_path = reports_dir / "unmatched_local_files.csv"
    _write_csv(
        unmatched_path,
        unmatched_rows,
        ["relative_path", "file_name", "sha256", "size_bytes", "matched_source_id", "match_score", "note", "created_at"],
    )

    manual_rows.sort(key=lambda row: (_priority_key(str(row.get("priority", ""))), str(row.get("status", "")), str(row.get("source_id", ""))))
    manual_path = reports_dir / "manual_work_queue.csv"
    _write_csv(
        manual_path,
        manual_rows,
        [
            "source_id",
            "title",
            "priority",
            "status",
            "manual_url",
            "alternate_url",
            "url",
            "landing_url",
            "best_clue",
            "last_error",
            "expected_formats",
            "manual_action",
            "next_action",
            "drop_folder",
        ],
    )
    manual_md_path = _write_manual_markdown(project_root, manual_rows)
    manual_titles_only_path = _write_titles_only(project_root, manual_rows)

    strict_rows.sort(
        key=lambda row: (
            _priority_key(str(row.get("priority", ""))),
            str(row.get("source_type", "")),
            str(row.get("source_id", "")),
        )
    )
    strict_path = reports_dir / "strict_fulltext_missing.csv"
    _write_csv(
        strict_path,
        strict_rows,
        [
            "source_id",
            "title",
            "search_title",
            "priority",
            "category",
            "source_type",
            "access_mode",
            "license",
            "current_state",
            "why_missing",
            "manual_url",
            "alternate_url",
            "best_clue",
            "last_error",
            "expected_formats",
            "manual_action",
            "drop_folder",
        ],
    )
    strict_md_path = _write_strict_markdown(project_root, strict_rows)
    strict_titles_only_path = _write_titles_only(
        project_root,
        strict_rows,
        "strict_fulltext_titles_only.txt",
    )
    strict_search_titles_only_path = _write_search_titles_only(project_root, strict_rows)

    counts = {
        "total": len(master_rows),
        "have": sum(1 for row in master_rows if row["status"] == "HAVE"),
        "have_local": sum(1 for row in master_rows if row["status"] == "HAVE_LOCAL"),
        "lead_only": sum(1 for row in master_rows if row["status"] == "LEAD_ONLY"),
        "missing": sum(1 for row in master_rows if row["status"] == "MISSING"),
        "unseen": sum(1 for row in master_rows if row["status"] == "UNSEEN"),
        "strict_fulltext_missing": len(strict_rows),
    }
    dashboard_path = reports_dir / "dashboard.md"
    top_missing = [row for row in missing_rows if row.get("priority") == "P1"][:10]
    lines = [
        f"# {project} acquisition dashboard",
        "",
        f"- Total sources: {counts['total']}",
        f"- Acquired by pipeline: {counts['have']}",
        f"- Available locally only: {counts['have_local']}",
        f"- Clue only: {counts['lead_only']}",
        f"- Missing with recorded errors: {counts['missing']}",
        f"- Unseen: {counts['unseen']}",
        f"- Strict full-text / original-file gaps: {counts['strict_fulltext_missing']}",
        "",
        "## Highest-priority missing items",
        "",
    ]
    if top_missing:
        for row in top_missing:
            lines.append(f"- `{row['source_id']}` {row['title']} | {row['status']} | {row['next_action']}")
    else:
        lines.append("- No P1 items are currently missing.")
    lines += [
        "",
        "## Output files",
        "",
        "- `master_index.csv`: full status index",
        "- `missing_sources.csv`: missing items with next actions",
        "- `manual_work_queue.csv`: links to open manually and intake instructions",
        "- `manual_work_queue.md`: human-friendly manual checklist",
        "- `manual_titles_only.txt`: missing titles only",
        "- `strict_fulltext_missing.csv`: strict gaps where a real full text / original file is still missing",
        "- `strict_fulltext_missing.md`: human-friendly strict full-text checklist",
        "- `strict_fulltext_titles_only.txt`: strict full-text titles only",
        "- `strict_search_titles_only.txt`: deduplicated search-ready titles only",
        "- `lead_queue.csv`: candidate links and redirects",
        "- `holdings_catalog.csv`: collected artifacts",
        "- `unmatched_local_files.csv`: local files that did not match a source",
    ]
    dashboard_path.write_text("\n".join(lines), encoding="utf-8")

    db.close()
    return {
        "master_index": str(master_path),
        "missing_sources": str(missing_path),
        "lead_queue": str(lead_path),
        "holdings_catalog": str(holdings_path),
        "unmatched_local_files": str(unmatched_path),
        "manual_work_queue": str(manual_path),
        "manual_work_queue_md": str(manual_md_path),
        "manual_titles_only": str(manual_titles_only_path),
        "strict_fulltext_missing": str(strict_path),
        "strict_fulltext_missing_md": str(strict_md_path),
        "strict_fulltext_titles_only": str(strict_titles_only_path),
        "strict_search_titles_only": str(strict_search_titles_only_path),
        "dashboard": str(dashboard_path),
    }
