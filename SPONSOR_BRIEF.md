# CSC-LCH — Research and Sponsorship Brief

**Project:** Cascading Semantic Compression + Lazy Context Hydration  
**Repository:** https://github.com/ytpokerspace/CSC--LCH-  
**Maintainer:** `ytpokerspace`  
**Stage:** Open research prototype; seeking technical review and a carefully scoped evaluation partner.

## Research question

Can a conservative context-compression layer combined with selective retrieval reduce the total context tokens needed for a task **without reducing correctness** once encoding, decoding instructions, retrieval overhead, and failure cases are counted?

The project treats this as an empirical question. It does not claim universal token savings, general accuracy improvements, or production readiness.

## What exists

- A Python benchmark harness for comparing context representations and retrieval behavior.
- A YAML instruction-set specification for a prompt-layer version of CSC-LCH.
- Synthetic corpus generation and a corpus-file input path.
- An offline `--dry-run` mode that can exercise benchmark logic without an API key or model-generation calls.
- Optional API-backed token counting and a separate optional live Q&A quality test.
- Explicit reporting limits distinguishing synthetic data, estimated token counts, and live measurements.

The Python harness is the executable benchmark. The YAML instruction set is a specification, not an independently executable optimizer.

## Evidence boundary

Offline tests can establish that the harness runs and that specific transformations/retrieval checks behave as expected. They cannot establish that an LLM will answer more accurately or that the approach saves money in production.

The dry-run tokenizer figures are estimates and must not be represented as actual model token counts. API-backed token-count measurements are different from live model-quality tests. The optional quality test makes live model calls and may incur charges.

Any credible evaluation should compare, on the same frozen task set:

1. Original full context.
2. Compressed context without hydration.
3. Compressed context with verifier-triggered hydration.

Report per-task correctness, total input/output tokens including all overhead, retrieval misses, model-call count, latency, cost, and failures. Use independent or deterministic scoring where possible. Publish negative results and limitations.

## Proposed first collaboration

The first stage costs no API spend: reproduce the offline tests, review the design, add adversarial synthetic cases, and agree on a task-specific evaluation protocol. A later provider-backed evaluation should occur only if the maintainer explicitly approves the provider, model, exact task set, call limits, and budget after verifying spending controls.

Possible support:
- Independent technical review and threat-model feedback.
- Benchmark and tokenizer expertise.
- Retrieval evaluation and adversarial test design.
- A small, explicitly bounded evaluation-credit allocation after the zero-cost stage is reviewed.

No unrestricted API access or unrestricted spending is requested.

## Milestones

- **M1 — Reproducibility:** clean offline run and automated regression tests.
- **M2 — Measurement quality:** real tokenizer accounting, all overhead included, task-level correctness and retrieval misses.
- **M3 — Adversarial evaluation:** negation, dates, quantities, identifiers, contradictory context, paraphrases, and cases where hydration is necessary.
- **M4 — Controlled model study:** only with separate authorization and verified spending controls; compare all three configurations on a frozen task set.
- **M5 — Decision:** publish measured trade-offs and decide whether the approach merits further integration.

## Current limitations and non-claims

- Synthetic performance is not real-model accuracy.
- Exact text reconstruction does not prove semantic equivalence.
- Token savings vary with tokenizer, corpus, model, and prompt overhead.
- Lexical or heuristic retrieval can miss relevant information.
- Projection figures are not measured large-scale outcomes.
- The prototype is not represented as a production service or a guarantee of correctness.

## Contact and review

Open a GitHub issue with a technical question or proposed evaluation. Please do not post API keys, private data, or confidential benchmark material in public issues.
