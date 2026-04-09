from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .constants import (
    DOWNLOADABLE_EXTENSIONS,
    DOWNLOADABLE_MIME_PREFIXES,
    DOWNLOAD_HINT_WORDS,
    HTML_MIME_PREFIXES,
)
from .db import CatalogDB
from .utils import detect_extension, ensure_dir, safe_filename, safe_slug, sha256_file, write_json


@dataclass
class Seed:
    source_id: str
    title: str
    url: str
    landing_url: str
    category: str
    source_type: str
    access_mode: str
    priority: str
    license: str
    tags: str
    expected_formats: str
    manual_action: str
    notes: str
    enabled: bool
    raw: dict[str, str]


def load_settings(repo_root: Path) -> dict[str, Any]:
    settings_path = repo_root / "config" / "settings.json"
    example_path = repo_root / "config" / "settings.example.json"
    if settings_path.exists():
        return json.loads(settings_path.read_text(encoding="utf-8"))
    return json.loads(example_path.read_text(encoding="utf-8"))


def load_manifest(manifest_path: Path) -> list[Seed]:
    rows: list[Seed] = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            enabled_value = (row.get("enabled") or "1").strip()
            rows.append(
                Seed(
                    source_id=(row.get("source_id") or "").strip(),
                    title=(row.get("title") or "").strip(),
                    url=(row.get("url") or "").strip(),
                    landing_url=(row.get("landing_url") or "").strip(),
                    category=(row.get("category") or "").strip(),
                    source_type=(row.get("source_type") or "").strip(),
                    access_mode=(row.get("access_mode") or "").strip(),
                    priority=(row.get("priority") or "").strip(),
                    license=(row.get("license") or "").strip(),
                    tags=(row.get("tags") or "").strip(),
                    expected_formats=(row.get("expected_formats") or "").strip(),
                    manual_action=(row.get("manual_action") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                    enabled=enabled_value.lower() not in {"0", "false", "no"},
                    raw=row,
                )
            )
    return rows


def _make_session(settings: dict[str, Any]) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": settings.get("user_agent", "LivermoreHarvester/1.0")})
    extra_headers = settings.get("extra_headers") or {}
    if isinstance(extra_headers, dict):
        session.headers.update(extra_headers)
    cookies_json = settings.get("cookies_json")
    if cookies_json:
        cookie_path = Path(cookies_json)
        if cookie_path.exists():
            try:
                cookie_payload = json.loads(cookie_path.read_text(encoding="utf-8"))
                for key, value in cookie_payload.items():
                    session.cookies.set(key, value)
            except Exception:
                pass
    return session


def _is_probably_download(url: str, content_type: str | None) -> bool:
    if content_type:
        content_type = content_type.split(";")[0].strip().lower()
        if any(content_type.startswith(prefix) for prefix in HTML_MIME_PREFIXES):
            return False
        if any(content_type.startswith(prefix) for prefix in DOWNLOADABLE_MIME_PREFIXES):
            return True
    lowered = url.lower()
    if any(lowered.endswith(ext) for ext in DOWNLOADABLE_EXTENSIONS):
        return True
    return False


def _is_html(content_type: str | None) -> bool:
    if not content_type:
        return False
    content_type = content_type.split(";")[0].strip().lower()
    return any(content_type.startswith(prefix) for prefix in HTML_MIME_PREFIXES)


def _extract_candidates(html: str, base_url: str) -> tuple[str, list[dict[str, Any]], int]:
    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    body_text = soup.get_text(" ", strip=True)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if href in seen:
            continue
        seen.add(href)
        anchor_text = " ".join(a.stripped_strings)
        lowered = f"{href} {anchor_text}".lower()
        score = 0
        if any(href.lower().endswith(ext) for ext in DOWNLOADABLE_EXTENSIONS):
            score += 5
        if any(word in lowered for word in DOWNLOAD_HINT_WORDS):
            score += 3
        if urlparse(href).netloc == urlparse(base_url).netloc:
            score += 1
        if score > 0:
            candidates.append({"url": href, "text": anchor_text, "score": score})
    candidates.sort(key=lambda item: (-item["score"], item["url"]))
    return page_title, candidates, len(body_text)


def _save_stream_to_file(response: requests.Response, target_path: Path, max_download_bytes: int) -> tuple[int, str]:
    total = 0
    with target_path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_download_bytes:
                raise RuntimeError(f"File too large: exceeded {max_download_bytes} bytes")
            fh.write(chunk)
    return total, sha256_file(target_path)


def _save_html_snapshot(seed_dir: Path, file_stem: str, html: str, metadata: dict[str, Any]) -> Path:
    html_path = seed_dir / f"{file_stem}.html"
    meta_path = seed_dir / f"{file_stem}.meta.json"
    html_path.write_text(html, encoding="utf-8", errors="ignore")
    write_json(meta_path, metadata)
    return html_path


def _save_response_html_snapshot(
    *,
    base_dir: Path,
    file_stem: str,
    response: requests.Response,
    metadata: dict[str, Any],
) -> Path | None:
    try:
        html = response.text
    except Exception:
        return None
    if not html:
        return None
    snapshot_metadata = {
        "final_url": response.url,
        "content_type": response.headers.get("Content-Type", ""),
        "status_code": response.status_code,
        **metadata,
    }
    return _save_html_snapshot(base_dir, file_stem, html, snapshot_metadata)


def _record_final_url(
    *,
    db: CatalogDB,
    project: str,
    source_id: str,
    run_id: int,
    original_url: str,
    final_url: str,
    relation: str,
    title: str,
) -> None:
    if not final_url or final_url == original_url:
        return
    db.add_lead(
        project=project,
        source_id=source_id,
        run_id=run_id,
        url=final_url,
        relation=relation,
        status="resolved",
        title=title,
        note=f"redirected_from={original_url}",
    )


def _attempt_candidate_downloads(
    *,
    db: CatalogDB,
    session: requests.Session,
    settings: dict[str, Any],
    project: str,
    seed: Seed,
    run_id: int,
    seed_dir: Path,
    candidates: list[dict[str, Any]],
) -> int:
    downloaded = 0
    max_attempts = int(settings.get("max_candidate_attempts", 8))
    timeout = int(settings.get("timeout_seconds", 25))
    max_download_bytes = int(settings.get("max_download_bytes", 50 * 1024 * 1024))

    for idx, candidate in enumerate(candidates[:max_attempts], start=1):
        url = candidate["url"]
        db.add_lead(
            project=project,
            source_id=seed.source_id,
            run_id=run_id,
            url=url,
            relation="candidate",
            status="discovered",
            title=candidate.get("text", ""),
            note=f"candidate_score={candidate.get('score', 0)}",
        )
        try:
            response = session.get(url, timeout=timeout, stream=True, allow_redirects=True)
            content_type = response.headers.get("Content-Type", "")
            _record_final_url(
                db=db,
                project=project,
                source_id=seed.source_id,
                run_id=run_id,
                original_url=url,
                final_url=response.url,
                relation="candidate_final",
                title=candidate.get("text", "") or seed.title,
            )
            if response.status_code >= 400:
                db.add_lead(
                    project=project,
                    source_id=seed.source_id,
                    run_id=run_id,
                    url=response.url or url,
                    relation="candidate",
                    status=f"http_{response.status_code}",
                    title=candidate.get("text", "") or seed.title,
                    note=f"candidate_score={candidate.get('score', 0)};content_type={content_type}",
                )
                snapshot_path = None
                if _is_html(content_type):
                    snapshot_path = _save_response_html_snapshot(
                        base_dir=seed_dir,
                        file_stem=f"candidate_{idx:02d}_error_{response.status_code}",
                        response=response,
                        metadata={
                            "candidate": candidate,
                            "requested_url": url,
                        },
                    )
                if snapshot_path:
                    db.add_artifact(
                        project=project,
                        source_id=seed.source_id,
                        run_id=run_id,
                        kind="error_page",
                        status=f"http_{response.status_code}",
                        source_url=response.url,
                        local_path=str(snapshot_path),
                        mime_type=content_type,
                        sha256=sha256_file(snapshot_path),
                        size_bytes=snapshot_path.stat().st_size,
                        http_status=response.status_code,
                        title=seed.title,
                        note=f"candidate_http_error:{candidate.get('text', '')}",
                    )
                db.add_error(
                    project=project,
                    source_id=seed.source_id,
                    run_id=run_id,
                    url=url,
                    stage="candidate_fetch",
                    message=f"http_{response.status_code}",
                )
                continue
            if _is_probably_download(response.url, content_type):
                ext = detect_extension(response.url, content_type) or ".bin"
                target = seed_dir / f"candidate_{idx:02d}{ext}"
                size_bytes, file_hash = _save_stream_to_file(response, target, max_download_bytes)
                db.add_artifact(
                    project=project,
                    source_id=seed.source_id,
                    run_id=run_id,
                    kind="download",
                    status="ok",
                    source_url=response.url,
                    local_path=str(target),
                    mime_type=content_type,
                    sha256=file_hash,
                    size_bytes=size_bytes,
                    http_status=response.status_code,
                    title=seed.title,
                    note=f"candidate_download:{candidate.get('text', '')}",
                )
                downloaded += 1
                time.sleep(float(settings.get("sleep_seconds_between_requests", 1.0)))
            elif _is_html(content_type):
                # Preserve interesting candidate HTML pages as extra leads
                try:
                    html = response.text
                except Exception:
                    html = ""
                if html:
                    snapshot_path = _save_html_snapshot(
                        seed_dir,
                        f"candidate_{idx:02d}_page",
                        html,
                        {
                            "candidate": candidate,
                            "final_url": response.url,
                            "content_type": content_type,
                            "status_code": response.status_code,
                        },
                    )
                    db.add_artifact(
                        project=project,
                        source_id=seed.source_id,
                        run_id=run_id,
                        kind="landing_page",
                        status="ok",
                        source_url=response.url,
                        local_path=str(snapshot_path),
                        mime_type=content_type,
                        sha256=sha256_file(snapshot_path),
                        size_bytes=snapshot_path.stat().st_size,
                        http_status=response.status_code,
                        title=seed.title,
                        note=f"candidate_html:{candidate.get('text', '')}",
                    )
            time.sleep(float(settings.get("sleep_seconds_between_requests", 1.0)))
        except Exception as exc:
            db.add_lead(
                project=project,
                source_id=seed.source_id,
                run_id=run_id,
                url=url,
                relation="candidate",
                status="request_failed",
                title=candidate.get("text", "") or seed.title,
                note=str(exc),
            )
            db.add_error(
                project=project,
                source_id=seed.source_id,
                run_id=run_id,
                url=url,
                stage="candidate_exception",
                message=str(exc),
            )
    return downloaded


def _seed_already_downloaded(db: CatalogDB, project: str, source_id: str) -> bool:
    rows = db.query(
        """
        SELECT 1 FROM artifacts
        WHERE project = ? AND source_id = ? AND kind IN ('download', 'html_content')
        LIMIT 1
        """,
        (project, source_id),
    )
    return bool(rows)


def _process_seed(
    *,
    project_root: Path,
    db: CatalogDB,
    session: requests.Session,
    settings: dict[str, Any],
    run_id: int,
    seed: Seed,
    force: bool,
) -> dict[str, int]:
    summary = {"downloaded": 0, "html_content": 0, "landing_only": 0, "errors": 0, "skipped": 0}
    project = project_root.name
    if not seed.enabled:
        summary["skipped"] += 1
        return summary
    if not force and _seed_already_downloaded(db, project, seed.source_id):
        summary["skipped"] += 1
        return summary

    target_url = seed.url or seed.landing_url
    if not target_url:
        db.add_error(
            project=project,
            source_id=seed.source_id,
            run_id=run_id,
            url="",
            stage="manifest",
            message="missing_url",
        )
        summary["errors"] += 1
        return summary

    timeout = int(settings.get("timeout_seconds", 25))
    max_download_bytes = int(settings.get("max_download_bytes", 50 * 1024 * 1024))
    seed_dir = ensure_dir(project_root / "data" / "acquired" / seed.source_id)
    landing_dir = ensure_dir(project_root / "data" / "landing_pages" / seed.source_id)

    try:
        db.add_lead(
            project=project,
            source_id=seed.source_id,
            run_id=run_id,
            url=target_url,
            relation="seed",
            status="queued",
            title=seed.title,
            note=f"access_mode={seed.access_mode};source_type={seed.source_type};expected_formats={seed.expected_formats}",
        )
        response = session.get(target_url, timeout=timeout, stream=True, allow_redirects=True)
        content_type = response.headers.get("Content-Type", "")
        _record_final_url(
            db=db,
            project=project,
            source_id=seed.source_id,
            run_id=run_id,
            original_url=target_url,
            final_url=response.url,
            relation="seed_final",
            title=seed.title,
        )
        if response.status_code >= 400:
            db.add_lead(
                project=project,
                source_id=seed.source_id,
                run_id=run_id,
                url=response.url or target_url,
                relation="seed",
                status=f"http_{response.status_code}",
                title=seed.title,
                note=f"content_type={content_type}",
            )
            snapshot_path = None
            if _is_html(content_type):
                snapshot_path = _save_response_html_snapshot(
                    base_dir=landing_dir,
                    file_stem=f"error_{response.status_code}",
                    response=response,
                    metadata={
                        "source_id": seed.source_id,
                        "seed_title": seed.title,
                        "requested_url": target_url,
                    },
                )
            if snapshot_path:
                db.add_artifact(
                    project=project,
                    source_id=seed.source_id,
                    run_id=run_id,
                    kind="error_page",
                    status=f"http_{response.status_code}",
                    source_url=response.url,
                    local_path=str(snapshot_path),
                    mime_type=content_type,
                    sha256=sha256_file(snapshot_path),
                    size_bytes=snapshot_path.stat().st_size,
                    http_status=response.status_code,
                    title=seed.title,
                    note=seed.notes,
                )
            db.add_error(
                project=project,
                source_id=seed.source_id,
                run_id=run_id,
                url=target_url,
                stage="fetch",
                message=f"http_{response.status_code}",
            )
            summary["errors"] += 1
            return summary

        if _is_probably_download(response.url, content_type):
            ext = detect_extension(response.url, content_type) or ".bin"
            file_name = safe_filename(f"{seed.source_id}_{safe_slug(seed.title)}{ext}")
            target_path = seed_dir / file_name
            size_bytes, file_hash = _save_stream_to_file(response, target_path, max_download_bytes)
            db.add_artifact(
                project=project,
                source_id=seed.source_id,
                run_id=run_id,
                kind="download",
                status="ok",
                source_url=response.url,
                local_path=str(target_path),
                mime_type=content_type,
                sha256=file_hash,
                size_bytes=size_bytes,
                http_status=response.status_code,
                title=seed.title,
                note=seed.notes,
            )
            summary["downloaded"] += 1
            time.sleep(float(settings.get("sleep_seconds_between_requests", 1.0)))
            return summary

        if _is_html(content_type):
            html = response.text
            page_title, candidates, body_length = _extract_candidates(html, response.url)
            is_direct_html_source = seed.access_mode == "direct" or seed.source_type == "direct_file"
            is_html_content = (
                body_length >= int(settings.get("html_content_threshold", 5000))
                or (is_direct_html_source and "html" in seed.expected_formats.lower())
            )
            snapshot_base_dir = seed_dir if is_html_content else landing_dir
            file_stem = "content" if is_html_content else "landing"
            snapshot_path = _save_html_snapshot(
                snapshot_base_dir,
                file_stem,
                html,
                {
                    "source_id": seed.source_id,
                    "seed_title": seed.title,
                    "requested_url": target_url,
                    "final_url": response.url,
                    "content_type": content_type,
                    "status_code": response.status_code,
                    "page_title": page_title,
                    "candidate_count": len(candidates),
                    "body_text_length": body_length,
                    "captured_at": response.headers.get("Date", ""),
                },
            )
            db.add_artifact(
                project=project,
                source_id=seed.source_id,
                run_id=run_id,
                kind="html_content" if is_html_content else "landing_page",
                status="ok",
                source_url=response.url,
                local_path=str(snapshot_path),
                mime_type=content_type,
                sha256=sha256_file(snapshot_path),
                size_bytes=snapshot_path.stat().st_size,
                http_status=response.status_code,
                title=page_title or seed.title,
                note=seed.notes,
            )
            if is_html_content:
                summary["html_content"] += 1
            else:
                summary["landing_only"] += 1

            if candidates:
                downloaded_from_candidates = _attempt_candidate_downloads(
                    db=db,
                    session=session,
                    settings=settings,
                    project=project,
                    seed=seed,
                    run_id=run_id,
                    seed_dir=seed_dir,
                    candidates=candidates,
                )
                summary["downloaded"] += downloaded_from_candidates
            time.sleep(float(settings.get("sleep_seconds_between_requests", 1.0)))
            return summary

        # Unknown content: preserve as a raw file if possible
        ext = detect_extension(response.url, content_type) or ".bin"
        file_name = safe_filename(f"{seed.source_id}_{safe_slug(seed.title)}{ext}")
        target_path = seed_dir / file_name
        size_bytes, file_hash = _save_stream_to_file(response, target_path, max_download_bytes)
        db.add_artifact(
            project=project,
            source_id=seed.source_id,
            run_id=run_id,
            kind="download",
            status="ok",
            source_url=response.url,
            local_path=str(target_path),
            mime_type=content_type,
            sha256=file_hash,
            size_bytes=size_bytes,
            http_status=response.status_code,
            title=seed.title,
            note="unknown-content-saved",
        )
        summary["downloaded"] += 1
        time.sleep(float(settings.get("sleep_seconds_between_requests", 1.0)))
        return summary

    except Exception as exc:
        db.add_lead(
            project=project,
            source_id=seed.source_id,
            run_id=run_id,
            url=target_url,
            relation="seed",
            status="request_failed",
            title=seed.title,
            note=str(exc),
        )
        db.add_error(
            project=project,
            source_id=seed.source_id,
            run_id=run_id,
            url=target_url,
            stage="exception",
            message=str(exc),
        )
        summary["errors"] += 1
        return summary


def run_collection(project_root: Path, force: bool = False, limit: int | None = None) -> dict[str, int]:
    repo_root = project_root.parents[1]
    manifest_path = project_root / "manifests" / "seeds_master.csv"
    settings = load_settings(repo_root)
    seeds = [seed for seed in load_manifest(manifest_path) if seed.enabled]
    if limit is not None:
        seeds = seeds[:limit]

    db = CatalogDB(project_root / "state" / "acquisition.db")
    run_id = db.begin_run(project=project_root.name, manifest_path=manifest_path)
    session = _make_session(settings)
    summary = {"downloaded": 0, "html_content": 0, "landing_only": 0, "errors": 0, "skipped": 0}
    try:
        for seed in seeds:
            result = _process_seed(
                project_root=project_root,
                db=db,
                session=session,
                settings=settings,
                run_id=run_id,
                seed=seed,
                force=force,
            )
            for key, value in result.items():
                summary[key] = summary.get(key, 0) + value
        db.finish_run(run_id, summary, status="finished")
    except Exception:
        db.finish_run(run_id, summary, status="failed")
        raise
    finally:
        db.close()
        session.close()
    return summary
