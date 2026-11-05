# Adaptive Mechanism-Based CSC LCH

**Author:** William Ganel Cox  
**Status:** Design proposal; not yet experimentally validated  
**Scope:** LLM context compression, token efficiency, semantic preservation, selective retrieval, and evidence-grounded latent representations

## 1. Purpose

Combine Cascading Semantic Compression + Lazy Context Hydration (CSC LCH) with a mechanism-based discovery loop. The system represents the structure that carries task-relevant meaning, estimates what can be omitted safely, detects information gaps, and retrieves source evidence only when a task requires it.

This document describes a testable design, not a claim of novelty or demonstrated performance.

## 2. Unified pipeline

1. **Ingest:** retain the original source and stable source-span references.
2. **Decompose:** extract entities, actions, attributes, relations, quantities, time, conditions, negation, modality, and causal or procedural dependencies when supported by the text.
3. **Build a semantic graph:** represent facts and dependencies without inventing missing links.
4. **Label evidence:** tag each item as OBS (directly present in source), INF (inferred, with rationale), or UNK (unknown/unresolved). Store provenance and confidence separately.
5. **Find redundancy:** merge repeated entities and repeated structures only when distinctions, scope, and provenance remain recoverable.
6. **Choose a representation:** select a compact encoding based on the target task, actual tokenizer, context budget, and preservation requirements.
7. **Detect gaps:** inspect required task questions and identify which answers are unsupported by the compact representation.
8. **Hydrate selectively:** retrieve exact source spans for unresolved, relevant details. Never fill a gap from guesswork when the source does not support an answer.
9. **Validate:** check required facts, relations, quantities, ordering, negation, conditions, and citations against the source.
10. **Measure and adapt:** record token costs, errors, retrieval frequency, and task outcomes. Change compression rules only based on reproducible evaluation results.
11. **Extract principles:** after evidence has been validated, summarize recurring mechanisms or principles while retaining links to the supporting and contradicting evidence.
12. **Map principles into latent representations:** embed evidence spans and extracted principles using a fixed, documented embedding model and version. Preserve the original text, provenance, and evidence status beside each vector.

## 3. Representation contract

Each retained fact should be expressible as a record with fields equivalent to subject, predicate, object, qualifiers (time, quantity, condition, modality, negation), evidence_status (OBS, INF, UNK), source_spans, confidence (only where a meaningful calibrated estimate exists), and task_relevance.

A compact serialization is not automatically smaller. Measure the serialized form with the tokenizer used by the target model; do not assume symbols, emoji, YAML, or graph notation save tokens.

## 4. Compression modes

**Exact / lossless mode:** preserve enough information to reconstruct the original bytes or text exactly. Use a reversible encoding and verify round-trip equality. Semantic graphs alone do not guarantee lossless reconstruction.

**Task-bounded semantic mode:** preserve a declared set of facts and relationships needed for a defined task. Record the task scope and validate against held-out questions. Do not call this lossless.

**Adaptive mode:** start with a compact task-bounded representation, then hydrate from the source when evidence is missing or the task changes. Include all hydration overhead in the cost.

## 5. Cost objective

Minimize J = T_rep + T_meta + λ T_hydrate + μ L_task + ν E_unsupported.

T_rep is tokens in the compressed representation; T_meta is tokens for metadata, provenance, indexes, and control instructions; T_hydrate is retrieval requests plus retrieved source tokens; L_task is measured task-relevant information loss or task error; E_unsupported is a penalty for answers asserted without adequate evidence. The weights λ, μ, and ν must be declared before each comparison.

Report raw measurements alongside any weighted score. A weighted score must not hide an accuracy regression.

## 6. Resource-bounded discovery loop

For each proposed compression rule or representation, state a hypothesis and expected failure mode; estimate compute, memory, tokens, and test cases; reject experiments that exceed the declared budget; run deterministic local tests first with no paid API calls; compare methods on identical inputs and held-out questions; update hypotheses only from observed evidence; and stop when the budget is exhausted, results are inconclusive, or a predeclared stop condition is met.

The system must be allowed to conclude that no tested method wins.

## 7. Fair benchmark protocol

Compare the original context, an ordinary summary, a structured semantic representation without hydration, and a structured semantic representation with lazy hydration. Use the same source passages, task questions, tokenizer, and accuracy criteria. Count all attributable tokens, including instructions, schema, metadata, indexes, retrieval queries, retrieved spans, and repair attempts.

