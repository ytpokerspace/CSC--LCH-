# LongBench v2 dataset audit and lexical baseline

This is a reproducible, zero-paid-API Colab workflow. It downloads the public LongBench v2 dataset, audits all records, and runs a deterministic lexical context-preparation baseline. It does not call a language model or generate answers.

## Colab run

Open a new Google Colab notebook and run these cells:

\`\`\`python
!git clone --branch feat/accuracy-qbs-evaluation https://github.com/ytpokerspace/CSC--LCH-.git
%cd CSC--LCH-
!pip -q install tiktoken
!python benchmarks/longbench_v2_audit.py --download
\`\`\`

The dataset download is approximately 160 MB. The script uses the official LongBench v2 JSON source and cl100k_base through the local tiktoken package. Installing tiktoken is a local package install, not a paid API call.

## Outputs

- artifacts/longbench_v2_audit/dataset_audit.json: all-row schema, ID, answer-label, category, and context-size audit.
- artifacts/longbench_v2_audit/baseline_summary.json: all-row token totals and retrieval diagnostics, plus the deterministic 10-example sample details.

The default settings match the documented prior experiment parameters: seed 2026, 10-example sample, top 5 chunks, 3,000-character chunks, 300-character overlap, and cl100k_base.

## Important reproduction note

The earlier summary artifact documented those settings but the exact earlier retrieval implementation was not present in the repository. This script therefore makes the lexical scoring rule explicit and versioned rather than claiming bit-for-bit reproduction. It ranks chunks by the number of distinct non-stopword question terms present, breaks ties by earlier source position, and restores selected chunks to source order.

The query-term coverage metric is only a lexical proxy. It does not measure evidence recall or answer accuracy. The dataset's official answer labels are audited and retained, but scoring still requires predictions from two policies on identical questions.

## Safety against misleading results

- The complete original context remains untouched in the downloaded dataset.
- The script does not overwrite source data.
- No model inference, API key, or paid service is used.
- A schema/integrity failure stops the baseline instead of silently producing a misleading report.
- Token reduction is context-preparation efficiency, not proof of storage savings or better answers.
- Do not tune against the final held-out evaluation set.
