# ARAF — AI Research Acceleration Framework

ARAF is an experimental, evidence-first workflow for turning research ideas into falsifiable hypotheses, testable study plans, risk reviews, and structured reports.

> **Status:** Prototype / research preview. ARAF does not autonomously establish novelty or guarantee scientific validity. Its scores are heuristic and must be justified.

## Goals

- Turn a research problem into measurable objectives.
- Represent hypotheses with predictions and rejection criteria.
- Check experiment plans for baselines, controls, metrics, and reproducibility details.
- Flag assumptions and likely failure modes.
- Keep measured results separate from hypotheses and literature-supported claims.
- Run the core validation checks without paid APIs or network access.

## Scope

The first prototype focuses on structured research planning and validation. It does **not** automatically perform literature searches, run scientific experiments, or verify novelty. Those are future integrations that must cite their sources and preserve an auditable evidence trail.

## Quick start

Requires Python 3.10 or newer.

```bash
python -m unittest discover -s tests -v
python -m araf.cli examples/llm_context_efficiency.json
```

No API key, paid service, or network access is required for these checks.

## Project layout

- `src/araf/core.py` — research-plan data structures and validation.
- `src/araf/cli.py` — local JSON-in / JSON-out command-line interface.
- `tests/` — offline unit tests.
- `examples/llm_context_efficiency.json` — sample research brief.

## Evidence labels

Use one of these labels for every substantive claim:

- `measured` — directly produced by a recorded experiment.
- `literature_supported` — supported by a cited source.
- `hypothesized` — a prediction awaiting testing.
- `unverified` — not yet independently checked.
- `contradicted` — evidence conflicts with the claim.

Do not label a proposed outcome as measured. Record the dataset, version, procedure, metrics, and raw-result location for experimental claims.

## Design principles

1. **Falsifiability:** each hypothesis states a prediction and a criterion that could reject it.
2. **Baselines:** improvement claims require a meaningful comparison.
3. **Reproducibility:** record data, configuration, procedure, and software version.
4. **Honest uncertainty:** heuristic scores are not probabilities or proof.
5. **Budget discipline:** the core prototype is offline and has no paid API dependency.
6. **Human review:** researchers remain responsible for source quality, study ethics, and interpretation.

## License

This project is offered under either the MIT License or Apache License 2.0. See `LICENSE-MIT` and `LICENSE-APACHE`.

## Roadmap

- [x] Structured research brief schema
- [x] Offline plan validation
- [x] JSON command-line interface
- [x] Synthetic example and unit tests
- [ ] Literature search with source citations
- [ ] Experiment runner and immutable result records
- [ ] Statistical analysis helpers
- [ ] Replication audit report
- [ ] Optional model adapters (disabled by default; no paid calls without explicit configuration)

## Contributing

Contributions should include tests and distinguish observed results from assumptions. Do not submit credentials, private datasets, or sensitive research data.
