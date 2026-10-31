import unittest

from csc_lch_integrated import audit, compress, hydrate


class IntegratedCSCLCHTests(unittest.TestCase):
    def test_duplicate_sentence_is_deduplicated_but_source_is_preserved(self):
        source = "Mira approved version 2. Mira approved version 2. Mira rejected version 3."
        package = compress(source, query="approved version", budget=100)
        self.assertEqual(package["coverage"]["duplicate_sentences_removed"], 1)
        self.assertEqual(package["source_archive"]["source_text"], source)
        self.assertTrue(audit(package)["source_hash_matches"])

    def test_hydration_recovers_deferred_original_sentence(self):
        source = (
            "The system stores a source archive. "
            "The operator must never delete the original record. "
            "The report describes a blue bicycle."
        )
        package = compress(source, query="archive", budget=3)
        result = hydrate(package, "original record", limit=3)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(any("must never delete the original record" in item["text"] for item in result["results"]))

    def test_audit_accounts_for_every_unique_unit(self):
        package = compress("A fact is here. Another fact is there.", budget=2)
        result = audit(package)
        self.assertTrue(result["unit_ids_unique"])
        self.assertTrue(result["selected_deferred_disjoint"])
        self.assertTrue(result["all_units_accounted_for"])
        self.assertFalse(result["semantic_preservation_verified"])
        self.assertFalse(result["token_savings_verified"])

    def test_tampered_archive_is_rejected(self):
        package = compress("The source says 17 units.", budget=1)
        package["source_archive"]["source_text"] = "changed"
        result = hydrate(package, "units")
        self.assertEqual(result["status"], "source_unavailable_or_hash_mismatch")
        self.assertEqual(result["results"], [])

    def test_custom_counter_is_used(self):
        package = compress("one two three.", budget=10, token_counter=lambda text: len(text))
        self.assertEqual(package["token_count_mode"], "custom_exact")
        self.assertEqual(package["measured_payload_tokens"], len(package["prompt_payload"]))


if __name__ == "__main__":
    unittest.main()
