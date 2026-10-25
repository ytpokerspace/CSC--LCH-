# CSC-LCH
**Cascading Semantic Compression + Lazy Context Hydration**

CSC-LCH is a research prototype for reducing repeated or unnecessary context while preserving the information required to answer correctly. It combines conservative deduplication/compression with tiered context and retrieval of deferred details when they matter.

**Status:** research prototype; not a production guarantee. The project has not established a general real-model accuracy improvement or universal token savings. Results depend on the input corpus, tokenizer, prompt overhead, retrieval quality, and task.

## Start here

The main harness is `csc_lch_bench.py`. It can run an offline logic smoke test without an API key or model generation:

```bash
python3 csc_lch_bench.py --dry-run --scale 1 --out benchmark-results/csc-lch-dry-run
```

This creates a text report and JSON report. In `--dry-run` mode, token figures are **estimates, not real tokenizer counts**. The default output path's parent directory must exist; create it first with `mkdir -p benchmark-results` on macOS/Linux or `New-Item -ItemType Directory -Force benchmark-results` in PowerShell.

Run the offline regression tests:

```bash
python3 -m unittest discover -s tests -v
```

No third-party Python packages are required for the benchmark harness and its offline tests.

## Local tokenizer audit (no model calls)

The optional tokenizer audit uses the public `tiktoken` package with its `o200k_base` encoding, associated with the GPT-4o model family. It counts the concatenated prompt text, including the CSC-LCH legend and hydration tool schema where applicable:

```bash
python3 -m pip install tiktoken
python3 benchmarks/tokenizer_audit.py --scale 1 --out benchmark-results/tokenizer-audit
```

This does not call a provider API or generate model output. The counts are exact for the text passed to that local encoding, but they are **not provider-reported request counts or billed usage**: chat framing and provider-specific tool accounting can differ. The bundled corpus is synthetic, and this audit does not measure answer quality or prove semantic equivalence. CI runs this audit separately from the standard-library-only offline tests.

### Latest measured local tokenizer audit

GitHub Actions run [#40189573422](https://github.com/ytpokerspace/CSC--LCH-/actions/runs/40189573422) completed successfully on 2026-10-25. On the 17-question synthetic corpus (seed 7, scale 1), the local `o200k_base` audit reported these mean input-payload counts:

| Condition | Mean tokens per question | Difference vs full context |
|---|---:|---:|
| Full context | 4,225.65 | Baseline |
| Literal glyph layer + deferral | 4,086.65 | 3.29% fewer |
| No glyph layer + deferral | 4,040.65 | 4.38% fewer |
| Token-aware glyph layer + deferral | 4,086.65 | 3.29% fewer |

These are measured tokenizer counts for the exact concatenated text payload used by this script, including the system instructions, context, question, and applicable registry/tool-schema overhead. They are **not provider-reported API usage**. The script represents hydration by including the tool schema; it does not simulate actual hydration calls or count any later retrieved content. The test is synthetic and does not measure answer correctness or semantic equivalence. In this run, the no-glyph variant had the lowest measured prompt-payload count; emoji substitution did not improve on that variant.

## Using your own context

Prepare a UTF-8 plain-text file with context segments separated by blank lines. Optional tags `[T0]` through `[T5]` at the start of a segment let you specify tiers. Supply a separate JSON QA file if you want the optional quality test to score task-specific required/forbidden patterns.

For an API-backed token-count run, provide an Anthropic API key through the environment and verify the provider's current pricing, terms, and rate limits before running. The token-count endpoint does not generate an answer, but availability and pricing may change. **Do not use `--quality` for the zero-cost workflow:** it performs live model calls and may incur charges. The harness asks for confirmation before paid quality calls unless `--yes` is passed; never pass `--yes` unless you have explicitly approved the run and budget.

Example commands for later, separately authorized work:

```bash
export ANTHROPIC_API_KEY="..."  # keep secrets out of source control
python3 csc_lch_bench.py --corpus context.txt --tiering tags --out results/context
```

To run the optional live quality evaluation, prepare a task-specific QA JSON file and review the task count, model, maximum output tokens, provider-side spending controls, and budget first. The offline CI does not execute this path.

## How to interpret results

- **Token counts:** distinguish offline estimates from provider-reported counts; include legends, instructions, retrieval tools, and hydrated context in comparisons.
- **Correctness:** exact reconstruction of a text representation is not the same as semantic equivalence or model-answer correctness.
- **Retrieval:** report missed facts and unnecessary hydrations, not just average savings.
- **Performance:** report latency and model-call count alongside tokens and quality.
- **Synthetic results:** validate harness behavior only; they do not establish real-world performance.
- **Projections:** arithmetic extrapolations are hypotheses, not measurements at scale.

Always compare the original context, compressed context without hydration, and compressed context with hydration on the same tasks and scoring rules. Retain per-task failures. Prefer a fallback to original context whenever the system cannot preserve constraints with confidence.

## Architecture at a glance

1. Protect critical instructions, constraints, quantities, negations, provenance, and uncertainty.
2. Remove only verified redundancy and apply conservative compression.
3. Keep references to deferred context rather than silently discarding it.
4. Retrieve the smallest relevant original details when the task or verifier requires them.
5. Check the result against explicit criteria and preserve an uncompressed fallback.

The YAML instruction set is a prompt-layer specification; it is not itself a standalone executable optimizer. The Python harness is the executable benchmark implementation.

## Contributing and sponsorship

The project welcomes reproducibility reviews, independent benchmark design, tokenizer and retrieval analysis, test cases, and technical mentorship. See [SPONSOR_BRIEF.md](SPONSOR_BRIEF.md) for the current research question, evidence boundaries, and proposed next steps.

## License

See [LICENSE](LICENSE). This is a research prototype; review the license and any dependencies before incorporating it into a commercial product.
