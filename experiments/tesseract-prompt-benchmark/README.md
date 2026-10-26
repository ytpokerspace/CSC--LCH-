# Tesseract Prompt Efficiency Benchmark

Experimental prompt-only configuration package for testing structured semantic context management and CSC-LCH-style lazy context hydration.

## Status

**Experimental.** This repository contains configuration rules and a deterministic synthetic harness. It does not yet demonstrate improved performance on a live language model.

## Contents

- `configs/`: six YAML specifications covering the dimensional analogy, human-safe behavior, semantic context, metrics, hardware boundaries, and experiment protocol.
- `validate_and_benchmark.py`: parses YAML, checks cross-file safety/measurement requirements, and runs five deterministic fixture tests.
- `validation_report.json`: sample report from the synthetic harness.

## Run locally

Python 3.10+ is recommended.

```bash
python -m pip install -r requirements.txt
python validate_and_benchmark.py
```

Run the command from this directory. The script writes `validation_report.json`.

## Interpretation

A passing result means the YAML parsed and the synthetic test fixtures passed. It is **not** an LLM benchmark. Word counts are not tokenizer token counts; fixture timing is not model latency; no GPU, memory, or energy telemetry is collected.

To evaluate actual efficiency, compare baseline and candidate prompts on identical held-out tasks with the same model/version/settings. Record tokenizer counts, latency, task correctness, and available hardware telemetry. Reject efficiency gains that breach preregistered quality or safety thresholds.

## Safety and limits

YAML is declarative configuration, not an enforcement mechanism. Model compliance, automatic retrieval, and hardware measurement require an appropriate runtime or application integration. Do not put secrets or personal data in benchmark fixtures.

## License

MIT. See `LICENSE`.
