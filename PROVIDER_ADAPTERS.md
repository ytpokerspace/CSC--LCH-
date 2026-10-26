# Live provider adapters

This is the live-API layer for the provider-neutral interface.

## Supported adapter types

- `AnthropicAdapter`: uses Anthropic Messages API and the provider's
  `/v1/messages/count_tokens` endpoint.
- `OpenAICompatibleAdapter`: uses the OpenAI Chat Completions API shape,
  including services that implement that same shape. Generation input/output
  usage is taken from the response's usage fields.

Both use Python's standard library for HTTP and JSON; no SDK is required.

## Example

```python
from csc_lch_provider_clients import AnthropicAdapter, OpenAICompatibleAdapter

anthropic = AnthropicAdapter()  # reads ANTHROPIC_API_KEY
result = anthropic.generate("Answer briefly: what is CSC-LCH?", model="YOUR_MODEL_ID")
print(result.text, result.usage)

openai = OpenAICompatibleAdapter()  # reads OPENAI_API_KEY
result = openai.generate("Answer briefly: what is CSC-LCH?", model="YOUR_MODEL_ID")
print(result.text, result.usage)
```

For OpenAI-compatible services, set `OPENAI_BASE_URL` when the endpoint is not
the OpenAI default. Use the model identifier accepted by that service.

## Token accounting rules

- Anthropic input counts come from the Anthropic count-tokens API.
- OpenAI-compatible generation reports actual prompt and completion usage.
- OpenAI-compatible APIs do not share a universal preflight counting endpoint.
  If the optional `tiktoken` package is installed and recognizes the model,
  `count_tokens` uses that local tokenizer and returns its count. Otherwise it
  returns `None`, rather than inventing a count.
- Actual usage values and local tokenizer counts are not interchangeable; record
  the source with every result.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests use fake responses and make no network calls. A passing unit test does not
prove live credentials, model access, endpoint compatibility, pricing, or quality.
