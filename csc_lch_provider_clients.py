"""Live provider adapters for CSC-LCH using only the Python standard library.

Anthropic supports provider-side input token counting. OpenAI-compatible APIs do
not expose a universal preflight token-count endpoint; this adapter therefore
returns None unless optional tiktoken is installed and supports the model.
Actual input/output usage from generation responses is kept separate.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from csc_lch_providers import ProviderAdapter, ProviderResponse, TokenUsage


class ProviderAPIError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class HTTPJSONClient:
    def __init__(self, base_url: str, headers: Dict[str, str], timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.headers = dict(headers)
        self.timeout = timeout

    def post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = dict(self.headers)
        headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise ProviderAPIError("HTTP %s on %s: %s" % (exc.code, path, detail), exc.code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderAPIError("Network error on %s: %s" % (path, exc)) from exc
        if not isinstance(parsed, dict):
            raise ProviderAPIError("Expected a JSON object from %s" % path)
        return parsed


class AnthropicAdapter(ProviderAdapter):
    provider_name = "anthropic"

    def __init__(self, api_key: Optional[str] = None,
                 base_url: str = "https://api.anthropic.com", timeout: int = 120):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("Set ANTHROPIC_API_KEY or pass api_key")
        self.client = HTTPJSONClient(base_url, {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "user-agent": "csc-lch-provider-adapter/1.0",
        }, timeout=timeout)

    def count_tokens(self, text: str, *, model: str) -> Optional[int]:
        data = self.client.post("/v1/messages/count_tokens", {
            "model": model,
            "messages": [{"role": "user", "content": text}],
        })
        count = data.get("input_tokens")
        if not isinstance(count, int) or count < 0:
            raise ProviderAPIError("Anthropic count_tokens response lacked a valid input_tokens")
        return count

    def generate(self, prompt: str, *, model: str,
                 options: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        opts = dict(options or {})
        body = {
            "model": model,
            "max_tokens": int(opts.pop("max_tokens", 512)),
            "messages": [{"role": "user", "content": prompt}],
        }
        system = opts.pop("system", None)
        if system:
            body["system"] = system
        body.update(opts)
        data = self.client.post("/v1/messages", body)
        text = "".join(
            item.get("text", "") for item in data.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        )
        usage = data.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        return ProviderResponse(
            text=text, provider=self.provider_name, model=str(data.get("model", model)),
            usage=TokenUsage(
                input_tokens=input_tokens if isinstance(input_tokens, int) else None,
                output_tokens=output_tokens if isinstance(output_tokens, int) else None,
                source="provider-reported" if isinstance(input_tokens, int) and isinstance(output_tokens, int)
                else "provider-usage-incomplete",
            ),
            raw_metadata={"stop_reason": data.get("stop_reason")},
        )


class OpenAICompatibleAdapter(ProviderAdapter):
    """Adapter for APIs implementing the OpenAI Chat Completions shape."""

    provider_name = "openai-compatible"

    def __init__(self, api_key: Optional[str] = None,
                 base_url: Optional[str] = None, timeout: int = 120):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("Set OPENAI_API_KEY or pass api_key")
        url = base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        self.client = HTTPJSONClient(url, {
            "Authorization": "Bearer " + key,
            "user-agent": "csc-lch-provider-adapter/1.0",
        }, timeout=timeout)

    def count_tokens(self, text: str, *, model: str) -> Optional[int]:
        # Optional local tokenizer. This is a tokenizer measurement, not a provider API count.
        try:
            import tiktoken  # type: ignore
        except ImportError:
            return None
        try:
            enc = tiktoken.encoding_for_model(model)
        except (KeyError, ValueError):
            return None
        return len(enc.encode(text))

    def generate(self, prompt: str, *, model: str,
                 options: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        opts = dict(options or {})
        body: Dict[str, Any] = {
            "model": model,
            "messages": [],
            "max_tokens": int(opts.pop("max_tokens", 512)),
        }
        system = opts.pop("system", None)
        if system:
            body["messages"].append({"role": "system", "content": system})
        body["messages"].append({"role": "user", "content": prompt})
        body.update(opts)
        data = self.client.post("/chat/completions", body)
        choices = data.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        content = message.get("content", "")
        if isinstance(content, list):
            content = "".join(
                item.get("text", "") for item in content if isinstance(item, dict)
            )
        usage = data.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        return ProviderResponse(
            text=content if isinstance(content, str) else "",
            provider=self.provider_name, model=str(data.get("model", model)),
            usage=TokenUsage(
                input_tokens=input_tokens if isinstance(input_tokens, int) else None,
                output_tokens=output_tokens if isinstance(output_tokens, int) else None,
                source="provider-reported" if isinstance(input_tokens, int) and isinstance(output_tokens, int)
                else "provider-usage-incomplete",
            ),
            raw_metadata={"finish_reason": choices[0].get("finish_reason") if choices else None},
        )
