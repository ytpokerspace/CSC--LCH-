import unittest

from benchmarks.hybrid_retrieval import RetrievalConfig, retrieve, sentence_chunks
from benchmarks.qbs_hybrid_retrieval_tuner import split_rows, tune


class HybridRetrievalTests(unittest.TestCase):
    def test_sentence_chunks_preserve_exact_source_slices(self):
        source = "First fact.  Second fact!\nThird fact?"
        chunks = sentence_chunks(source)
        self.assertEqual([source[c.start:c.end] for c in chunks], [c.text for c in chunks])
        self.assertEqual(len(chunks), 3)

    def test_identifier_and_exact_phrase_signals_rank_relevant_chunk(self):
        context = (
            "The project has several unrelated milestones. "
            "The CSC-LCH release tag is v2.4.1 and its checksum is abc-123. "
            "A separate note discusses gardening."
        )
        result = retrieve(context, "What is the CSC-LCH release tag v2.4.1?",
                          RetrievalConfig(top_k=1, max_chars=500))
        self.assertIn("v2.4.1", result.retrieved_text)
        self.assertTrue(result.hits[0].identifier_matches)
        self.assertGreater(result.hits[0].score, 0)

    def test_budget_is_respected_and_offsets_are_valid(self):
        source = "Alpha has a unique marker 111. Beta has marker 222. Gamma has marker 333."
        result = retrieve(source, "marker 222", RetrievalConfig(top_k=3, max_chars=35))
        self.assertLessEqual(result.retrieved_characters, 36)
        for hit in result.hits:
            self.assertEqual(source[hit.start:hit.end], hit.text)

    def test_invalid_config_is_rejected(self):
        with self.assertRaises(ValueError):
            retrieve("Some text.", "text", RetrievalConfig(top_k=0))

    def test_tuner_keeps_dev_and_heldout_disjoint_and_reports_no_accuracy(self):
        rows = [
            {"id": "a", "question": "What is code 111?", "context": "Code 111 is alpha. Other material.",
             "gold_evidence": ["Code 111 is alpha."]},
            {"id": "b", "question": "What is code 222?", "context": "Code 222 is beta. Other material.",
             "gold_evidence": ["Code 222 is beta."]},
            {"id": "c", "question": "What is code 333?", "context": "Code 333 is gamma. Other material.",
             "gold_evidence": ["Code 333 is gamma."]},
            {"id": "d", "question": "What is code 444?", "context": "Code 444 is delta. Other material.",
             "gold_evidence": ["Code 444 is delta."]},
        ]
        dev, heldout = split_rows(rows, 2026)
        self.assertFalse({r["id"] for r in dev} & {r["id"] for r in heldout})
        result = tune(rows, seed=2026, min_recall=0.0)
        self.assertEqual(result["candidate_count"], 81)
        self.assertIsNone(result["answer_accuracy"])
        self.assertIn("evidence_recall", result["heldout_metrics"])


if __name__ == "__main__":
    unittest.main()
