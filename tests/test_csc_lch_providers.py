"""Unit tests for the provider-neutral CSC-LCH adapter contract."""
import unittest

from csc_lch_providers import (
    MockProvider,
    ProviderAdapter,
    ProviderResponse,
    TokenUsage,
    estimate_tokens_by_characters,
)


class ProviderAdapterTests(unittest.TestCase):
    def test_mock_provider_is_deterministic_and_offline(self):
        provider = MockProvider()
        first = provider.generate("hello", model="mock-v1")
        second = provider.generate("hello", model="mock-v1")
        self.assertEqual(first, second)
        self.assertEqual(first.text, "MOCK_RESPONSE: hello")
        self.assertEqual(first.provider, "mock")
        self.assertEqual(first.model, "mock-v1")
        self.assertIsNone(first.usage.input_tokens)
        self.assertEqual(first.usage.source, "mock-no-token-metrics")

    def test_base_adapter_does_not_invent_token_counts(self):
        self.assertIsNone(ProviderAdapter().count_tokens("hello", model="x"))

    def test_usage_rejects_negative_counts(self):
        with self.assertRaises(ValueError):
            TokenUsage(input_tokens=-1, source="provider")

    def test_response_can_represent_real_provider_usage(self):
        response = ProviderResponse(
            text="ok",
            provider="example",
            model="example-model",
            usage=TokenUsage(input_tokens=10, output_tokens=2, source="provider-reported"),
        )
        self.assertEqual(response.usage.input_tokens, 10)
        self.assertEqual(response.usage.source, "provider-reported")

    def test_character_estimate_is_explicitly_separate(self):
        self.assertEqual(estimate_tokens_by_characters(""), 0)
        self.assertEqual(estimate_tokens_by_characters("12345", chars_per_token=4), 2)
        with self.assertRaises(ValueError):
            estimate_tokens_by_characters("x", chars_per_token=0)

    def test_mock_rejects_invalid_model(self):
        with self.assertRaises(ValueError):
            MockProvider().generate("hello", model="")


if __name__ == "__main__":
    unittest.main()
