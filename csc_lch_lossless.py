"""Exact, reversible text codec for CSC-LCH.

This module is a lossless storage/transport primitive, not a claim that encoded
text will use fewer LLM tokens. It preserves the original UTF-8 byte sequence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import zlib
from typing import Any, Dict

CODEC = "csc-lch-lossless/1"
DEFAULT_MAX_OUTPUT_BYTES = 64 * 1024 * 1024


def encode_text(text: str, level: int = 9) -> Dict[str, Any]:
    """Encode text into a JSON-safe, checksummed lossless packet."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= 9:
        raise ValueError("level must be an integer from 0 to 9")

    original = text.encode("utf-8", errors="strict")
    compressed = zlib.compress(original, level)
    return {
        "codec": CODEC,
        "encoding": "utf-8",
        "original_bytes": len(original),
        "sha256": hashlib.sha256(original).hexdigest(),
        "payload_b64": base64.b64encode(compressed).decode("ascii"),
    }


def decode_text(packet: Dict[str, Any], *, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> str:
    """Decode and validate a packet; reject corruption, wrong types, or oversized output."""
    if not isinstance(packet, dict):
        raise ValueError("packet must be an object")
    if packet.get("codec") != CODEC or packet.get("encoding") != "utf-8":
        raise ValueError("unsupported codec or encoding")

    expected_size = packet.get("original_bytes")
    if (not isinstance(expected_size, int) or isinstance(expected_size, bool)
            or expected_size < 0 or expected_size > max_output_bytes):
        raise ValueError("invalid or oversized original_bytes")
    expected_hash = packet.get("sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ValueError("invalid sha256 field")
    payload_text = packet.get("payload_b64")
    if not isinstance(payload_text, str):
        raise ValueError("payload_b64 must be a string")

    try:
        compressed = base64.b64decode(payload_text.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError("invalid base64 payload") from exc

    try:
        inflater = zlib.decompressobj()
        raw = inflater.decompress(compressed, max_output_bytes + 1)
        if len(raw) > max_output_bytes or inflater.unconsumed_tail:
            raise ValueError("decoded output exceeds size limit")
        raw += inflater.flush()
    except zlib.error as exc:
        raise ValueError("invalid compressed payload") from exc

    if len(raw) > max_output_bytes:
        raise ValueError("decoded output exceeds size limit")
    if not inflater.eof or inflater.unused_data:
        raise ValueError("truncated payload or trailing compressed data")
    if len(raw) != expected_size:
        raise ValueError("original byte length mismatch")
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("sha256 checksum mismatch")

    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("payload is not valid UTF-8") from exc


def packet_json_size(packet: Dict[str, Any]) -> int:
    """Return serialized UTF-8 JSON size for measurement; not an LLM token count."""
    return len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
