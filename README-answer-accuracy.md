# Paired answer-accuracy evaluation

This addition scores predictions already produced by two or more systems on the same questions. It makes no model calls and needs no API key.

## Input

One JSON object per line:

```json
{"question_id":"q1","policy":"full","prediction":"Paris","gold_answers":["Paris","the city of Paris"]}
{"question_id":"q1","policy":"compressed","prediction":"Paris","gold_answers":["Paris","the city of Paris"]}
```

Every policy must have exactly the same question IDs. Gold answers must be verified independently. Include multiple accepted aliases when appropriate. Do not use synthetic examples as real benchmark evidence.

## Run

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python benchmarks/answer_accuracy.py path/to/answers.jsonl
```

The report includes normalized exact-match accuracy and mean token F1 per policy, plus per-question scores. Exact match is the primary strict metric; token F1 is diagnostic and can reward partial lexical overlap without proving semantic correctness.

## QBS integration boundary

This is stage 1 of the QBS-inspired accuracy-tuning workflow: create a trustworthy paired quality signal before tuning. The existing repository does not expose the six proposed retrieval controls as runtime parameters, so this change deliberately does not pretend to tune compression, relevance, hydration, evidence, exploration, or validation weights yet. Stage 2 must connect those controls to the actual retriever, evaluate candidate settings on a tuning split, and report results on a separate held-out split. Critical-fact preservation remains a hard gate; token savings cannot compensate for lost required facts.

The search strategy is classical and deterministic. "QBS/Grover-inspired" describes candidate exploration only; no quantum computation is performed.
