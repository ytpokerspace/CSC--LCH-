# CSC-LCH provider adapters

## What this adds

`csc_lch_providers.py` defines a small, vendor-neutral interface so CSC-LCH
can eventually connect to different model APIs without putting provider-specific
assumptions into its core logic. It has no third-party dependencies and makes
no network requests.

- `ProviderAdapter.generate(...)` is the normalized generation contract.
- `ProviderAdapter.count_tokens(...)` returns a provider-accurate count when
  implemented, otherwise `None`.
- `ProviderResponse` normalizes text, provider/model identity, usage, and
  optional metadata.
- `TokenUsage.source` records where metrics came from.
- `MockProvider` gives deterministic offline behavior for integration tests.
- `estimate_tokens_by_characters` is only a rough estimate; it must not be
  reported as a tokenizer/API measurement.

## Run the tests

With Python 3.8+:

```sh
python -m unittest discover -s tests -v
```

No API key or internet connection is required.

## Adding a real provider

Create a subclass of `ProviderAdapter` for each provider. The implementation
should:
1. Read credentials from environment variables or a secret manager, never from
   committed source code.
2. Use that provider's documented endpoint and model identifiers.
3. Preserve provider-reported usage separately from local estimates.
4. Return a `ProviderResponse` with the actual provider and model names.
5. Raise clear errors for authentication, rate limits, timeouts, and malformed
   responses; do not silently fall back to mock results.
6. Include tests using mocked HTTP responses, including error cases.

## Scope and limitations

This is the adapter contract and offline test foundation, not a completed live
integration with OpenAI, Anthropic, or a local model runtime. The existing
benchmark has not been rewired in this change. That is deliberate: provider
selection, token accounting, pricing, and quality evaluation should be changed
in a follow-up with provider-specific tests so existing benchmark behavior is
not accidentally broken.

A provider-neutral interface does not itself improve compression. Compression
savings and output quality must be measured against the same inputs, model
settings, and provider-reported metrics.
