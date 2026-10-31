"""Tests for lossless dictionary encoding and hydration payloads."""
import json
import unittest

from csc_lch_codec import (
    build_lazy_payload, build_lazy_raw_payload, decode_documents, decode_lazy_payload, encode_documents,
    split_exact,
)
from csc_lch_compression_bench import SYNTHETIC_CORPUS, run_benchmark


class CodecTests(unittest.TestCase):
    def test_split_exact_unicode_and_whitespace(self):
        for value in ["", "  hello\tworld\n", "🧠 café 漢字", "a...b"]:
            self.assertEqual("".join(split_exact(value)), value)

    def test_dictionary_round_trip(self):
        docs = ["repeat repeat 🧠", "repeat, again!", ""]
        encoded = encode_documents(docs)
        self.assertEqual(decode_documents(encoded.serialized), docs)
        self.assertLessEqual(encoded.dictionary_entries, sum(len(split_exact(x)) for x in docs))

    def test_empty_corpus_round_trip(self):
        self.assertEqual(decode_documents(encode_documents([]).serialized), [])

    def test_invalid_symbol_id_rejected(self):
        with self.assertRaises(ValueError):
            decode_documents({"version": 1, "dictionary": ["x"], "streams": [[1]]})

    def test_unknown_version_rejected(self):
        with self.assertRaises(ValueError):
            decode_documents({"version": 999, "dictionary": [], "streams": []})

    def test_lazy_payload_round_trip(self):
        docs = ["alpha alpha", "beta beta", "gamma"]
        payload = build_lazy_payload(docs, [2, 0, 2])
        index, ids, hydrated = decode_lazy_payload(payload)
        self.assertEqual(len(index), 3)
        self.assertEqual(ids, [0, 2])
        self.assertEqual(hydrated, ["alpha alpha", "gamma"])

    def test_raw_lazy_payload_keeps_selected_text_exact(self):
        docs = ["first", "second 🧠", "third"]
        payload = json.loads(build_lazy_raw_payload(docs, [1]))
        self.assertEqual(payload["selected_documents"], ["second 🧠"])
        self.assertEqual(payload["selected_document_ids"], [1])

    def test_lazy_payload_rejects_invalid_selection(self):
        with self.assertRaises(ValueError):
            build_lazy_payload(["one"], [1])

    def test_benchmark_reports_integrity_and_tokenizer_scope(self):
        report = run_benchmark(SYNTHETIC_CORPUS, [0, 2])
        self.assertTrue(report["integrity"]["full_corpus_exact"])
        self.assertTrue(report["integrity"]["lazy_selected_exact"])
        self.assertIn("tokenizer", report)
        self.assertIn("limitations", report)


if __name__ == "__main__":
    unittest.main()
