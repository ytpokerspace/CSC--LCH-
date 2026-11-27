# LongBench v2 — context-selection baseline audit

**Author:** William Gunnell Cox  
**Experiment:** full context vs lexical top-k context preparation  
**Status:** retrospective audit of the supplied run; no model inference

## Baseline comparison (10 evaluated examples)

| Measure | Full-context baseline | Lexical top-5 | Interpretation |
|---|---:|---:|---|
| Context tokens | 1,499,387 | 37,453 | Retrieved prompt is 2.50% of full context |
| Token reduction | 0% | **97.5021%** | Preparation-stage reduction only |
| Query-term coverage proxy | Not applicable | **77.9664%** | About 22.03% of query terms are absent from selected chunks on average |
| Evidence recall | Not measured | Not measured | No evidence annotations were scored |
| Answer accuracy | Not measured | Not measured | No model was called |

The full-context baseline retains all source text, so its source-retention ceiling is 100%. The lexical top-5 condition selects five chunks per example using lexical query overlap. The reported query-term coverage is a diagnostic proxy, **not evidence recall and not answer accuracy**.

## What the current run establishes

- This specific lexical selection procedure reduced prepared context tokens by 97.5021% across 10 evaluated examples.
- It achieved a mean query-term coverage proxy of 0.779664.
- It does **not** establish answer correctness, evidence preservation, or that the full CSC-LCH tiering/hydration pipeline outperforms a baseline.
- Only 10 of 503 available rows were evaluated (1.99%): a small pilot, not a representative benchmark.
- The source run says original context remains in memory. This is prompt-selection reduction, not archive/storage savings.

## Next reproducible comparison

Run longbench_context_baseline.py on the same fixed JSONL examples for:
1. Full context (reference condition).
2. Lexical top-5 (current control).
3. CSC-LCH selection with the same chunking, token counter, and examples.

Input is one JSON object per line with id, context, query (or question), and optional evidence (string or list of exact evidence spans). The script reports token counts, query-term coverage, and evidence-span recall when annotations are supplied. It deliberately does not infer answer accuracy.

For a valid quality comparison, use a fixed QA set and run the same model, prompt, decoding settings, and questions against each condition. Score answer accuracy separately from retrieval metrics. Include all 503 rows or a pre-registered sample, not a post-selected ten.

## Provenance

Values are copied from the supplied summary.json: 503 rows available; 10 evaluated; seed 2026; top-k 5; chunk size 3,000 characters; overlap 300 characters; tokenizer label cl100k_base; full tokens 1,499,387; retrieved tokens 37,453; reduction 0.975021; query-term coverage proxy 0.779664; answer accuracy null; no model inference or paid API calls.

No raw contexts, per-example rankings, evidence labels, or QA outputs were included. This audit does not fabricate them.
