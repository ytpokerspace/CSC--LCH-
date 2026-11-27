import json
import tempfile
import unittest
from pathlib import Path
from benchmarks.answer_accuracy import load_and_score, normalize, score_one, token_f1

FIXTURE = Path(__file__).parent / "fixtures" / "answer_accuracy_sample.jsonl"

class AnswerAccuracyTests(unittest.TestCase):
    def test_normalization_and_aliases(self):
        self.assertEqual(normalize("The QUICK, brown fox!"), "quick brown fox")
        self.assertEqual(score_one("NYC", ["New York", "NYC"])[0], 1.0)

    def test_token_f1_partial_overlap(self):
        self.assertAlmostEqual(token_f1("the red car", "red car"), 1.0)
        self.assertEqual(token_f1("blue", "red"), 0.0)

    def test_paired_metrics(self):
        result = load_and_score(FIXTURE)
        self.assertEqual(result["policies"]["full"]["exact_match_accuracy"], 1.0)
        self.assertAlmostEqual(result["policies"]["compressed"]["exact_match_accuracy"], 1 / 3, places=6)
        self.assertGreater(result["policies"]["compressed"]["mean_token_f1"], 0.5)

    def test_mismatched_question_sets_rejected(self):
        rows = [json.loads(x) for x in FIXTURE.read_text().splitlines()]
        rows.pop()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in rows))
            with self.assertRaisesRegex(ValueError, "identical question_id sets"):
                load_and_score(path)

    def test_duplicate_pair_rejected(self):
        row = json.loads(FIXTURE.read_text().splitlines()[0])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "duplicate.jsonl"
            path.write_text(json.dumps(row) + "\n" + json.dumps(row))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_and_score(path)

    def test_missing_gold_rejected(self):
        with self.assertRaisesRegex(ValueError, "gold_answers"):
            score_one("answer", [])

if __name__ == "__main__":
    unittest.main()