Pre-register the dataset split, token-counting method, allowed external knowledge, accuracy tolerance, resource budget, and primary metric before examining test results. Tune on a development set; keep a held-out test set untouched until final evaluation. Apply equivalent effort and access to source information across methods. Report raw scores and uncertainty, not only a weighted objective. Include failures and cases where no method meets the target. The ordinary-summary baseline must be allowed to win.

Report total tokens and percentage change; held-out answer accuracy; entity and relation preservation; negation, quantity, time, and condition preservation; hydration rate and overhead; unsupported-claim rate; exact reconstruction success only for lossless mode; and failures or inconclusive cases.

Do not tune on the evaluation questions and then claim independent evaluation. Start with a small hand-checkable test set.

## 8. Latent-space analysis of evidence and principles

Latent space can help organize semantic relationships, but it does not provide a universal coordinate system. Coordinates depend on the chosen embedding model, model version, input formatting, and context. A vector location is not by itself proof that a principle is true or causally important.

Use this sequence:

1. **Define evidence units:** split source material into stable, citable spans and keep each span's source ID, timestamp or section when available, and OBS/INF/UNK label.
2. **Extract candidate principles:** state each principle as a concise proposition with its mechanism, conditions, and predicted consequences. Link it to supporting, contradicting, and unresolved evidence. Do not merge contradictory principles merely because their vectors are close.
3. **Embed consistently:** use the same embedding model and version, input template, and normalization policy for all evidence and principles in a comparison. Store model/version metadata with each vector.
4. **Measure relationships:** use cosine similarity or another declared metric to retrieve candidate-neighbor evidence. Treat similarity as a search signal, not as a truth score. Check important links against the source and, where appropriate, against counterexamples.
5. **Find gaps:** compare a proposed principle's predicted consequences with observed evidence. Mark missing observations as unknown; generate a testable hypothesis rather than filling the gap by assumption.
6. **Evaluate structure:** assess retrieval precision/recall on labeled examples, whether contradictions remain visible, and whether nearby vectors actually share the relevant mechanism. Compare with simple lexical or keyword retrieval as a baseline.
7. **Visualize carefully:** use PCA or UMAP only as a view of high-dimensional relationships. Distances and apparent clusters in a two-dimensional projection can distort the original geometry. Do not treat plotted axes as intrinsic semantic dimensions.
8. **Update with evidence:** after a new experiment, update the principle's evidence links and confidence calibration. Re-embedding or changing models requires a versioned migration; coordinates from different embedding spaces must not be compared directly without a validated alignment method.

The practical goal is not to claim an exact universal latent-space address for a principle. It is to build a reproducible, model-specific map of semantic proximity, evidence support, disagreement, and unanswered questions.

## 9. Initial falsifiable hypotheses

**H1:** On a defined set of LLM-context tasks, structured semantic compression with selective source hydration reduces total tokens relative to an ordinary summary while keeping held-out task accuracy within a predeclared tolerance.

**H2:** Evidence-linked principle embeddings improve retrieval of relevant supporting and contradicting evidence over a declared baseline, without increasing unsupported claims.

Possible disconfirming outcomes: metadata overhead erases savings; hydration retrieves too much; parsing loses distinctions; accuracy falls; embeddings fail to retrieve counterevidence; or simple keyword search performs equally well at lower cost. Set tolerances, dataset, model versions, metrics, and budget before evaluation.

## 10. Safety and correctness invariants

Never convert an inference into an observation. Preserve negation, uncertainty, units, time, conditions, and provenance. Do not treat missing information as false or as evidence for a preferred hypothesis. Do not silently answer from external knowledge when source-grounded answers are required. Hydration must use an authorized source and must not use the expected answer as an oracle. Keep a fallback to the original source when the compressed form fails validation. Report measurements separately from estimates and design expectations.

## 11. Initial implementation boundary

The first prototype should be deliberately small: deterministic fact records, source-span references, a simple budget-aware encoder, a query-to-fact coverage check, and a local benchmark. Add evidence-linked principle extraction and embeddings as a separate measured stage only after the basic compression benchmark is reproducible. Avoid paid API calls, speculative prefetch, and complex probability tuning until the baseline demonstrates a measurable benefit.

**Current evidence status:** architecture proposal only. No performance result is claimed by this document.
