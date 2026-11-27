import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dsi_omega.memory import (
    IntegrityError, RecordNotFound, SQLiteMemoryStore, ValidationError,
)


class SQLiteMemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "memory.sqlite3"
        self.store = SQLiteMemoryStore(self.db)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def add_record(self, **overrides):
        values = {
            "project_id": "dsi-omega",
            "title": "CSC-LCH source integrity",
            "content": "Original source text with exact punctuation.\nSecond line.",
            "summary": "Preserve original source and verify SHA-256 integrity.",
            "tier": "T3",
            "evidence": "OBS",
            "tags": ["memory", "integrity"],
            "metadata": {"origin": "unit-test"},
        }
        values.update(overrides)
        return self.store.add(**values)

    def test_add_and_hydrate_round_trip_preserves_original_text(self):
        original = "café\r\nline with trailing spaces  \n"
        record = self.add_record(content=original, tier="T5")
        stub = self.store.get(record.memory_id, hydrate=False)
        self.assertIsNone(stub.content)
        hydrated = self.store.hydrate(record.memory_id)
        self.assertEqual(hydrated.content, original)
        self.assertEqual(
            hydrated.content_sha256,
            hashlib.sha256(original.encode("utf-8")).hexdigest(),
        )

    def test_search_returns_deferred_tier_as_stub(self):
        record = self.add_record(tier="T5")
        hits = self.store.search("source integrity", project_id="dsi-omega")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].record.memory_id, record.memory_id)
        self.assertFalse(hits[0].hydrated)
        self.assertIsNone(hits[0].record.content)
        self.assertEqual(self.store.hydrate(record.memory_id).content, record.content)

    def test_search_hydrates_active_tiers_by_default(self):
        record = self.add_record(tier="T2")
        hit = self.store.search("source integrity", project_id="dsi-omega")[0]
        self.assertTrue(hit.hydrated)
        self.assertEqual(hit.record.content, record.content)

    def test_project_isolation(self):
        self.add_record(project_id="project-a")
        self.add_record(project_id="project-b")
        hits = self.store.search("source integrity", project_id="project-a")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].record.project_id, "project-a")

    def test_invalid_tier_and_evidence_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.add_record(tier="T9")
        with self.assertRaises(ValidationError):
            self.add_record(evidence="MAYBE")

    def test_duplicate_id_is_rejected(self):
        self.add_record(memory_id="fixed-id")
        with self.assertRaises(ValidationError):
            self.add_record(memory_id="fixed-id")

    def test_tampered_database_content_fails_integrity_check(self):
        record = self.add_record()
        connection = sqlite3.connect(self.db)
        connection.execute(
            "UPDATE memory_records SET content = ? WHERE memory_id = ?",
            ("tampered", record.memory_id),
        )
        connection.commit()
        connection.close()
        with self.assertRaises(IntegrityError):
            self.store.hydrate(record.memory_id)

    def test_deactivate_preserves_record_but_hides_it(self):
        record = self.add_record()
        self.store.deactivate(record.memory_id)
        self.assertEqual(self.store.count(project_id="dsi-omega"), 0)
        with self.assertRaises(RecordNotFound):
            self.store.get(record.memory_id)

    def test_query_validation(self):
        with self.assertRaises(ValidationError):
            self.store.search("!!!", project_id="dsi-omega")
        with self.assertRaises(ValidationError):
            self.store.search("memory", project_id="dsi-omega", limit=0)


if __name__ == "__main__":
    unittest.main()
