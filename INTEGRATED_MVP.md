# Integrated CSC LCH Prototype (v0.1)

## Purpose

This is a single offline prototype that joins four CSC LCH ideas in one pipeline:

1. conservative sentence-level units and exact source provenance;
2. duplicate removal;
3. task-query prioritization under a caller-supplied budget;
4. lazy retrieval of deferred source spans, with a source-integrity hash.

It is deliberately a baseline, not a claim that full semantic compression has been solved.

## Files

- `csc_lch_integrated.py` — compression, archive references, hydration, and accounting audit.
- `test_csc_lch_integrated.py` — standard-library unit tests.

## Run

No API key, paid model call, or third-party package is required.

```bash
python csc_lch_integrated.py context.txt --query "Which version was rejected?" --budget 256 --hydrate
python -m unittest -v test_csc_lch_integrated.py
```

The default token counter is a rough lexical estimate. For meaningful token budgets, call `compress(..., token_counter=your_model_tokenizer)` and use the tokenizer for the target model. The budget applies to the encoded prompt payload, including its IDs and provenance labels. If metadata alone or a single unit cannot fit, the system may defer that unit; inspect the output and audit.

## Data flow

```text
source text
  -> sentence units + source hash
  -> exact duplicate removal
  -> task relevance + pinned constraint ranking
  -> encoded payload under budget
  -> deferred source references
  -> query-triggered hydration
  -> integrity/accounting audit
```

The source archive is separate from `prompt_payload`. In deployment, keep it in a retrievable store or tool rather than injecting the full archive into the model prompt. Measure storage, lookup, and hydration costs too.

## Safety and honesty properties

- Source spans are retained verbatim in the archive.
- The hash check rejects a missing or modified archive.
- Negation, conditions, requirements, and numbers are prioritized heuristically, not guaranteed to be retained.
- `OBS` means “verbatim in the supplied source,” not “externally verified true.”
- Audit explicitly reports semantic preservation and token savings as **not verified**.
- Hydration is keyword-based and may miss paraphrases or return irrelevant candidates.
- Sentence splitting can fail on abbreviations, lists, tables, code, and unusual punctuation.
- This version does not build a real semantic/mechanism graph and does not infer missing facts.

## Required next experiment

Use the same held-out contexts and questions to compare:

1. original context;
2. ordinary summary;
3. this structured baseline without hydration;
4. this structured baseline with hydration.

Use the same model/tokenizer and score all input tokens, metadata, retrieval queries, retrieved passages, retries, answer accuracy, and relationship/constraint preservation. Do not call a result a win unless accuracy is comparable and total tokens are lower. Keep a zero-cost offline test suite separate from any optional live model evaluation.
