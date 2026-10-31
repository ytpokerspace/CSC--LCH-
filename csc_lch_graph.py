"""CSC-LCH semantic graph engine.

This module is an additive, standard-library-only graph and source-preservation
component. It does not claim token compression: EncodedSource deliberately keeps
the original source so exact reconstruction can be verified independently.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


class Ring(str, Enum):
    ACTIVE = "active"
    WORKING = "working"
    CONSOLIDATED = "consolidated"
    ARCHIVE = "archive"


RING_ORDER = (Ring.ACTIVE, Ring.WORKING, Ring.CONSOLIDATED, Ring.ARCHIVE)
CODEBOOK_FORMAT_VERSION = 1


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class SourceRecord:
    source_id: str
    original_text: str
    checksum: str
    character_positions: List[Tuple[int, int]] = field(default_factory=list)
    token_boundaries: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SourcePreservationManager:
    """Retain exact source text and a reversible lexical segmentation."""

    @staticmethod
    def create_source_record(text: str, source_id: Optional[str] = None) -> SourceRecord:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        parts = re.findall(r"\w+|\s+|[^\w\s]", text, flags=re.UNICODE)
        positions: List[Tuple[int, int]] = []
        offset = 0
        for part in parts:
            end = offset + len(part)
            positions.append((offset, end))
            offset = end
        if "".join(parts) != text:
            raise AssertionError("internal segmentation failed to preserve source")
        return SourceRecord(
            source_id=source_id or f"src_{uuid.uuid4().hex}",
            original_text=text,
            checksum=sha256_text(text),
            character_positions=positions,
            token_boundaries=parts,
        )

    @staticmethod
    def verify_source(record: SourceRecord, current_text: Optional[str] = None) -> bool:
        candidate = record.original_text if current_text is None else current_text
        return (
            isinstance(candidate, str)
            and sha256_text(candidate) == record.checksum
            and candidate == record.original_text
        )


@dataclass
class Node:
    symbol_id: int
    text: str
    kind: str
    ring: Ring
    created_at: int
    last_seen: int
    frequency: int = 1
    source_ref: Optional[str] = None


@dataclass(frozen=True, order=True)
class Edge:
    left_id: int
    right_id: int
    relation_type: str = "semantic"
    weight: float = 1.0


@dataclass
class EncodedSource:
    source_text: str
    symbol_ids: List[int]
    token_spellings: List[str]
    sha256: str
    format_version: int = 1

    def decode(self) -> str:
        if sha256_text(self.source_text) != self.sha256:
            raise ValueError("source payload checksum mismatch")
        if len(self.symbol_ids) != len(self.token_spellings):
            raise ValueError("symbol/token sequence length mismatch")
        return self.source_text


class DynamicSemanticGraph:
    """Interned symbol graph with typed, undirected relationships."""

    def __init__(self, initial_capacity: int = 1536, growth_chunk: int = 1024):
        if isinstance(initial_capacity, bool) or initial_capacity < 1:
            raise ValueError("initial_capacity must be a positive integer")
        if isinstance(growth_chunk, bool) or growth_chunk < 1:
            raise ValueError("growth_chunk must be a positive integer")
        self.initial_capacity = int(initial_capacity)
        self.growth_chunk = int(growth_chunk)
        self.capacity = self.initial_capacity
        self.next_symbol_id = 0
        self.tick = 0
        self.text_to_id: Dict[str, int] = {}
        self.nodes: Dict[int, Node] = {}
        self.edges: Dict[Tuple[int, int, str], Edge] = {}
        self.ring_members: Dict[Ring, set[int]] = {ring: set() for ring in RING_ORDER}

    @staticmethod
    def _classify(text: str) -> str:
        if text.isidentifier():
            return "identifier-or-keyword"
        if text.isnumeric():
            return "number"
        if text in {"+", "-", "*", "/", "//", "%", "**", "=", "==", "!=", "<", ">", "<=", ">="}:
            return "operator"
        if text in {"(", ")", "[", "]", "{", "}", ":", ",", ".", ";"}:
            return "delimiter"
        if len(text) >= 2 and text[0] in {"'", '"'} and text[-1] == text[0]:
            return "string"
        return "symbol"

    def _ensure_capacity_for(self, count: int) -> None:
        while count > self.capacity:
            self.capacity += self.growth_chunk

    def intern(
        self, text: str, ring: Ring = Ring.ACTIVE, source_ref: Optional[str] = None
    ) -> int:
        if not isinstance(text, str) or not text:
            raise ValueError("text must be a non-empty string")
        ring = Ring(ring)
        self.tick += 1
        existing = self.text_to_id.get(text)
        if existing is not None:
            node = self.nodes[existing]
            node.frequency += 1
            node.last_seen = self.tick
            if source_ref is not None:
                node.source_ref = source_ref
            return existing
        symbol_id = self.next_symbol_id
        self._ensure_capacity_for(symbol_id + 1)
        self.next_symbol_id += 1
        node = Node(
            symbol_id, text, self._classify(text), ring,
            self.tick, self.tick, 1, source_ref
        )
        self.nodes[symbol_id] = node
        self.text_to_id[text] = symbol_id
        self.ring_members[ring].add(symbol_id)
        return symbol_id

    def move(self, symbol_id: int, destination: Ring) -> None:
        if symbol_id not in self.nodes:
            raise KeyError(f"unknown symbol ID: {symbol_id}")
        destination = Ring(destination)
        node = self.nodes[symbol_id]
        if node.ring != destination:
            self.ring_members[node.ring].remove(symbol_id)
            self.ring_members[destination].add(symbol_id)
            node.ring = destination
        self.tick += 1
        node.last_seen = self.tick

    def connect(
        self, left_id: int, right_id: int, relation_type: str = "semantic",
        weight: float = 1.0
    ) -> Edge:
        if left_id not in self.nodes or right_id not in self.nodes:
            raise KeyError("both edge endpoints must exist")
        if left_id == right_id:
            raise ValueError("self-edges are not supported")
        if not isinstance(relation_type, str) or not relation_type.strip():
            raise ValueError("relation_type must be a non-empty string")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise TypeError("weight must be numeric")
        if not 0.0 <= float(weight) <= 1.0:
            raise ValueError("weight must be between 0.0 and 1.0")
        a, b = sorted((left_id, right_id))
        edge = Edge(a, b, relation_type.strip(), float(weight))
        self.edges[(a, b, edge.relation_type)] = edge
        return edge

    def neighbors(self, symbol_id: int, relation_type: Optional[str] = None) -> List[int]:
        if symbol_id not in self.nodes:
            raise KeyError(f"unknown symbol ID: {symbol_id}")
        found = set()
        for edge in self.edges.values():
            if relation_type is not None and edge.relation_type != relation_type:
                continue
            if edge.left_id == symbol_id:
                found.add(edge.right_id)
            elif edge.right_id == symbol_id:
                found.add(edge.left_id)
        return sorted(found)

    def encode_source(self, source: str, source_ref: Optional[str] = None) -> EncodedSource:
        # This lexical pass indexes tokens but never substitutes or discards source bytes.
        tokens = re.findall(r"\w+|[^\w\s]", source, flags=re.UNICODE)
        ids = [self.intern(item, source_ref=source_ref) for item in tokens]
        return EncodedSource(source, ids, tokens, sha256_text(source))

    @staticmethod
    def decode_source(encoded: EncodedSource) -> str:
        return encoded.decode()

    def stats(self) -> Dict[str, Any]:
        return {
            "capacity": self.capacity,
            "allocated_nodes": len(self.nodes),
            "unused_capacity": self.capacity - len(self.nodes),
            "edges": len(self.edges),
            "ring_counts": {ring.value: len(self.ring_members[ring]) for ring in RING_ORDER},
            "unique_symbols": len(self.text_to_id),
        }

    def validate(self) -> bool:
        if len(self.text_to_id) != len(self.nodes):
            raise ValueError("text index and node table differ in size")
        seen: set[int] = set()
        for ring, members in self.ring_members.items():
            for symbol_id in members:
                if symbol_id not in self.nodes or self.nodes[symbol_id].ring != ring:
                    raise ValueError("ring membership is inconsistent")
                if symbol_id in seen:
                    raise ValueError("node appears in multiple rings")
                seen.add(symbol_id)
        if seen != set(self.nodes):
            raise ValueError("some nodes have no ring membership")
        for text, symbol_id in self.text_to_id.items():
            if symbol_id not in self.nodes or self.nodes[symbol_id].text != text:
                raise ValueError("text index is inconsistent")
        for key, edge in self.edges.items():
            if key != (edge.left_id, edge.right_id, edge.relation_type):
                raise ValueError("edge index is inconsistent")
            if edge.left_id not in self.nodes or edge.right_id not in self.nodes:
                raise ValueError("edge references a missing node")
        if self.next_symbol_id <= max(self.nodes, default=-1):
            raise ValueError("next_symbol_id would reuse an allocated ID")
        if self.capacity < len(self.nodes):
            raise ValueError("capacity is smaller than allocated node count")
        return True

    def save_codebook(self, path: str | os.PathLike[str]) -> None:
        self.validate()
        payload = {
            "format_version": CODEBOOK_FORMAT_VERSION,
            "initial_capacity": self.initial_capacity,
            "growth_chunk": self.growth_chunk,
            "capacity": self.capacity,
            "next_symbol_id": self.next_symbol_id,
            "tick": self.tick,
            "nodes": [
                {**asdict(node), "ring": node.ring.value}
                for _, node in sorted(self.nodes.items())
            ],
            "edges": [asdict(edge) for _, edge in sorted(self.edges.items())],
        }
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    @classmethod
    def load_codebook(cls, path: str | os.PathLike[str]) -> "DynamicSemanticGraph":
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("format_version") != CODEBOOK_FORMAT_VERSION:
            raise ValueError("unsupported codebook format version")
        graph = cls(payload["initial_capacity"], payload["growth_chunk"])
        graph.capacity = int(payload["capacity"])
        graph.next_symbol_id = int(payload["next_symbol_id"])
        graph.tick = int(payload["tick"])
        for raw in payload["nodes"]:
            raw = dict(raw)
            raw["ring"] = Ring(raw["ring"])
            node = Node(**raw)
            if node.symbol_id in graph.nodes or node.text in graph.text_to_id:
                raise ValueError("duplicate node ID or symbol text in codebook")
            graph.nodes[node.symbol_id] = node
            graph.text_to_id[node.text] = node.symbol_id
            graph.ring_members[node.ring].add(node.symbol_id)
        for raw in payload["edges"]:
            edge = Edge(**raw)
            key = (edge.left_id, edge.right_id, edge.relation_type)
            if key in graph.edges:
                raise ValueError("duplicate edge in codebook")
            graph.edges[key] = edge
        graph.validate()
        return graph


@dataclass
class RetrievalLog:
    query_type: str
    target_id: str
    timestamp: float
    retrieved_data: Any


class LazyContextHydration:
    """Small auditable retrieval facade over graph nodes and preserved source."""

    def __init__(self, graph: DynamicSemanticGraph, source_record: SourceRecord):
        self.graph = graph
        self.source_record = source_record
        self.audit_log: List[RetrievalLog] = []

    def get_node(self, node_id: int) -> Optional[Node]:
        node = self.graph.nodes.get(node_id)
        self.audit_log.append(RetrievalLog("get_node", str(node_id), time.time(), node_id if node else None))
        return node

    def get_neighbors(self, node_id: int, relation_type: Optional[str] = None) -> List[Node]:
        ids = self.graph.neighbors(node_id, relation_type)
        self.audit_log.append(RetrievalLog("get_neighbors", str(node_id), time.time(), ids))
        return [self.graph.nodes[item] for item in ids]

    def hydrate_source(self) -> SourceRecord:
        self.audit_log.append(
            RetrievalLog("hydrate_source", self.source_record.source_id, time.time(), self.source_record.checksum)
        )
        return self.source_record
