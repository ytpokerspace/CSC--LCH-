# CSC-LCH lossless text mode

## Purpose

`csc_lch_lossless.py` is a small, deterministic, reversible UTF-8 codec. It exists as a correctness baseline: the original text can be recovered byte-for-byte after JSON-safe storage or transport, and corruption is detected before text is returned.

This is **not** semantic compression and does **not** claim to reduce LLM tokens. The compressed zlib payload is Base64-encoded so it can be carried in JSON; Base64 adds overhead. Whether the resulting packet is smaller depends on the source text.

## Example

```python
from csc_lch_lossless import encode_text, decode_text, packet_json_size

source = "Do not change 0.5 kg to 5 kg. 🧠\n"
packet = encode_text(source)
restored = decode_text(packet)

assert restored == source
print("source bytes:", len(source.encode("utf-8")))
print("packet JSON bytes:", packet_json_size(packet))
```

The packet contains:
- codec/version identifier;
- UTF-8 encoding label;
- original byte length;
- SHA-256 checksum of the original UTF-8 bytes;
- zlib-compressed payload encoded as Base64.

The decoder rejects unsupported versions, malformed Base64/zlib, truncation, trailing compressed data, oversized output, length mismatch, checksum mismatch, and invalid UTF-8. The default decompressed-output limit is 64 MiB; callers can lower it for their environment.

## Verification

Run the complete offline suite:

```sh
python -m unittest discover -s tests -v
```

Tests cover exact round-trip behavior for whitespace, line endings, Unicode/emoji, negations, dates, identifiers, and numerical units, as well as deterministic output and corrupted packet rejection.

## What this does and does not prove

- **Proven by the codec tests:** exact local recovery for tested cases and detection of tested corruption cases.
- **Not proven:** that a semantic rewrite preserves every meaning, that compressed prompts use fewer model tokens, or that a model answers equally well from a compressed prompt.
- **Separate experiment:** `csc_lch_cross_provider_bench.py` compares original context with the existing semantic `compress_text` transformation. Its mock mode tests plumbing only. Use real provider-reported usage and a quality test before making savings or accuracy claims.
