"""Offline regression tests for the CSC-LCH benchmark harness.

These tests intentionally do not call provider APIs or generate model answers.
"""
import unittest

import csc_lch_bench as csc


class SyntheticHarnessTests(unittest.TestCase):
    def test_synthetic_corpus_is_nonempty_and_reproducible(self):
        segs_a, qa_a = csc.build_synthetic(scale=1, seed=7)
        segs_b, qa_b = csc.build_synthetic(scale=1, seed=7)
        self.assertGreater(len(segs_a), 0)
        self.assertGreater(len(qa_a), 0)
        self.assertEqual([s.text for s in segs_a], [s.text for s in segs_b])
        self.assertEqual(qa_a, qa_b)

    def test_variants_include_no_glyph_baseline_and_store(self):
        segs, _ = csc.build_synthetic(scale=1, seed=7)
        pairs = csc.usable_pairs(csc.load_lexicon(None))
        result = csc.build_variants(segs, pairs, {}, 4)
        self.assertIn("variants", result)
        self.assertIn("noglyph", result["variants"])
        baseline = result["variants"]["noglyph"]
        self.assertIn("text", baseline)
        self.assertIsInstance(baseline["text"], str)
        self.assertIsInstance(baseline["store"], dict)

    def test_offline_token_estimator_returns_nonnegative_integer(self):
        estimate = csc.estimate_tokens({
            "system": csc.BASE_SYSTEM,
            "messages": [{"role": "user", "content": "A short offline smoke test."}],
        })
        self.assertIsInstance(estimate, int)
        self.assertGreaterEqual(estimate, 0)

    def test_lexicon_validation_is_callable(self):
        issues = csc.validate_lexicon(csc.load_lexicon(None))
        self.assertIsInstance(issues, list)


if __name__ == "__main__":
    unittest.main()
