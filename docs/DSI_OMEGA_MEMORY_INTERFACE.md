# DSI-Ω / CSC-LCH Memory Interface — Milestone 1

**Author:** William Gunnell Cox  
**Status:** Initial local prototype  
**Dependencies:** Python standard library only

## Purpose

Provide one replaceable memory contract for DSI-Ω coordinator, research,
engineering, and verification modules. CSC-LCH remains the semantic memory
layer; this package is an adapter and local storage implementation, not a new
independent memory framework.

## First implementation

The dsi_omega.memory.MemoryBackend protocol defines the shared contract.
SQLiteMemoryStore implements it using SQLite and no network service.

Example:

    from dsi_omega import SQLiteMemoryStore

    with SQLiteMemoryStore("workspace_memory.sqlite3") as memory:
        record = memory.add(
            project_id="my-project",
            title="Baseline benchmark",
            content="The original experiment notes and measurements...",
            summary="Baseline run; preserve the exact measurements.",
            tier="T2",
            evidence="OBS",
            source_ref="benchmarks/run-001.json",
            tags=["benchmark", "baseline"],
        )
        hits = memory.search("baseline benchmark", project_id="my-project")
        original = memory.hydrate(record.memory_id)

## Preservation and hydration

- Original text is stored separately from its summary.
- A SHA-256 digest is calculated over the exact UTF-8 encoding of the stored text.
- Hydration recalculates and checks that digest before returning the source.
- T0–T3 records are hydrated by default in search results.
- T4–T5 records return summary-only stubs unless hydrate=True is requested.
- deactivate() is a soft-delete; it does not erase the archived source.

This local text store does not claim byte-for-byte preservation of arbitrary
binary files. For file archives, use the repository's separate source-integrity
manifest verifier over the original file bytes.

## Retrieval baseline

Search is project-scoped and uses deterministic lexical overlap with weighted
title, summary, tag, and content matches. It is intentionally dependency-free.
It is not embedding-based semantic search, and benchmark results must not be
described as semantic retrieval performance.

## Run tests

From the repository root:

    python -m unittest discover -s tests -v

The tests are offline and use temporary local databases.

## Limitations and next steps

- Single-process local SQLite implementation; no distributed synchronization yet.
- No access-control or multi-user tenancy layer; keep the database in a trusted,
  appropriately permissioned workspace.
- Lexical search is a baseline; evaluate retrieval recall before adding embeddings.
- No automatic summarizer is included. Summaries are supplied by the caller and
  must not replace the original content.
- No provider API, external service, or paid dependency is required.

The interface is designed so future distributed stores can implement
MemoryBackend without changing DSI-Ω callers.
