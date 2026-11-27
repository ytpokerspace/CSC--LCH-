# LongBench v2 context-preparation experiment

This directory adds a reproducible context-preparation experiment to CSC-LCH. The
workflow downloads the public LongBench v2 dataset, selects a fixed-seed sample, and
compares full-context token counts with a deterministic lexical top-k chunk selector.

## Important scope boundary

This first implementation is NOT a full CSC-LCH integration and is NOT an answer-
accuracy benchmark. It measures context selection only. The original source context is
kept intact in process memory, so the experiment does not claim archive-storage savings.
The query-term coverage metric is only a diagnostic proxy; it is not evidence recall and
must not be reported as answer accuracy.

No LLM endpoint, API key, or paid inference call is used. Token counts use the fixed
tiktoken cl100k_base encoding as a reference. Model-specific evaluations must use the
actual model tokenizer and an explicit inference adapter in a later, separately approved
phase.

## Run locally

    python -m pip install -r benchmarks/longbench_v2/requirements.txt
    python -m unittest discover -s benchmarks/longbench_v2/tests -v
    python benchmarks/longbench_v2/evaluate.py --limit 10

Use --limit 503 for all records. The default sample is 10 records selected with seed
2026. Results are written to research-results/longbench-v2/ as JSON and CSV.

## GitHub Actions

Run "LongBench v2 context experiment" manually from the Actions tab. Select 10, 50, or
503 examples. The workflow uploads summary and per-example metrics as an artifact.
It does not commit results, publish a leaderboard entry, or alter the default branch.

## Metrics

- Full-context and selected-context token counts.
- Context token reduction fraction.
- Number of chunks selected / available.
- Query-term coverage proxy.
- Dataset ID, domain, difficulty, and length metadata.

## Next research gate

Before claiming that CSC-LCH preserves answer quality, integrate the real CSC-LCH
compression/hydration implementation and a separately approved inference backend. Compare
full context, a standard retrieval control, and CSC-LCH under the same model, tokenizer,
prompt, and compute budget. Report accuracy and cost together, including failed examples.

## Dataset and citation

LongBench v2 is a 503-question multiple-choice benchmark. Dataset fields include
_id, domain, sub_domain, difficulty, length, question, four choices, answer, and context.

Dataset: https://huggingface.co/datasets/THUDM/LongBench-v2
Project: https://github.com/THUDM/LongBench
Paper: https://arxiv.org/abs/2412.15204

Respect the dataset's license and terms when using or redistributing its contents.
