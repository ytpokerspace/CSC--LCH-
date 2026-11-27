# QBS-inspired candidate search

`benchmarks/qbs_candidate_search.py` ranks **already measured** retrieval configurations and proposes bounded coordinate neighbors for the next experiment. It is classical deterministic search, not a quantum algorithm.

## Candidate input

JSONL fields:
- `candidate_id`: unique name.
- `controls`: exactly six normalized values in [0,1]: `compression`, `retrieval_relevance`, `hydration_priority`, `evidence_confidence`, `exploration`, `validation_strictness`.
- `answer_accuracy`, `evidence_recall`, `factual_precision`, `efficiency`: measured values in [0,1]. Efficiency should be a consistently normalized measure such as token reduction.
- `critical_facts_pass`: independently verified boolean hard gate.

## Objective and search

`utility = 0.50*answer_accuracy + 0.20*evidence_recall + 0.15*factual_precision + 0.15*efficiency`

Candidates failing the critical-fact gate or optional minimum-accuracy floor are ineligible, regardless of utility. The winner generates up to 12 proposals: one positive and one negative bounded step for each control. Proposals are explicitly marked unevaluated; run the actual retriever and score its answers before feeding results back into the next round.

Run:

```bash
python benchmarks/qbs_candidate_search.py path/to/candidates.jsonl --step 0.1 --min-accuracy 0.9
```

Use a tuning split to select settings and a separate held-out split for final reporting. Do not optimize on the held-out set. The included fixture is synthetic and only tests the implementation. The current repository has no adapter exposing these six controls to the live retrieval engine; this tool proposes experiments but does not itself execute retrieval.
