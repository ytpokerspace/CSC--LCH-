# CSC-LCH Oracle and Source-Integrity Audit

**Status:** Offline CI passed  
**Workflow run:** [46104307846](https://github.com/ytpokerspace/CSC--LCH-/actions/runs/46104307846)  
**Branch:** `research/oracle-boundary-audit-2026-11`  
**Evaluated corpus:** 3 repository documents, 61 semantic paragraphs, 15 fixed evidence questions

## What changed

1. Replaced answer-aware exact-substring selection with a deterministic BM25 lexical retriever.
2. Retrieval receives only the natural-language query and deferred paragraphs. Expected evidence is consulted only after candidate selection to score recovery.
3. Added an immutable, byte-preserving source archive. It splits files at blank-line boundaries while retaining every byte, hashes each chunk, reassembles chunks in order, and checks the reconstructed whole-file SHA-256.
4. Added regression tests for answer-key separation, BM25 ranking, archive round trips, missing chunks, and corrupted chunks.

## Offline results

| Policy | Evidence recovered | Hydration candidates | Stubs | Lexical-unit reduction |
|---|---:|---:|---:|---:|
| T3 | 15/15 | 6 | 40 | 28.900% |
| T4 | 15/15 | 5 | 6 | 6.205% |
| T5 | 15/15 | 2 | 3 | 2.107% |

All three policies had zero paragraph-integrity failures.

The baseline was 43,515 lexical units across the 15 repeated full-context tasks. Policy totals include active context, registry instructions, estimated hydration prompt units, retrieved text, and fixed output units. These are **lexical proxies**, not model-token counts.

## Byte-exact archive results

| Source | Chunks | Bytes | SHA-256 round trip |
|---|---:|---:|---|
| `README.md` | 77 | 6,615 | PASS |
| `benchmarks/milestone6_report.md` | 51 | 5,019 | PASS |
| `ARAF/README.md` | 51 | 3,548 | PASS |

All 3 files reconstructed byte-for-byte with zero source reconstruction failures.

## Interpretation

The BM25 test removes the previous Oracle's direct access to expected answers during candidate selection. It is a meaningful improvement in test independence, but it is still a small, hand-authored, in-domain lexical retrieval benchmark. A 15/15 result is not proof of general retrieval quality or semantic answer accuracy.

The source archive proves exact reconstruction for the three frozen files in this experiment. It is a separate cold-storage layer; the compressed and tiered active representation is not itself a byte-exact copy of the original files.

## Remaining work

- Replace curated section-name tier assignment with an independently evaluated tier classifier.
- Expand the query set with unseen, ambiguous, paraphrased, and multi-source questions.
- Compare BM25 with a second retrieval baseline and include explicit no-hit / wrong-hit cases.
- Integrate source-archive retrieval into the actual hydration interface, not only the validation harness.
- Measure real tokenizer usage, end-to-end latency, and answer quality before making production efficiency claims.

No paid APIs or external model calls were used. This audit does not establish production readiness.
