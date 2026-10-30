import json, tempfile, unittest
from pathlib import Path
from scripts.paired_benchmark import load_rows, summarize

FIXTURE = Path(__file__).parent / "fixtures" / "paired_sample.jsonl"

class PairedBenchmarkTests(unittest.TestCase):
    def test_five_paired_tasks_per_policy(self):
        summary = summarize(load_rows(FIXTURE))
        self.assertEqual(summary["data_status"], "synthetic_fixture")
        self.assertEqual(summary["policies"]["T3"]["observations"], 5)
        self.assertEqual(summary["policies"]["T3"]["baseline_fact_recall"], 1.0)
        self.assertEqual(summary["policies"]["T5"]["policy_reconstruction_failures"], 5)

    def test_both_totals_count_four_categories(self):
        r = load_rows(FIXTURE)[0]
        self.assertEqual(r["baseline_total_tokens"], sum(r[k] for k in (
            "baseline_prompt_tokens", "baseline_hydration_prompt_tokens",
            "baseline_retrieved_tokens", "baseline_output_tokens")))
        self.assertEqual(r["policy_total_tokens"], sum(r[k] for k in (
            "active_prompt_tokens", "hydration_prompt_tokens", "retrieved_tokens", "output_tokens")))

    def test_mismatched_policy_question_sets_rejected(self):
        rows = load_rows(FIXTURE)
        policy = rows[-1]["policy"]
        question_id = rows[-1]["question_id"]
        rows = [r for r in rows if not (r["policy"] == policy and r["question_id"] == question_id)]
        with self.assertRaisesRegex(ValueError, "identical question_id sets"):
            summarize(rows)

    def test_duplicate_pair_rejected(self):
        row = load_rows(FIXTURE)[0]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "duplicate.jsonl"
            p.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate observation"):
                load_rows(p)

if __name__ == "__main__":
    unittest.main()
