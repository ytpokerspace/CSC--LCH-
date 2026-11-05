import unittest

from araf.core import validate_payload


VALID_PLAN = {
    "title": "Context compression pilot",
    "domain": "LLM efficiency",
    "problem_statement": "Determine whether compression reduces input tokens without unacceptable accuracy loss.",
    "objective": "Compare compressed and uncompressed contexts on a fixed task set.",
    "success_criteria": ["Lower median input-token count with accuracy within a predeclared tolerance."],
    "hypotheses": [{
        "statement": "Compression reduces input-token count.",
        "prediction": "The compressed condition uses fewer input tokens on the fixed task set.",
        "independent_variables": ["compression condition"],
        "dependent_variables": ["input token count", "task accuracy"],
        "rejection_criterion": "Reject if median input tokens do not decrease.",
    }],
    "experiment": {
        "baseline": "Original uncompressed context",
        "controls": ["Same tasks", "Same model/version", "Same generation settings"],
        "dataset": "A documented fixed synthetic task set",
        "method": "Run both conditions and record token counts and task outcomes.",
        "metrics": ["input tokens", "task accuracy", "latency"],
        "reproducibility_notes": ["Record seed, task set version, model identifier, and settings."],
    },
    "risks": ["Compression may remove information required to solve a task."],
    "claims": [
        {"claim": "The method may reduce token usage.", "status": "hypothesized"}
    ],
    "scores": {"feasibility": 7},
}


class ValidatePayloadTests(unittest.TestCase):
    def test_valid_plan_passes_structural_checks(self):
        result = validate_payload(VALID_PLAN)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["errors"], [])

    def test_missing_baseline_is_rejected(self):
        data = {**VALID_PLAN, "experiment": {**VALID_PLAN["experiment"], "baseline": ""}}
        result = validate_payload(data)
        self.assertFalse(result["valid"])
        self.assertTrue(any("experiment.baseline" in error for error in result["errors"]))

    def test_literature_claim_requires_source(self):
        data = {
            **VALID_PLAN,
            "claims": [{"claim": "A prior paper shows this.", "status": "literature_supported"}],
        }
        result = validate_payload(data)
        self.assertFalse(result["valid"])
        self.assertTrue(any("must include a source" in error for error in result["errors"]))

    def test_score_range_is_checked(self):
        data = {**VALID_PLAN, "scores": {"novelty": 11}}
        result = validate_payload(data)
        self.assertFalse(result["valid"])
        self.assertTrue(any("scores.novelty" in error for error in result["errors"]))

    def test_invalid_top_level_fields_return_error(self):
        result = validate_payload({"experiment": {}})
        self.assertFalse(result["valid"])
        self.assertIsInstance(result["errors"], list)

    def test_unknown_evidence_status_is_rejected(self):
        data = {**VALID_PLAN, "claims": [{"claim": "Unsupported claim", "status": "probably_true"}]}
        result = validate_payload(data)
        self.assertFalse(result["valid"])
        self.assertTrue(any("claims[1].status" in error for error in result["errors"]))

    def test_hypothesis_without_dependent_variable_is_rejected(self):
        hypothesis = {**VALID_PLAN["hypotheses"][0], "dependent_variables": []}
        data = {**VALID_PLAN, "hypotheses": [hypothesis]}
        result = validate_payload(data)
        self.assertFalse(result["valid"])
        self.assertTrue(any("dependent_variables must not be empty" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
