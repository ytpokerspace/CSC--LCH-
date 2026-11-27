import json
import tempfile
import unittest
from pathlib import Path
from benchmarks.qbs_candidate_search import load_candidates, rank_and_propose

FIXTURE = Path(__file__).parent / "fixtures" / "qbs_candidates_sample.jsonl"

class QBSCandidateSearchTests(unittest.TestCase):
    def test_selects_best_feasible_candidate_and_proposes_neighbors(self):
        candidates = load_candidates(FIXTURE)
        result = rank_and_propose(candidates, step=0.1)
        self.assertEqual(result["winner"]["candidate_id"], "balanced")
        self.assertEqual(len(result["next_candidates"]), 12)
        self.assertTrue(all(x["status"] == "proposal_not_yet_evaluated" for x in result["next_candidates"]))

    def test_critical_fact_gate_overrides_high_utility(self):
        candidates = load_candidates(FIXTURE)
        result = rank_and_propose(candidates)
        rejected = {x["candidate_id"] for x in result["rejected_candidates"]}
        self.assertIn("unsafe_high_score", rejected)

    def test_accuracy_floor_can_reject_every_candidate(self):
        result = rank_and_propose(load_candidates(FIXTURE), min_accuracy=0.99)
        self.assertEqual(result["status"], "no_feasible_candidate")
        self.assertIsNone(result["winner"])

    def test_invalid_control_range_rejected(self):
        rows = [json.loads(x) for x in FIXTURE.read_text().splitlines()]
        rows[0]["controls"]["compression"] = 1.5
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in rows))
            with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                load_candidates(path)

if __name__ == "__main__":
    unittest.main()
