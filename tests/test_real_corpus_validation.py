"""Regression tests for the offline CSC-LCH real-document validation."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import real_corpus_validation as validation  # noqa: E402


class IntegrityTests(unittest.TestCase):
    def test_source_archive_reconstructs_exact_bytes(self):
        original = b"# Heading\\r\\n\\r\\nUnicode: caf\\xc3\\xa9\\nLast line"
        chunks = validation.archive_source(original)
        self.assertEqual(validation.reconstruct_source(chunks, validation.sha256(original)), original)

    def test_source_archive_rejects_corrupted_chunk(self):
        original = b"first\\n\\nsecond\\n"
        chunks = validation.archive_source(original)
        chunks[0]["data"] += b"corruption"
        with self.assertRaisesRegex(ValueError, "chunk SHA-256 mismatch"):
            validation.reconstruct_source(chunks, validation.sha256(original))

    def test_source_archive_rejects_missing_chunk(self):
        original = b"first\\n\\nsecond"
        chunks = validation.archive_source(original)
        chunks.pop(1)
        with self.assertRaisesRegex(ValueError, "incomplete or duplicated"):
            validation.reconstruct_source(chunks, validation.sha256(original))

    def test_hydration_accepts_original_content(self):
        text = "Archived evidence: 1.40×"
        hashes = {"doc001": validation.sha256(text.encode("utf-8"))}
        self.assertEqual(
            validation.hydrate_verified("doc001", {"doc001": text}, hashes),
            text,
        )

    def test_hydration_rejects_corrupted_content(self):
        original = "Archived evidence: 1.40×"
        hashes = {"doc001": validation.sha256(original.encode("utf-8"))}
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validation.hydrate_verified(
                "doc001", {"doc001": "Archived evidence: 9.99×"}, hashes
            )

    def test_hydration_rejects_missing_hash(self):
        with self.assertRaisesRegex(KeyError, "No source integrity hash"):
            validation.hydrate_verified("doc001", {"doc001": "text"}, {})


class BenchmarkAccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.segments, cls.source_hashes, cls.source_archives,
         cls.evidence_text, cls.segment_hashes) = validation.load_real_documents()
        for _qid, _label, _query, fact, source in validation.QUESTIONS:
            if fact.casefold() not in cls.evidence_text[source].casefold():
                raise AssertionError(f"Fixture evidence missing from {source}: {fact!r}")
        cls.baseline = validation.join(cls.segments)

    def test_all_repository_sources_reconstruct_byte_exactly(self):
        for source, chunks in self.source_archives.items():
            with self.subTest(source=source):
                rebuilt = validation.reconstruct_source(chunks, self.source_hashes[source])
                self.assertEqual(validation.sha256(rebuilt), self.source_hashes[source])

    def test_queries_do_not_contain_expected_evidence(self):
        for _qid, _label, query, fact, _source in validation.QUESTIONS:
            with self.subTest(query=query):
                self.assertIsNone(re.search(r"\\b" + re.escape(fact) + r"\\b", query, re.IGNORECASE))

    def test_bm25_retriever_uses_query_and_returns_ranked_candidates(self):
        store = {
            "doc001": "The project license is GPL-3.0-or-later.",
            "doc002": "The project records its author and contributors.",
            "doc003": "Historical ablation results reported a T3 ratio of 1.40x.",
        }
        ranked = validation.retrieve_bm25("What license governs this project?", store, top_k=2)
        self.assertEqual(ranked[0][0], "doc001")
        self.assertLessEqual(len(ranked), 2)
        self.assertGreater(ranked[0][1], 0)

    def test_bm25_retriever_rejects_invalid_top_k(self):
        with self.assertRaisesRegex(ValueError, "top_k"):
            validation.retrieve_bm25("license", {"doc001": "license"}, top_k=0)

    def test_historical_ablation_table_is_t5_archive(self):
        self.assertEqual(validation.tier_for("Reported ablation results", "milestone6_report.md"), 5)

    def test_registry_and_all_cost_components_are_counted(self):
        for name, threshold in (("T3", 3), ("T4", 4), ("T5", 5)):
            with self.subTest(policy=name):
                result = validation.evaluate_policy(
                    name, self.segments, threshold, self.baseline,
                    validation.QUESTIONS, self.segment_hashes,
                )
                self.assertGreater(result["registry_lexical_units"], 0)
                expected_total = (
                    result["policy_active_lexical_units"]
                    + result["registry_lexical_units"]
                    + result["hydration_prompt_lexical_units"]
                    + result["retrieved_lexical_units"]
                    + result["output_lexical_units"]
                )
                self.assertEqual(result["policy_total_lexical_units"], expected_total)
                self.assertEqual(result["reconstruction_failures"], 0)

    def test_t5_creates_stubs_and_hydrates_archived_evidence(self):
        result = validation.evaluate_policy(
            "T5", self.segments, 5, self.baseline,
            validation.QUESTIONS, self.segment_hashes,
        )
        self.assertGreater(result["stubs_created"], 0)
        self.assertGreater(result["hydration_calls"], 0)
        self.assertEqual(result["evidence_recovered"], result["evidence_expected"])
        self.assertEqual(result["reconstruction_failures"], 0)
        archived_trace = next(
            row for row in result["per_question"]
            if row["question_id"] == "Q15"
        )
        self.assertTrue(archived_trace["hydrated_entry_ids"])
        self.assertTrue(archived_trace["hydrated_sha256_verified"])


if __name__ == "__main__":
    unittest.main()
