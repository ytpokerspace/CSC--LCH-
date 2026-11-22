#!/usr/bin/env python3
"""Verify archived CSC-LCH source records against a dataset manifest.

Offline and standard-library-only. Hashes are calculated over exact file bytes,
so whitespace, line endings, and Unicode encodings are not normalized.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_REQUIRED_TOP = {"schema_version", "dataset_id", "dataset_version",
                 "policy_version", "run_config", "source_records"}
_REQUIRED_SOURCE = {"source_id", "archive_path", "sha256", "byte_length"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("manifest contains duplicate JSON key: " + key)
        result[key] = value
    return result


def verify_manifest(manifest_path, archive_root):
    """Return a verification summary or raise ValueError on any integrity issue."""
    manifest_path = Path(manifest_path)
    root = Path(archive_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("archive root must be a directory")

    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read manifest: " + str(exc)) from exc

    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    missing = _REQUIRED_TOP - manifest.keys()
    if missing:
        raise ValueError("manifest missing fields: " + ", ".join(sorted(missing)))
    if manifest["schema_version"] != 1:
        raise ValueError("unsupported schema_version; expected 1")
    for field in ("dataset_id", "dataset_version", "policy_version"):
        value = manifest[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(field + " must be a non-empty string")
    if not isinstance(manifest["run_config"], dict):
        raise ValueError("run_config must be a JSON object")
    records = manifest["source_records"]
    if not isinstance(records, list) or not records:
        raise ValueError("source_records must be a non-empty array")

    seen = set()
    total_bytes = 0
    verified = []
    for index, record in enumerate(records):
        label = "source_records[" + str(index) + "]"
        if not isinstance(record, dict):
            raise ValueError(label + " must be a JSON object")
        missing = _REQUIRED_SOURCE - record.keys()
        if missing:
            raise ValueError(label + " missing fields: " + ", ".join(sorted(missing)))
        source_id = record["source_id"]
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError(label + ".source_id must be a non-empty string")
        if source_id in seen:
            raise ValueError("duplicate source_id: " + source_id)
        seen.add(source_id)

        relative = record["archive_path"]
        if not isinstance(relative, str) or not relative:
            raise ValueError(label + ".archive_path must be a non-empty string")
        candidate = (root / relative).resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(label + ".archive_path escapes archive root") from exc
        if not candidate.is_file():
            raise ValueError(label + ".archive_path is not a regular file")

        expected_hash = record["sha256"]
        if not isinstance(expected_hash, str) or not _SHA256.fullmatch(expected_hash):
            raise ValueError(label + ".sha256 must be 64 lowercase hexadecimal characters")
        expected_size = record["byte_length"]
        if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size < 0:
            raise ValueError(label + ".byte_length must be a non-negative integer")

        content = candidate.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if len(content) != expected_size:
            raise ValueError(label + ": byte_length mismatch")
        if actual_hash != expected_hash:
            raise ValueError(label + ": SHA-256 mismatch")
        total_bytes += len(content)
        verified.append(source_id)

    return {
        "schema_version": 1,
        "dataset_id": manifest["dataset_id"],
        "dataset_version": manifest["dataset_version"],
        "policy_version": manifest["policy_version"],
        "sources_verified": len(verified),
        "total_source_bytes": total_bytes,
        "verified_source_ids": verified,
        "integrity": "verified",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("archive_root", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_manifest(args.manifest, args.archive_root),
                         indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print("integrity error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
