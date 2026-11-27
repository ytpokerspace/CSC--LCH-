import unittest

from benchmarks.longbench_v2.evaluate import (
    select_chunks,
    split_chunks,
    terms,
    validate_row,
)


class LongBenchAdapterTests(unittest.TestCase):
    def test_split_chunks_covers_start_and_end(self):
        source = ("alpha beta gamma\n" * 500)
        chunks = split_chunks(source, chunk_chars=120, overlap_chars=20)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0][:20], source[:20])
        self.assertEqual(chunks[-1][-20:], source[-20:])

    def test_rejects_invalid_overlap(self):
        with self.assertRaises(ValueError):
            split_chunks("abc", chunk_chars=10, overlap_chars=10)

    def test_select_chunks_prefers_matching_chunk(self):
        chunks = ["apples and oranges", "quantum mechanics field theory", "history of Rome"]
        self.assertEqual(select_chunks("quantum field", chunks, top_k=1), [1])

    def test_terms_removes_common_words(self):
        self.assertEqual(terms("What is the answer about cats?"), {"answer", "cats"})

    def test_validates_longbench_v2_record(self):
        validate_row({
            "_id": "sample-1", "question": "Which option?", "context": "Evidence.",
            "answer": "B",
        })
        with self.assertRaises(ValueError):
            validate_row({"_id": "bad", "question": "Q", "context": "C", "answer": "E"})


if __name__ == "__main__":
    unittest.main()
