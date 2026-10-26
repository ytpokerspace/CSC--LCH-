"""Provider-neutral interfaces for CSC-LCH.

This module intentionally has no network or vendor SDK dependencies. It defines
the contract a provider adapter must implement and supplies a deterministic
offline adapter for tests and demos.

Important: token counts are optional metadata. A character-based estimate is
not a provider tokenizer count, and mock results are not model-quality evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TokenUsage:
    """Token metrics with explicit provenance.

    input_tokens/output_tokens should be populated only when reported by the
    provider or measured with that provider's tokenizer. Keep estimates separate.
    """
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    source: str = "unknown"
    estimated_input_tokens: Optional[int] = None
    estimated_output_tokens: Optional[int] = None

    def __post_init__(self) -> None:
        for name in ("input_tokens", "output_tokens",
                     "estimated_input_tokens", "estimated_output_tokens"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(name + " must be non-negative")


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized response shared across provider integrations."""
    text: str
    provider: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


class ProviderAdapter:
    """Minimal contract for a CSC-LCH model-provider integration.

    Implementations should raise clear exceptions on transport, authentication,
    or provider errors. Never silently replace missing usage with a fake count.
    """

    provider_name = "unknown"

    def generate(self, prompt: str, *, model: str,
                 options: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        """Generate a response for prompt. Subclasses must implement this."""
        raise NotImplementedError

    def count_tokens(self, text: str, *, model: str) -> Optional[int]:
        """Return a provider-accurate count, or None when unavailable."""
        return None


class MockProvider(ProviderAdapter):
    """Deterministic offline adapter; useful for plumbing tests only."""

    provider_name = "mock"

    def generate(self, prompt: str, *, model: str,
                 options: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")
        if not model or not isinstance(model, str):
            raise ValueError("model must be a non-empty string")
        return ProviderResponse(
            text="MOCK_RESPONSE: " + prompt,
            provider=self.provider_name,
            model=model,
            usage=TokenUsage(source="mock-no-token-metrics"),
        )


def estimate_tokens_by_characters(text: str, *, chars_per_token: float = 4.0) -> int:
    """Return a clearly labeled rough estimate, never a tokenizer measurement."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if chars_per_token <= 0:
        raise ValueError("chars_per_token must be positive")
    if not text:
        return 0
    # Ceiling division without depending on a provider-specific tokenizer.
    return int(len(text) / chars_per_token) + (1 if len(text) % chars_per_token else 0)
