"""Regression tests for the offline CSC-LCH real-document validation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import real_corpus_validation as validation  # noqa: E402


class IntegrityTests(unittest.TestCase):
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
        (cls.segments, cls.source_hashes, cls.evidence_text,
         cls.segment_hashes) = validation.load_real_documents()
        for _qid, _label, fact, source in validation.QUESTIONS:
            if fact.casefold() not in cls.evidence_text[source].casefold():
                raise AssertionError(f"Fixture evidence missing from {source}: {fact!r}")
        cls.baseline = validation.join(cls.segments)

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
