"""Offline tests for the CSC-LCH semantic graph engine."""
import json
import tempfile
import unittest
from pathlib import Path

from csc_lch_graph import (
    DynamicSemanticGraph, Edge, LazyContextHydration, Ring,
    SourcePreservationManager,
)


class SemanticGraphTests(unittest.TestCase):
    def test_exact_source_reconstruction_unicode_and_whitespace(self):
        samples = ["", "Hello, CSC LCH!\n", "  tabs\tand spaces  ", "emoji 🧠 café 漢字"]
        for text in samples:
            record = SourcePreservationManager.create_source_record(text)
            self.assertEqual("".join(record.token_boundaries), text)
            self.assertTrue(SourcePreservationManager.verify_source(record))
            self.assertTrue(SourcePreservationManager.verify_source(record, text))

    def test_source_tampering_is_detected(self):
        record = SourcePreservationManager.create_source_record("original")
        self.assertFalse(SourcePreservationManager.verify_source(record, "changed"))

    def test_empty_source_is_valid(self):
        record = SourcePreservationManager.create_source_record("")
        self.assertEqual(record.token_boundaries, [])
        self.assertTrue(SourcePreservationManager.verify_source(record))

    def test_interning_reuses_ids_and_tracks_frequency(self):
        graph = DynamicSemanticGraph(initial_capacity=2, growth_chunk=2)
        first = graph.intern("alpha")
        second = graph.intern("alpha")
        self.assertEqual(first, second)
        self.assertEqual(graph.nodes[first].frequency, 2)
        self.assertEqual(graph.stats()["allocated_nodes"], 1)

    def test_capacity_grows_without_reusing_ids(self):
        graph = DynamicSemanticGraph(initial_capacity=1, growth_chunk=2)
        ids = [graph.intern(str(i)) for i in range(6)]
        self.assertEqual(ids, list(range(6)))
        self.assertGreaterEqual(graph.capacity, 6)

    def test_ring_moves_keep_membership_consistent(self):
        graph = DynamicSemanticGraph()
        sid = graph.intern("keep")
        graph.move(sid, Ring.ARCHIVE)
        self.assertIn(sid, graph.ring_members[Ring.ARCHIVE])
        self.assertNotIn(sid, graph.ring_members[Ring.ACTIVE])
        self.assertTrue(graph.validate())

    def test_typed_edges_are_independent(self):
        graph = DynamicSemanticGraph()
        a, b = graph.intern("a"), graph.intern("b")
        graph.connect(a, b, "semantic", 0.9)
        graph.connect(a, b, "temporal", 0.5)
        self.assertEqual(len(graph.edges), 2)
        self.assertEqual(graph.neighbors(a, "temporal"), [b])
        self.assertEqual(graph.neighbors(b), [a])

    def test_invalid_edges_are_rejected(self):
        graph = DynamicSemanticGraph()
        a = graph.intern("a")
        with self.assertRaises(ValueError):
            graph.connect(a, a)
        with self.assertRaises(ValueError):
            graph.connect(a, 999)

    def test_encode_decode_retains_original_exactly(self):
        graph = DynamicSemanticGraph()
        source = "x = 'hello 🧠'\n\n"
        encoded = graph.encode_source(source)
        self.assertEqual(graph.decode_source(encoded), source)
        self.assertEqual(len(encoded.symbol_ids), len(encoded.token_spellings))

    def test_codebook_round_trip_preserves_graph(self):
        graph = DynamicSemanticGraph(initial_capacity=2, growth_chunk=3)
        a = graph.intern("alpha", source_ref="src1")
        b = graph.intern("beta", Ring.WORKING)
        graph.connect(a, b, "supports", 0.75)
        graph.move(a, Ring.CONSOLIDATED)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "codebook.json"
            graph.save_codebook(path)
            restored = DynamicSemanticGraph.load_codebook(path)
        self.assertTrue(restored.validate())
        self.assertEqual(restored.stats(), graph.stats())
        self.assertEqual(restored.nodes[a].text, "alpha")
        self.assertEqual(restored.neighbors(a), [b])
        self.assertEqual(restored.edges[(a, b, "supports")], Edge(a, b, "supports", 0.75))

    def test_corrupt_codebook_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"format_version": 999}), encoding="utf-8")
            with self.assertRaises(ValueError):
                DynamicSemanticGraph.load_codebook(path)

    def test_lazy_hydration_records_retrieval(self):
        graph = DynamicSemanticGraph()
        sid = graph.intern("node")
        source = SourcePreservationManager.create_source_record("source")
        lch = LazyContextHydration(graph, source)
        self.assertEqual(lch.get_node(sid).text, "node")
        self.assertEqual(lch.hydrate_source().original_text, "source")
        self.assertEqual([x.query_type for x in lch.audit_log], ["get_node", "hydrate_source"])


if __name__ == "__main__":
    unittest.main()
