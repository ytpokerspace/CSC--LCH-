"""CSC-LCH memory interface for DSI-Ω.

Copyright (C) 2026 William Gunnell Cox.
Dependency-free SQLite backend with retained originals and SHA-256 hydration checks.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence

TIERS = ("T0", "T1", "T2", "T3", "T4", "T5")
EVIDENCE = ("OBS", "INF", "SPEC")
_WORDS = re.compile(r"[\w'-]+", re.UNICODE)


class MemoryErrorBase(Exception):
    """Base class for memory interface errors."""


class RecordNotFound(MemoryErrorBase):
    """Requested record is missing or inactive."""


class IntegrityError(MemoryErrorBase):
    """Archived content does not match its SHA-256 digest."""


class ValidationError(MemoryErrorBase, ValueError):
    """Input violates the memory contract."""


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    project_id: str
    title: str
    summary: str
    tier: str
    evidence: str
    source_ref: Optional[str]
    content_sha256: str
    tags: tuple[str, ...]
    metadata: Mapping[str, Any]
    created_at: str
    updated_at: str
    content: Optional[str] = None


@dataclass(frozen=True)
class MemoryHit:
    record: MemoryRecord
    score: float
    hydrated: bool


class MemoryBackend(Protocol):
    """Replaceable contract for local or future distributed memory backends."""
    def add(self, *, project_id: str, title: str, content: str, summary: str,
            tier: str = "T3", evidence: str = "OBS",
            source_ref: Optional[str] = None, tags: Sequence[str] = (),
            metadata: Optional[Mapping[str, Any]] = None,
            memory_id: Optional[str] = None) -> MemoryRecord: ...
    def get(self, memory_id: str, *, hydrate: bool = True) -> MemoryRecord: ...
    def search(self, query: str, *, project_id: str,
               tiers: Optional[Sequence[str]] = None, hydrate: bool = False,
               limit: int = 10) -> list[MemoryHit]: ...
    def close(self) -> None: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _terms(value: str) -> set[str]:
    return {word.casefold() for word in _WORDS.findall(value) if len(word) > 1}


class SQLiteMemoryStore:
    """Local CSC-LCH store. T4/T5 results remain summary-only until hydrated."""

    def __init__(self, database: str | Path = "dsi_omega_memory.sqlite3") -> None:
        self.database = str(database)
        if self.database != ":memory:":
            Path(self.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.database)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA busy_timeout = 5000")
        if self.database != ":memory:":
            self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS memory_records (
                memory_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT NOT NULL,
                tier TEXT NOT NULL CHECK(tier IN ('T0','T1','T2','T3','T4','T5')),
                evidence TEXT NOT NULL CHECK(evidence IN ('OBS','INF','SPEC')),
                source_ref TEXT,
                content_sha256 TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
            );
            CREATE INDEX IF NOT EXISTS idx_memory_project_active
                ON memory_records(project_id, active);
            CREATE INDEX IF NOT EXISTS idx_memory_project_tier
                ON memory_records(project_id, tier, active);
            PRAGMA user_version = 1;
        """)
        self._db.commit()

    def add(self, *, project_id: str, title: str, content: str, summary: str,
            tier: str = "T3", evidence: str = "OBS",
            source_ref: Optional[str] = None, tags: Sequence[str] = (),
            metadata: Optional[Mapping[str, Any]] = None,
            memory_id: Optional[str] = None) -> MemoryRecord:
        for name, value in (("project_id", project_id), ("title", title),
                            ("content", content), ("summary", summary)):
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{name} must be a non-empty string")
        if tier not in TIERS:
            raise ValidationError(f"tier must be one of {', '.join(TIERS)}")
        if evidence not in EVIDENCE:
            raise ValidationError(f"evidence must be one of {', '.join(EVIDENCE)}")
        if source_ref is not None and not isinstance(source_ref, str):
            raise ValidationError("source_ref must be a string or None")
        if isinstance(tags, (str, bytes)) or not isinstance(tags, Sequence):
            raise ValidationError("tags must be a sequence of strings")
        clean_tags = []
        for tag in tags:
            if not isinstance(tag, str) or not tag.strip():
                raise ValidationError("each tag must be a non-empty string")
            clean_tags.append(tag.strip())
        try:
            metadata_json = json.dumps(dict(metadata or {}), ensure_ascii=False,
                                       sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("metadata must be JSON serializable") from exc
        tags_json = json.dumps(clean_tags, ensure_ascii=False, separators=(",", ":"))
        record_id = memory_id or str(uuid.uuid4())
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValidationError("memory_id must be a non-empty string")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        now = _now()
        try:
            self._db.execute("""
                INSERT INTO memory_records
                (memory_id, project_id, title, content, summary, tier, evidence,
                 source_ref, content_sha256, tags_json, metadata_json,
                 created_at, updated_at, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (record_id, project_id, title, content, summary, tier, evidence,
                  source_ref, digest, tags_json, metadata_json, now, now))
            self._db.commit()
        except sqlite3.IntegrityError as exc:
            self._db.rollback()
            raise ValidationError(f"memory_id already exists or record is invalid: {record_id}") from exc
        return self.get(record_id)

    def get(self, memory_id: str, *, hydrate: bool = True) -> MemoryRecord:
        row = self._db.execute(
            "SELECT * FROM memory_records WHERE memory_id = ? AND active = 1",
            (memory_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFound(memory_id)
        content = row["content"] if hydrate else None
        if hydrate:
            self._verify(row, content)
        return self._record(row, content)

    def hydrate(self, memory_id: str) -> MemoryRecord:
        """Return original archived text only after verifying its digest."""
        return self.get(memory_id, hydrate=True)

    def search(self, query: str, *, project_id: str,
               tiers: Optional[Sequence[str]] = None, hydrate: bool = False,
               limit: int = 10) -> list[MemoryHit]:
        if not isinstance(query, str) or not query.strip():
            raise ValidationError("query must be a non-empty string")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValidationError("project_id must be a non-empty string")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValidationError("limit must be an integer between 1 and 100")
        if tiers is not None:
            if isinstance(tiers, (str, bytes)) or not isinstance(tiers, Sequence):
                raise ValidationError("tiers must be a sequence")
            invalid = set(tiers) - set(TIERS)
            if invalid:
                raise ValidationError("invalid tier filter: " + ", ".join(sorted(invalid)))
            if not tiers:
                return []
        query_terms = _terms(query)
        if not query_terms:
            raise ValidationError("query must contain searchable words")
        sql = "SELECT * FROM memory_records WHERE project_id = ? AND active = 1"
        params: list[Any] = [project_id]
        if tiers is not None:
            sql += " AND tier IN (" + ",".join("?" for _ in tiers) + ")"
            params.extend(tiers)
        rows = self._db.execute(sql, params).fetchall()
        hits = []
        for row in rows:
            title_terms = _terms(row["title"])
            summary_terms = _terms(row["summary"])
            tag_terms = _terms(" ".join(json.loads(row["tags_json"])))
            content_terms = _terms(row["content"])
            score = (3.0 * len(query_terms & title_terms)
                     + 2.0 * len(query_terms & summary_terms)
                     + 2.0 * len(query_terms & tag_terms)
                     + 1.0 * len(query_terms & content_terms))
            if query.casefold() in row["title"].casefold():
                score += 2.0
            if score <= 0:
                continue
            is_hydrated = hydrate or row["tier"] not in ("T4", "T5")
            content = row["content"] if is_hydrated else None
            if is_hydrated:
                self._verify(row, content)
            hits.append(MemoryHit(self._record(row, content), score, is_hydrated))
        hits.sort(key=lambda hit: (-hit.score, hit.record.created_at, hit.record.memory_id))
        return hits[:limit]

    def deactivate(self, memory_id: str) -> None:
        cursor = self._db.execute(
            "UPDATE memory_records SET active = 0, updated_at = ? "
            "WHERE memory_id = ? AND active = 1",
            (_now(), memory_id),
        )
        self._db.commit()
        if cursor.rowcount == 0:
            raise RecordNotFound(memory_id)

    def count(self, *, project_id: Optional[str] = None) -> int:
        if project_id is None:
            row = self._db.execute(
                "SELECT COUNT(*) AS n FROM memory_records WHERE active = 1"
            ).fetchone()
        else:
            row = self._db.execute(
                "SELECT COUNT(*) AS n FROM memory_records WHERE active = 1 AND project_id = ?",
                (project_id,),
            ).fetchone()
        return int(row["n"])

    @staticmethod
    def _verify(row: sqlite3.Row, content: str) -> None:
        actual = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if actual != row["content_sha256"]:
            raise IntegrityError(f"SHA-256 mismatch for memory record {row['memory_id']}")

    @staticmethod
    def _record(row: sqlite3.Row, content: Optional[str]) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"], project_id=row["project_id"],
            title=row["title"], summary=row["summary"], tier=row["tier"],
            evidence=row["evidence"], source_ref=row["source_ref"],
            content_sha256=row["content_sha256"],
            tags=tuple(json.loads(row["tags_json"])),
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
            content=content,
        )

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "SQLiteMemoryStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
