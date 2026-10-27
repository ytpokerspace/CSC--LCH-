# CSC LCH — Milestone 6 Ablation and Milestone 6.1 Validation

## Scope and evidence status

This document records the supplied Milestone 6 aggregate results and defines the next reproducible validation step. The aggregate results below are **reported study results supplied by the project author**; raw per-question traces were not provided with the summary, so they are not independently reproduced by this repository change.

## Reported ablation results

The study changed only `max_defer_tier`, the tier threshold governing which content may be deferred from the active prompt.

| Policy | Meaning | Active tokens | Tokens saved | Ratio | Quality | Hydration calls | Stubs |
|---|---|---:|---:|---:|---:|---:|---:|
| T3 | Defer T3 and below | 197 | 79 | 1.40× | 1.00 | 12 | 9 |
| T4 | Defer T4–T5 | 238 | 38 | 1.16× | 1.00 | 4 | 4 |
| T5 | Defer T5 only | 254 | 22 | 1.09× | 1.00 | 3 | 2 |

These numbers imply a shared baseline of 276 active tokens (active tokens + tokens saved). Relative to that implied baseline, active-prompt reductions are 28.6% for T3, 13.8% for T4, and 8.0% for T5.

### Interpretation

- T3 saves the most active-prompt tokens but had the most hydration calls in this seven-question study.
- T4 is a reasonable provisional balance between active-prompt reduction and observed retrieval frequency.
- T5 is the most conservative of the three policies in terms of deferral.
- The reported quality score was 1.00 for every policy. This supports successful answers on the tested questions under the study's scoring rubric; it does not establish universal semantic fidelity or production readiness.
- Moving T5 → T4 saves 16 additional active tokens; moving T4 → T3 saves another 41.
- Hydration-call counts alone do not establish latency or cost. Calls may differ in payload size, latency, and overlap.

## How CSC LCH works

1. Preserve original source content and provenance; integrity hashes can detect accidental changes.
2. Represent content and relationships in a semantic graph and assign content to tiers.
3. Keep high-priority context active. For eligible lower-priority content, place a provenance-preserving stub in the active context.
4. When a query requires deferred information, resolve the stub and retrieve the original source content.
5. Measure both the initial prompt and the full retrieval-assisted request. Validate answers and source reconstruction against a non-deferred baseline.

The source remains the authority. A stub is a pointer to content, not a substitute for the original source record.

## Milestone 6.1: total-cost and retrieval-latency validation

Record one row per question and policy. The benchmark harness in `scripts/m6_benchmark.py` accepts JSON Lines observations and emits machine-readable JSON and CSV summaries.

Required per-question fields:

- `policy`, `question_id`
- `baseline_prompt_tokens`, `active_prompt_tokens`
- `hydration_calls`, `hydration_prompt_tokens`, `retrieved_tokens`
- `output_tokens`, `latency_ms`
- `quality_score`
- `material_facts_expected`, `material_facts_recovered`
- `reconstruction_ok`

Token accounting convention for this harness:

`total_tokens = active_prompt_tokens + hydration_prompt_tokens + retrieved_tokens + output_tokens`

This is an explicit accounting convention for benchmark records. Avoid double-counting retrieved content if your instrumentation already includes it in another field; adapt the adapter/schema to the provider's actual usage semantics and document that choice. If the system sends a new full prompt after hydration, record the tokens actually sent, not just the delta, and use a consistent definition across policies.

### Recommended report metrics

- Active-context reduction relative to baseline.
- Total observed tokens, including retrieval and output.
- Hydration calls and stubs resolved.
- Median and p95 end-to-end latency (once enough repeated observations exist).
- Mean quality score, material-fact recall, and reconstruction failures.
- Per-question traces so a failed answer can be diagnosed.

### Reproducibility checklist

- Use the same frozen corpus and question set for each policy.
- Keep the uncompressed baseline in the comparison.
- Record commit SHA, configuration, corpus hash, question-set hash, and scoring rubric.
- Run offline/mock tests in CI. Do not make paid API calls in the default workflow.
- Treat missing values as missing; do not silently interpret them as zero.
- Test missing-source, ambiguous-query, multi-tier, Unicode, and retrieval-failure cases.

## Provisional policy guidance

- **T4:** provisional default pending full-cost measurements.
- **T3:** consider when context pressure is high and retrieval overhead is demonstrably acceptable.
- **T5:** conservative mode when fewer retrieval dependencies are preferred.

These are engineering hypotheses based on the reported small study, not a proven globally optimal policy. Choose the operating point using measured total tokens, latency, quality, and workload characteristics.
