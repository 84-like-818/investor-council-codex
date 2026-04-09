from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .utils import ensure_dir, utc_now_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    manifest_path TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT,
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    source_id TEXT NOT NULL,
    run_id INTEGER,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    source_url TEXT,
    local_path TEXT,
    mime_type TEXT,
    sha256 TEXT,
    size_bytes INTEGER,
    http_status INTEGER,
    title TEXT,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    source_id TEXT NOT NULL,
    run_id INTEGER,
    url TEXT NOT NULL,
    relation TEXT,
    status TEXT,
    title TEXT,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    source_id TEXT NOT NULL,
    run_id INTEGER,
    url TEXT,
    stage TEXT,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS local_items (
    local_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER,
    matched_source_id TEXT,
    match_score REAL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_project_source ON artifacts(project, source_id);
CREATE INDEX IF NOT EXISTS idx_leads_project_source ON leads(project, source_id);
CREATE INDEX IF NOT EXISTS idx_errors_project_source ON errors(project, source_id);
CREATE INDEX IF NOT EXISTS idx_local_project_match ON local_items(project, matched_source_id);
"""


class CatalogDB:
    def __init__(self, db_path: Path):
        ensure_dir(db_path.parent)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def begin_run(self, project: str, manifest_path: Path) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs(project, manifest_path, started_at, status) VALUES (?, ?, ?, ?)",
            (project, str(manifest_path), utc_now_iso(), "running"),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, summary: dict[str, Any], status: str = "finished") -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at = ?, status = ?, summary_json = ? WHERE run_id = ?",
            (utc_now_iso(), status, json.dumps(summary, ensure_ascii=False), run_id),
        )
        self.conn.commit()

    def add_artifact(self, **kwargs: Any) -> None:
        payload = {
            "project": kwargs.get("project"),
            "source_id": kwargs.get("source_id"),
            "run_id": kwargs.get("run_id"),
            "kind": kwargs.get("kind"),
            "status": kwargs.get("status"),
            "source_url": kwargs.get("source_url"),
            "local_path": kwargs.get("local_path"),
            "mime_type": kwargs.get("mime_type"),
            "sha256": kwargs.get("sha256"),
            "size_bytes": kwargs.get("size_bytes"),
            "http_status": kwargs.get("http_status"),
            "title": kwargs.get("title"),
            "note": kwargs.get("note"),
            "created_at": utc_now_iso(),
        }
        self.conn.execute(
            """
            INSERT INTO artifacts(
                project, source_id, run_id, kind, status, source_url, local_path,
                mime_type, sha256, size_bytes, http_status, title, note, created_at
            ) VALUES (
                :project, :source_id, :run_id, :kind, :status, :source_url, :local_path,
                :mime_type, :sha256, :size_bytes, :http_status, :title, :note, :created_at
            )
            """,
            payload,
        )
        self.conn.commit()

    def add_lead(self, **kwargs: Any) -> None:
        payload = {
            "project": kwargs.get("project"),
            "source_id": kwargs.get("source_id"),
            "run_id": kwargs.get("run_id"),
            "url": kwargs.get("url"),
            "relation": kwargs.get("relation"),
            "status": kwargs.get("status"),
            "title": kwargs.get("title"),
            "note": kwargs.get("note"),
            "created_at": utc_now_iso(),
        }
        self.conn.execute(
            """
            INSERT INTO leads(project, source_id, run_id, url, relation, status, title, note, created_at)
            VALUES (:project, :source_id, :run_id, :url, :relation, :status, :title, :note, :created_at)
            """,
            payload,
        )
        self.conn.commit()

    def add_error(self, **kwargs: Any) -> None:
        payload = {
            "project": kwargs.get("project"),
            "source_id": kwargs.get("source_id"),
            "run_id": kwargs.get("run_id"),
            "url": kwargs.get("url"),
            "stage": kwargs.get("stage"),
            "message": kwargs.get("message"),
            "created_at": utc_now_iso(),
        }
        self.conn.execute(
            "INSERT INTO errors(project, source_id, run_id, url, stage, message, created_at) VALUES (:project, :source_id, :run_id, :url, :stage, :message, :created_at)",
            payload,
        )
        self.conn.commit()

    def replace_local_items(self, project: str, rows: list[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM local_items WHERE project = ?", (project,))
        self.conn.executemany(
            """
            INSERT INTO local_items(project, relative_path, file_name, sha256, size_bytes, matched_source_id, match_score, note, created_at)
            VALUES (:project, :relative_path, :file_name, :sha256, :size_bytes, :matched_source_id, :match_score, :note, :created_at)
            """,
            rows,
        )
        self.conn.commit()

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, params).fetchall())
