# CSC-LCH Paired Benchmark Add-on

This offline benchmark corrects the baseline-accounting mismatch by comparing paired observations for the same tasks.

## Run
```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/paired_benchmark.py tests/fixtures/paired_sample.jsonl
```

No network, model calls, API keys, or paid services are used.

**Important:** the included fixture is synthetic demonstration data, not measured LLM performance. Replace it with paired observations from identical tasks before making claims. Both baseline and policy totals include prompt/input, hydration prompt, retrieved context, and output. Keep categories mutually exclusive and use the same tokenizer/model and output requirements. Reports include token reduction, latency, material-fact recall, quality scores, and reconstruction failures.
