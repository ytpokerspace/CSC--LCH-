"""CSC LCH + Five-Cube Context Engine prototype.

Experimental reference implementation:
- Source text remains authoritative.
- Graph traversal is bounded by max_hops.
- Five-cube metadata contributes to candidate ranking.
- Overlapping half-open source spans are merged.
- Candidates are admitted only when the assembled payload fits the token budget.
- Invalid source references and offsets are reported.
- Original source text is never reconstructed from token IDs.

The included whitespace tokenizer is for tests and demos only. Use the exact
tokenizer for the target model before making real token-budget claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Sequence, Set, Tuple
import hashlib
import heapq
import unittest


Coordinates = Tuple[int, int, int, int, int]
Span = Tuple[int, int]


@dataclass(frozen=True)
class Node:
    source_id: str
    start_offset: int
    end_offset: int
    tier: int = 1
    priority: float = 0.5


@dataclass
class HydrationResult:
    budget_tokens: int
    actual_tokens: int
    nodes_considered: int
    nodes_selected: int
    spans_before_merge: int
    spans_after_merge: int
    source_bytes: int
    truncated: bool
    reconstructed_text: str
    spatial_coordinates: List[Coordinates]
    rejected_for_budget: int
    integrity_errors: List[str]


def whitespace_tokenizer(text: str) -> List[str]:
    """Demo/test tokenizer only; not representative of a specific LLM."""
    return text.split() if text else []


class CSCLCHFiveCubeEngine:
    """CSC LCH-style selective hydration with experimental five-cube ranking."""

    def __init__(
        self,
        source_records: Dict[str, str],
        graph_nodes: Dict[str, Any],
        adj_list: Dict[str, List[str]],
        tokenizer: Callable[[str], Sequence[Any]],
    ) -> None:
        self.source_records = source_records
        self.graph_nodes = graph_nodes
        self.adj_list = adj_list
        self.tokenizer = tokenizer

    def _coordinates(
        self, node_id: str, node: Any, hop: int
    ) -> Coordinates:
        """Build deterministic binary coordinates from node metadata."""
        tier = getattr(node, "tier", 1)
        priority = getattr(node, "priority", 0.5)
        source_id = getattr(node, "source_id", None)

        # A stable hash bit is reproducible, but is NOT semantic similarity.
        digest = hashlib.sha256(node_id.encode("utf-8")).digest()
        stable_bit = digest[0] & 1

        return (
            int(tier <= 1),
            int(priority >= 0.8),
            int(hop <= 1),
            int(source_id in self.source_records),
            int(stable_bit == 0),
        )

    @staticmethod
    def _cube_weight(coords: Coordinates) -> float:
        """Normalized five-axis vertex weight in the range 0.0–1.0."""
        return sum(coords) / 5.0

    def _validate_node(self, node_id: str) -> str | None:
        node = self.graph_nodes[node_id]
        source_id = getattr(node, "source_id", None)

        if source_id not in self.source_records:
            return f"{node_id}: missing source {source_id!r}"

        source = self.source_records[source_id]
        if not isinstance(source, str):
            return f"{node_id}: source must be a string"

        start = getattr(node, "start_offset", None)
        end = getattr(node, "end_offset", None)

        # bool is a subclass of int; reject it as an offset.
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
        ):
            return f"{node_id}: offsets must be integers"

        if start < 0 or end < start or end > len(source):
            return (
                f"{node_id}: invalid interval [{start}, {end}) "
                f"for source length {len(source)}"
            )

        priority = getattr(node, "priority", 0.5)
        if (
            not isinstance(priority, (int, float))
            or isinstance(priority, bool)
        ):
            return f"{node_id}: priority must be numeric"

        return None

    def _merge_spans(
        self, selected: Sequence[str]
    ) -> Dict[str, List[Span]]:
        grouped: Dict[str, List[Span]] = {}

        for node_id in selected:
            node = self.graph_nodes[node_id]
            grouped.setdefault(node.source_id, []).append(
                (node.start_offset, node.end_offset)
            )

        merged_by_source: Dict[str, List[Span]] = {}

        for source_id, spans in grouped.items():
            merged: List[Span] = []

            for start, end in sorted(spans):
                # Merge overlapping or adjacent half-open intervals.
                if merged and start <= merged[-1][1]:
                    previous_start, previous_end = merged[-1]
                    merged[-1] = (
                        previous_start,
                        max(previous_end, end),
                    )
                else:
                    merged.append((start, end))

            merged_by_source[source_id] = merged

        return merged_by_source

    def _assemble(
        self, selected: Sequence[str]
    ) -> Tuple[str, int, int]:
        merged = self._merge_spans(selected)
        parts: List[str] = []

        # Stable order makes the final payload reproducible.
        for source_id in sorted(merged):
            source = self.source_records[source_id]
            for start, end in merged[source_id]:
                parts.append(source[start:end])

        payload = "\n...\n".join(parts)
        return (
            payload,
            len(selected),
            sum(len(spans) for spans in merged.values()),
        )

    def retrieve(
        self,
        seed_node_ids: List[str],
        token_budget: int = 40,
        max_hops: int = 2,
    ) -> HydrationResult:
        if token_budget < 0:
            raise ValueError("token_budget cannot be negative")
        if max_hops < 0:
            raise ValueError("max_hops cannot be negative")

        if token_budget == 0:
            return HydrationResult(
                budget_tokens=0,
                actual_tokens=0,
                nodes_considered=0,
                nodes_selected=0,
                spans_before_merge=0,
                spans_after_merge=0,
                source_bytes=0,
                truncated=False,
                reconstructed_text="",
                spatial_coordinates=[],
                rejected_for_budget=0,
                integrity_errors=[],
            )

        queue = []
        discovered: Set[str] = set()
        selected: List[str] = []
        coordinates: Dict[str, Coordinates] = {}
        counter = 0
        considered = 0
        rejected = 0
        errors: List[str] = []

        for seed_id in seed_node_ids:
            if seed_id not in self.graph_nodes:
                errors.append(f"Unknown seed node: {seed_id}")
                continue
            if seed_id in discovered:
                continue

            discovered.add(seed_id)
            node = self.graph_nodes[seed_id]
            coords = self._coordinates(seed_id, node, 0)
            coordinates[seed_id] = coords
            priority = float(getattr(node, "priority", 0.5))

            heapq.heappush(
                queue,
                (-self._cube_weight(coords), -priority, counter, seed_id, 0),
            )
            counter += 1

        while queue:
            _, _, _, node_id, hop = heapq.heappop(queue)
            considered += 1
            error = self._validate_node(node_id)

            if error:
                errors.append(error)
            else:
                # Count the complete payload, including separators and merges.
                candidate_text, _, _ = self._assemble(selected + [node_id])
                if len(self.tokenizer(candidate_text)) <= token_budget:
                    selected.append(node_id)
                else:
                    rejected += 1

            # A rejected node does not stop traversal: a descendant may fit.
            if hop < max_hops:
                for neighbor_id in self.adj_list.get(node_id, []):
                    if neighbor_id not in self.graph_nodes:
                        errors.append(
                            f"{node_id}: unknown neighbor {neighbor_id}"
                        )
                        continue
                    if neighbor_id in discovered:
                        continue

                    discovered.add(neighbor_id)
                    node = self.graph_nodes[neighbor_id]
                    coords = self._coordinates(
                        neighbor_id, node, hop + 1
                    )
                    coordinates[neighbor_id] = coords
                    priority = float(getattr(node, "priority", 0.5))

                    heapq.heappush(
                        queue,
                        (
                            -self._cube_weight(coords),
                            -priority,
                            counter,
                            neighbor_id,
                            hop + 1,
                        ),
                    )
                    counter += 1

        payload, spans_before, spans_after = self._assemble(selected)
        actual_tokens = len(self.tokenizer(payload))

        # Enforce the hard-budget invariant; never fake text from token IDs.
        if actual_tokens > token_budget:
            raise RuntimeError("Final payload exceeds token budget")

        return HydrationResult(
            budget_tokens=token_budget,
            actual_tokens=actual_tokens,
            nodes_considered=considered,
            nodes_selected=len(selected),
            spans_before_merge=spans_before,
            spans_after_merge=spans_after,
            source_bytes=len(payload.encode("utf-8")),
            truncated=False,
            reconstructed_text=payload,
            spatial_coordinates=[coordinates[n] for n in selected],
            rejected_for_budget=rejected,
            integrity_errors=errors,
        )


def run_demo() -> None:
    sources = {
        "doc-alpha": (
            "Cascading semantic compression systematically reduces "
            "token overhead while preserving lossless graph integrity."
        ),
        "doc-beta": (
            "Lazy context hydration dynamically assembles budgeted payloads "
            "via priority queues and half-open intervals."
        ),
    }
    nodes = {
        "n1": Node("doc-alpha", 0, 48, tier=1, priority=0.95),
        "n2": Node("doc-alpha", 30, 85, tier=2, priority=0.75),
        "n3": Node("doc-beta", 0, 52, tier=1, priority=0.90),
    }
    adjacency = {"n1": ["n2"], "n2": ["n3"], "n3": []}

    engine = CSCLCHFiveCubeEngine(
        sources, nodes, adjacency, whitespace_tokenizer
    )
    result = engine.retrieve(["n1"], token_budget=15, max_hops=2)

    print("=== CSC LCH + Five-Cube Demo ===")
    print(f"Budget:              {result.budget_tokens}")
    print(f"Actual demo tokens:  {result.actual_tokens}")
    print(f"Nodes considered:    {result.nodes_considered}")
    print(f"Nodes selected:      {result.nodes_selected}")
    print(
        f"Spans before/after:  "
        f"{result.spans_before_merge}/{result.spans_after_merge}"
    )
    print(f"Rejected for budget: {result.rejected_for_budget}")
    print(f"Final UTF-8 bytes:   {result.source_bytes}")
    print(f"Truncated:           {result.truncated}")
    print(f"Coordinates:         {result.spatial_coordinates}")
    print(f"Integrity errors:    {result.integrity_errors}")
    print("\n--- Reconstructed Payload ---")
    print(result.reconstructed_text)


class EngineTests(unittest.TestCase):
    def make_engine(self):
        sources = {
            "a": "alpha beta gamma delta epsilon",
            "b": "Unicode text: café 東京 🌍",
        }
        nodes = {
            "a1": Node("a", 0, 16, priority=0.95),
            "a2": Node("a", 11, 27, priority=0.70),
            "b1": Node("b", 0, len(sources["b"]), priority=0.90),
        }
        graph = {"a1": ["a2"], "a2": ["b1"], "b1": []}
        return CSCLCHFiveCubeEngine(
            sources, nodes, graph, whitespace_tokenizer
        )

    def test_hard_budget(self):
        result = self.make_engine().retrieve(["a1"], 4, 2)
        self.assertLessEqual(result.actual_tokens, result.budget_tokens)

    def test_overlapping_spans_merge(self):
        result = self.make_engine().retrieve(["a1", "a2"], 20, 0)
        self.assertEqual(result.spans_before_merge, 2)
        self.assertEqual(result.spans_after_merge, 1)

    def test_unicode_preserved(self):
        result = self.make_engine().retrieve(["b1"], 20, 0)
        self.assertIn("café", result.reconstructed_text)
        self.assertIn("東京", result.reconstructed_text)
        self.assertIn("🌍", result.reconstructed_text)

    def test_missing_source_rejected(self):
        engine = self.make_engine()
        engine.graph_nodes["bad"] = Node("missing", 0, 1)
        result = engine.retrieve(["bad"], 10, 0)
        self.assertEqual(result.nodes_selected, 0)
        self.assertTrue(result.integrity_errors)

    def test_invalid_offsets_rejected(self):
        engine = self.make_engine()
        engine.graph_nodes["bad"] = Node("a", -1, 4)
        result = engine.retrieve(["bad"], 10, 0)
        self.assertEqual(result.nodes_selected, 0)
        self.assertTrue(result.integrity_errors)

    def test_zero_budget(self):
        result = self.make_engine().retrieve(["a1"], 0, 2)
        self.assertEqual(result.actual_tokens, 0)
        self.assertEqual(result.reconstructed_text, "")

    def test_coordinates_are_deterministic(self):
        engine = self.make_engine()
        node = engine.graph_nodes["a1"]
        first = engine._coordinates("a1", node, 0)
        second = engine._coordinates("a1", node, 0)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 5)
        self.assertTrue(all(bit in (0, 1) for bit in first))


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        unittest.main(argv=[sys.argv[0]])
    else:
        run_demo()
