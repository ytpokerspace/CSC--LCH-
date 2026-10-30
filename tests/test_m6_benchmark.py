import json
import tempfile
import unittest
from pathlib import Path

from scripts.m6_benchmark import load_rows, summarize


def observation(policy="T4", question_id="q1", **overrides):
    row = {
        "policy": policy,
        "question_id": question_id,
        "baseline_prompt_tokens": 100,
        "active_prompt_tokens": 70,
        "hydration_calls": 1,
        "hydration_prompt_tokens": 5,
        "retrieved_tokens": 10,
        "output_tokens": 8,
        "latency_ms": 25.0,
        "quality_score": 1.0,
        "material_facts_expected": 2,
        "material_facts_recovered": 2,
        "reconstruction_ok": True,
    }
    row.update(overrides)
    return row


class Milestone6BenchmarkTests(unittest.TestCase):
    def test_total_tokens_and_active_savings(self):
        result = summarize([observation()])["policies"]["T4"]
        self.assertEqual(result["active_tokens_saved"], 30)
        self.assertEqual(result["total_tokens_including_recorded_retrieval_and_output"], 93)
        self.assertNotIn("total_tokens_saved_vs_baseline_prompt_only", result)
        self.assertEqual(result["material_fact_recall"], 1.0)

    def test_groups_policies_after_validating_same_tasks(self):
        rows = [observation("T3", "q1"), observation("T4", "q1", active_prompt_tokens=80)]
        result = summarize(rows)["policies"]
        self.assertEqual(result["T3"]["active_prompt_tokens_total"], 70)
        self.assertEqual(result["T4"]["active_prompt_tokens_total"], 80)

    def test_rejects_mismatched_question_sets(self):
        with self.assertRaisesRegex(ValueError, "identical question_id sets"):
            summarize([observation("T3", "q1"), observation("T4", "q2")])

    def test_rejects_baseline_mismatch_for_same_question(self):
        with self.assertRaisesRegex(ValueError, "baseline prompt tokens"):
            summarize([observation("T3", "q1"), observation("T4", "q1", baseline_prompt_tokens=101)])

    def test_rejects_duplicate_policy_question_observation(self):
        with self.assertRaisesRegex(ValueError, "duplicate observation"):
            summarize([observation("T3", "q1"), observation("T3", "q1"), observation("T4", "q1")])

    def test_rejects_missing_field(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            row = observation()
            del row["quality_score"]
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing fields"):
                load_rows(path)

    def test_rejects_negative_token_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            path.write_text(json.dumps(observation(active_prompt_tokens=-1)) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-negative integer"):
                load_rows(path)

    def test_rejects_recovered_facts_above_expected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            path.write_text(json.dumps(observation(material_facts_expected=1, material_facts_recovered=2)) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot exceed"):
                load_rows(path)


if __name__ == "__main__":
    unittest.main()
