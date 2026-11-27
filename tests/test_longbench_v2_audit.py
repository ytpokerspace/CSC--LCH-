import unittest

from benchmarks.longbench_v2_audit import audit_rows, lexical_retrieve, make_chunks, run_baseline


class FakeTokenizer:
    def encode(self, text, disallowed_special=()):
        return text.split()


def sample_row(rid, question, context, answer="A"):
    return {
        "_id": rid,
        "domain": "Single-Document QA",
        "sub_domain": "Academic",
        "difficulty": "easy",
        "length": "short",
        "question": question,
        "choice_A": "first",
        "choice_B": "second",
        "choice_C": "third",
        "choice_D": "fourth",
        "answer": answer,
        "context": context,
    }


class LongBenchAuditTests(unittest.TestCase):
    def test_valid_schema_and_answer_distribution(self):
        rows = [
            sample_row("q1", "Where is the observatory?", "The observatory is in Chile.", "A"),
            sample_row("q2", "Who wrote the report?", "Ada wrote the report.", "B"),
        ]
        result = audit_rows(rows)
        self.assertTrue(result["schema_valid"])
        self.assertEqual(result["rows"], 2)
        self.assertEqual(result["unique_ids"], 2)
        self.assertEqual(result["answer_label_counts"], {"A": 1, "B": 1})

    def test_duplicate_ids_and_invalid_labels_fail_audit(self):
        row = sample_row("q1", "What is recorded?", "The record is complete.", "Z")
        result = audit_rows([row, row])
        self.assertFalse(result["schema_valid"])
        self.assertEqual(result["duplicate_ids"], ["q1"])
        self.assertEqual(len(result["invalid_answer_labels"]), 2)

    def test_chunk_overlap_and_validation(self):
        self.assertEqual(make_chunks("abcdefghij", 6, 2), ["abcdef", "efghij"])
        with self.assertRaises(ValueError):
            make_chunks("abc", 4, 4)

    def test_lexical_retrieval_prefers_matching_chunk(self):
        context = "apples grow on trees. " + ("unrelated filler. " * 4) + "oranges contain vitamin c."
        retrieved, coverage, count = lexical_retrieve(
            context, "What contains vitamin c?", top_k=1, chunk_chars=35, overlap_chars=5
        )
        self.assertIn("vitamin c", retrieved)
        self.assertGreater(coverage, 0)
        self.assertGreater(count, 1)

    def test_baseline_uses_seeded_sample_and_reports_no_accuracy(self):
        rows = [
            sample_row("q1", "Where is the observatory?", "The observatory is in Chile."),
            sample_row("q2", "Who wrote the report?", "Ada wrote the report.", "B"),
            sample_row("q3", "What is the result?", "The result is stable.", "C"),
        ]
        result = run_baseline(rows, FakeTokenizer(), sample_size=2, seed=2026,
                              top_k=1, chunk_chars=20, overlap_chars=2)
        self.assertEqual(result["dataset_examples"], 3)
        self.assertEqual(result["sample_size"], 2)
        self.assertIsNone(result["answer_accuracy"])\n        self.assertIn("context_token_reduction_fraction", result["sampled_rows"])
        self.assertEqual(len(result["sampled_rows"]["examples"]), 2)


if __name__ == "__main__":
    unittest.main()
