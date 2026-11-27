# Hybrid Retrieval and QBS Tuning (Experimental)

This prototype adds a deterministic retrieval layer that can be evaluated separately before integration into CSC-LCH.

## Capabilities

- Sentence-sized chunks with exact source offsets.
- BM25-style lexical ranking.
- Exact phrase and identifier signals for versions, IDs, paths, and numeric codes.
- Diversity penalty to reduce redundant selected chunks.
- Character-budget enforcement and source-backed retrieval results.
- Bounded classical grid search with a development split and a held-out evaluation.

## Limitations

- Not a semantic embedding model.
- Does not summarize or irreversibly compress source material.
- No LLM inference, paid APIs, or quantum computation.
- Character reduction is not token reduction. Token claims require the target model tokenizer and must include index, stub, tool, and hydration overhead.
- Exact evidence-string recall is not answer accuracy. Answer accuracy is reported as null.

## Run tests

From the repository root:

    python -m unittest tests.test_hybrid_retrieval -v

## Run the tuner

Prepare JSONL rows with id, question, context, and a non-empty gold_evidence list. Every evidence string must occur exactly in that row's context.

    python benchmarks/qbs_hybrid_retrieval_tuner.py path/to/evidence_dataset.jsonl --seed 2026 --min-recall 0.90 --out artifacts/qbs_hybrid_retrieval_tuning.json

The tuner evaluates 81 configurations on a deterministic 70/30 development/held-out split. It selects using development metrics only and evaluates the selected configuration once on held-out data. If no development candidate meets the recall gate, the best utility candidate is still reported and the gate remains visibly failed.

## Integration gate

Do not connect this to live CSC-LCH compression/hydration until it demonstrates high evidence recall, preserves critical facts and qualifications, reduces target-tokenizer cost after all overhead, and improves reproducibly against existing controls without unacceptable latency or memory overhead.
