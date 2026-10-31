"""Measured, reversible dictionary codec for CSC-LCH experiments.

This is a lossless serialization experiment, not semantic summarization. The full
source is recoverable from the dictionary and token-ID streams. Token counts use
tiktoken when installed; otherwise the report explicitly labels a lexical proxy.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple

CODEC_VERSION = 1
LEXEME_PATTERN = re.compile(r"\w+|\s+|[^\w\s]", re.UNICODE)


def split_exact(text: str) -> List[str]:
    parts = LEXEME_PATTERN.findall(text)
    if "".join(parts) != text:
        raise ValueError("lossless segmentation invariant failed")
    return parts


@dataclass(frozen=True)
class CodecResult:
    payload: Dict[str, Any]
    serialized: str
    dictionary_entries: int
    source_characters: int


def encode_documents(documents: Sequence[str]) -> CodecResult:
    """Encode documents using one shared first-seen dictionary and integer streams."""
    if not all(isinstance(document, str) for document in documents):
        raise TypeError("all documents must be strings")
    dictionary: List[str] = []
    ids_by_token: Dict[str, int] = {}
    streams: List[List[int]] = []
    for document in documents:
        stream: List[int] = []
        for piece in split_exact(document):
            if piece not in ids_by_token:
                ids_by_token[piece] = len(dictionary)
                dictionary.append(piece)
            stream.append(ids_by_token[piece])
        streams.append(stream)
    payload = {"version": CODEC_VERSION, "dictionary": dictionary, "streams": streams}
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return CodecResult(
        payload=payload,
        serialized=serialized,
        dictionary_entries=len(dictionary),
        source_characters=sum(map(len, documents)),
    )


def decode_documents(payload_or_json: Dict[str, Any] | str) -> List[str]:
    payload = json.loads(payload_or_json) if isinstance(payload_or_json, str) else payload_or_json
    if payload.get("version") != CODEC_VERSION:
        raise ValueError("unsupported codec version")
    dictionary = payload.get("dictionary")
    streams = payload.get("streams")
    if not isinstance(dictionary, list) or not all(isinstance(x, str) for x in dictionary):
        raise ValueError("invalid dictionary")
    if not isinstance(streams, list):
        raise ValueError("invalid streams")
    decoded: List[str] = []
    for stream in streams:
        if not isinstance(stream, list):
            raise ValueError("invalid token stream")
        pieces = []
        for symbol_id in stream:
            if isinstance(symbol_id, bool) or not isinstance(symbol_id, int):
                raise ValueError("symbol IDs must be integers")
            if symbol_id < 0 or symbol_id >= len(dictionary):
                raise ValueError("symbol ID out of range")
            pieces.append(dictionary[symbol_id])
        decoded.append("".join(pieces))
    return decoded


def tokenizer_counter(model: str = "gpt-4o"):
    """Return (counter, name); never silently label a proxy as model tokens."""
    try:
        import tiktoken  # type: ignore
    except ImportError:
        def proxy(text: str) -> int:
            return len(re.findall(r"\w+|\s+|[^\w\s]", text, flags=re.UNICODE))
        return proxy, "lexical_proxy_not_model_tokens"
    encoding = tiktoken.encoding_for_model(model)
    return lambda text: len(encoding.encode(text)), f"tiktoken:{encoding.name}:{model}"


def build_lazy_payload(documents: Sequence[str], selected_ids: Sequence[int]) -> str:
    """Build an oracle-selected retrieval payload; selection quality is not evaluated."""
    selected = sorted(set(selected_ids))
    if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= len(documents) for i in selected):
        raise ValueError("selected document ID out of range")
    selected_docs = [documents[i] for i in selected]
    encoded = encode_documents(selected_docs)
    index = [{"id": i, "characters": len(documents[i])} for i in range(len(documents))]
    result = {
        "version": CODEC_VERSION,
        "index": index,
        "selected_document_ids": selected,
        "selected_documents": encoded.payload,
    }
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def decode_lazy_payload(serialized: str) -> Tuple[List[Dict[str, int]], List[int], List[str]]:
    payload = json.loads(serialized)
    if payload.get("version") != CODEC_VERSION:
        raise ValueError("unsupported lazy payload version")
    index = payload["index"]
    selected = payload["selected_document_ids"]
    docs = decode_documents(payload["selected_documents"])
    if len(selected) != len(docs):
        raise ValueError("selected IDs and documents differ in length")
    return index, selected, docs
