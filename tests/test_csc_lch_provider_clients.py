"""Tests for live adapter response normalization; no network calls or API keys."""
import json
import unittest
from unittest.mock import patch

from csc_lch_provider_clients import (
    AnthropicAdapter, OpenAICompatibleAdapter, ProviderAPIError
)


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, path, body):
        self.calls.append((path, body))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class ClientAdapterTests(unittest.TestCase):
    def test_anthropic_generation_uses_reported_usage(self):
        adapter = AnthropicAdapter.__new__(AnthropicAdapter)
        adapter.client = FakeClient({
            "model": "claude-test", "content": [{"type": "text", "text": "hello"}],
            "usage": {"input_tokens": 12, "output_tokens": 3}, "stop_reason": "end_turn"
        })
        result = adapter.generate("question", model="claude-test")
        self.assertEqual(result.text, "hello")
        self.assertEqual(result.usage.input_tokens, 12)
        self.assertEqual(result.usage.output_tokens, 3)
        self.assertEqual(result.usage.source, "provider-reported")

    def test_anthropic_count_tokens_uses_api_count(self):
        adapter = AnthropicAdapter.__new__(AnthropicAdapter)
        adapter.client = FakeClient({"input_tokens": 17})
        self.assertEqual(adapter.count_tokens("x", model="claude-test"), 17)
        self.assertEqual(adapter.client.calls[0][0], "/v1/messages/count_tokens")

    def test_openai_generation_uses_reported_usage(self):
        adapter = OpenAICompatibleAdapter.__new__(OpenAICompatibleAdapter)
        adapter.client = FakeClient({
            "model": "gpt-test", "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 4}
        })
        result = adapter.generate("question", model="gpt-test")
        self.assertEqual(result.text, "answer")
        self.assertEqual(result.usage.input_tokens, 9)
        self.assertEqual(result.usage.output_tokens, 4)
        self.assertEqual(adapter.client.calls[0][0], "/chat/completions")

    def test_openai_count_returns_none_without_optional_tokenizer(self):
        adapter = OpenAICompatibleAdapter.__new__(OpenAICompatibleAdapter)
        with patch.dict("sys.modules", {"tiktoken": None}):
            self.assertIsNone(adapter.count_tokens("hello", model="unknown-model"))

    def test_api_errors_are_not_silently_swallowed(self):
        adapter = AnthropicAdapter.__new__(AnthropicAdapter)
        adapter.client = FakeClient(ProviderAPIError("unauthorized", 401))
        with self.assertRaises(ProviderAPIError):
            adapter.generate("question", model="claude-test")


if __name__ == "__main__":
    unittest.main()
