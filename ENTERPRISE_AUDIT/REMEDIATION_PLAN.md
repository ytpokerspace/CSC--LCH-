# Enterprise Audit Remediation — CSC-LCH

**Owner:** William Gunnell Cox  
**Repository:** yt pokerspace / CSC-LCH  
**Status:** Baseline plan committed; remediation evidence not yet established.

## Audit objective

Demonstrate that context compression and lazy hydration preserve task-critical facts, provenance, and answer correctness while accounting for the complete token and latency cost.

## Existing evidence inspected

- The repository contains a paired benchmark harness and tests in `tests/test_paired_benchmark.py`.
- The paired harness checks identical question sets, duplicate observations, baseline consistency, and source provenance.
- The README explicitly describes CSC-LCH as a research prototype and says reported results require independent reproduction.
- The current paired test fixture is synthetic. It is not evidence of real-corpus or production retrieval accuracy.

## Remediation sequence

### CSC-A1 — Dataset and provenance contract
- Require stable task IDs, source IDs, source hashes, dataset version, policy version, and run configuration.
- Separate synthetic fixtures, user-supplied corpora, and externally sourced benchmark data.
- Reject duplicate pairs, missing source references, and mismatched baseline/policy task sets.
- Preserve original source records; summaries must retain resolvable provenance.

### CSC-A2 — Paired semantic-fidelity evaluation
- Evaluate baseline and compressed-plus-hydrated context on identical questions and model/configuration.
- Measure exact required-fact recall, answer correctness, citation/provenance correctness, abstention behavior, and unsupported-claim rate.
- Use deterministic checks wherever an answer has a verifiable expected fact. Similarity scores are diagnostic signals only, not proof of equivalence.
- Report confidence intervals and per-task failures; do not hide aggregate regressions.

### CSC-A3 — Hydration safety
- Define explicit triggers from missing required facts, unresolved references, low retrieval confidence, or failed deterministic validation.
- Hydrate original source spans before finalizing an answer when a required fact is missing or uncertain.
- Record hydration reason, source IDs, retrieved spans, and added token cost.
- Fail closed when source material cannot be recovered.

### CSC-A4 — Acceptance gate
The proposed maximum 1.5% accuracy degradation is a target, not a current result. Define the metric and confidence method before enforcing it. Release gate requires:
- same paired task set and model/configuration;
- predeclared metric and non-inferiority margin;
- zero silent source/provenance loss;
- reproducible run manifest and raw per-task results;
- documented failures and limitations.

## Required evidence artifacts

- `evidence/dataset_manifest.json`
- `evidence/run_manifest.json`
- `evidence/paired_results.jsonl`
- `evidence/summary.md`
- `evidence/source-integrity.json`

## Current status

| Gate | Status | Evidence needed |
|---|---|---|
| Paired harness structural tests | Existing tests present; execution not performed in this audit | CI run URL and test output |
| Real retrieval/QA evaluation | NOT RUN | Representative, permissioned corpus and fixed evaluation config |
| Semantic non-inferiority ≤1.5% | NOT VERIFIED | Predefined metric, adequate sample, paired results |
| Deterministic replay | NOT VERIFIED | Repeated run manifests and matching deterministic fields |
| Lossless source preservation | NOT VERIFIED by this plan | Hash-verified source archive and reconstruction tests |

## Execution constraints

Offline tests only by default. No provider-backed API calls, paid datasets, external benchmark submissions, or live model evaluations without separate maintainer authorization.

## Change control

This plan is additive. It does not alter the repository's existing license or claim that the acceptance criteria have passed. Resolve licensing centrally before publishing an SDK or changing distribution terms.


## Implementation update — CSC-A1 source integrity increment

The audit branch now includes an offline source archive integrity verifier:

- `scripts/source_integrity.py` validates a versioned dataset manifest and checks each archived source's exact byte length and SHA-256 digest.
- Source IDs must be unique; required dataset/policy metadata and run configuration must be present.
- Archive paths are resolved and constrained to the declared archive root, including symlink resolution.
- Duplicate JSON object keys are rejected rather than silently overwritten.
- `tests/test_source_integrity.py` covers exact-byte verification (including Unicode and CRLF/trailing whitespace), tampering, duplicate IDs, path traversal, missing metadata, duplicate JSON keys, and length mismatch.
- `.github/workflows/offline-tests.yml` adds a Python 3.11 compile and standard-library unittest gate.

**Validation status:** implementation and test files are committed to this audit branch. The workflow is configured, but a completed CI result has not yet been confirmed in this audit. Do not treat the tests as passed until the Actions run is inspected. This verifier establishes integrity only for the source records explicitly listed in a manifest; it does not prove dataset completeness, semantic fidelity, or model answer correctness.
