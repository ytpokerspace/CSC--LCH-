# CSC-LCH
## Cascading Semantic Compression + Lazy Context Hydration

**Creator and author: William Gunnell Cox**  
**Project:** CSC-LCH — original cascading semantic compression and lazy context hydration framework  
**Status:** Public research prototype; benchmark claims must be independently reproduced.

CSC-LCH is a context-management approach for large language model (LLM) workflows. It aims to reduce repeated or low-priority context in the active prompt while preserving essential meaning and retrieving deferred information when it becomes relevant.

The central idea is **compress what can safely be summarized, keep critical semantics explicit, and lazily hydrate supporting context only when needed**.

## Original design

The framework combines two mechanisms:

1. **Cascading Semantic Compression** — organize context by importance and compress redundant wording progressively, rather than treating every token as equally valuable.
2. **Lazy Context Hydration** — retain references to supporting or archived material and retrieve the original details only when a question or decision requires them.

### Context tiers

The initial design uses tiers to express how aggressively information may be compressed or deferred:

| Tier | Role | Handling principle |
|---|---|---|
| T0 | Immutable anchors | Never compress away or defer critical constraints, safety requirements, or required output formats. |
| T1 | Core semantics | Preserve the goal, essential facts, and success criteria explicitly. |
| T2 | Active context | Keep current state, dependencies, and active decisions available while relevant. |
| T3 | Supporting context | Retain useful explanations and supporting detail; summarize carefully. |
| T4 | Distant context | Defer details that are not currently needed, while preserving a retrieval path. |
| T5 | Archive | Keep older or low-relevance source material retrievable rather than silently discarding it. |

Tier labels are a context-management convention, not a claim that a model internally stores information in these exact layers.

### Evidence markers

- `OBS` — observed or explicitly supplied information.
- `INF` — inference supported by available evidence.
- `SPEC` — speculation or an unverified hypothesis.

Do not silently promote inference or speculation to observed fact. Preserve source provenance when details may affect an answer.

## Repository contents

- [`csc_lch_chatbot_instructions.yaml`](csc_lch_chatbot_instructions.yaml) — YAML prompt-layer specification.
- [`csc_lch_bench.py`](csc_lch_bench.py) — benchmark harness for token counting, compression stages, projections, and optional quality checks.
- [`csc_lch_bench.yaml`](csc_lch_bench.yaml) — YAML-packaged benchmark source.
- [`benchmarks/milestone6_report.md`](benchmarks/milestone6_report.md) — reported T3/T4/T5 ablation results and the Milestone 6.1 total-cost validation protocol (reported aggregates are not independently reproduced yet).
- [`LICENSE`](LICENSE) — GNU GPL v3.0 or later (GPL-3.0-or-later).

## Reproduce carefully

The benchmark supports a dry-run mode for offline logic checks:

```bash
python3 csc_lch_bench.py --dry-run
```

For token-counting or quality experiments, read the script's help and inspect its options first. Provider-backed quality tests may make network requests and can incur charges depending on the selected service and current terms. **No paid API calls are required to review the concept or run the offline dry run.** Do not run live tests unless you deliberately authorize them and understand the costs.

Use your own representative corpus for meaningful evaluation. Synthetic examples cannot establish real-world savings for your workload.

## Evaluation standard

Compare original context and compressed-plus-hydrated context on the same tasks. Report:

- actual input and output token counts from the named tokenizer or provider counting endpoint;
- compression, decoding, and hydration overhead;
- answer correctness and material-fact preservation;
- latency and number of retrieval/hydration calls;
- the test corpus, model/service, configuration, and date;
- failed cases and limitations, not just successful examples.

Projected savings are not measured savings. Token reduction alone is not success if answer quality or essential information degrades.

## Research status and limitations

CSC-LCH is a prompt/context-layer research approach. This repository does not establish that every LLM or workload will benefit, nor does it demonstrate a change inside a model's internal serving stack. Results depend on the context, tokenizer, model, retrieval strategy, and evaluation design.

Treat performance numbers as established only when the corresponding experiment has been run and its method and evidence are available.

## Attribution

CSC-LCH and the original framework concept documented here are attributed to **William Gunnell Cox**. If you build on this work, retain this attribution and cite this repository. Attribution does not imply that every subsequent contribution, implementation, or independent idea belongs to the original author.

## License

This repository is licensed under the GNU General Public License v3.0 or later (GPL-3.0-or-later). See [LICENSE](LICENSE).
