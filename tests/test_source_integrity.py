import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.source_integrity import verify_manifest


class SourceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / "archive"
        self.archive.mkdir()
        self.manifest = self.root / "manifest.json"
        self.source = self.archive / "original.txt"
        # Includes non-ASCII text, CRLF, and trailing spaces: hash exact bytes.
        self.content = "café\r\nline with trailing spaces  \n".encode("utf-8")
        self.source.write_bytes(self.content)
        self.record = {
            "source_id": "source-001",
            "archive_path": "original.txt",
            "sha256": hashlib.sha256(self.content).hexdigest(),
            "byte_length": len(self.content),
        }
        self.data = {
            "schema_version": 1,
            "dataset_id": "fixture-set",
            "dataset_version": "1",
            "policy_version": "T3-v1",
            "run_config": {"mode": "offline"},
            "source_records": [self.record],
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.data), encoding="utf-8")

    def test_exact_source_bytes_verify(self):
        self.write_manifest()
        result = verify_manifest(self.manifest, self.archive)
        self.assertEqual(result["integrity"], "verified")
        self.assertEqual(result["sources_verified"], 1)
        self.assertEqual(result["total_source_bytes"], len(self.content))

    def test_modified_source_is_rejected(self):
        self.write_manifest()
        self.source.write_bytes(self.content + b"changed")
        with self.assertRaisesRegex(ValueError, "byte_length mismatch|SHA-256 mismatch"):
            verify_manifest(self.manifest, self.archive)

    def test_duplicate_source_ids_are_rejected(self):
        self.data["source_records"].append(dict(self.record))
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "duplicate source_id"):
            verify_manifest(self.manifest, self.archive)

    def test_path_escape_is_rejected(self):
        self.data["source_records"][0]["archive_path"] = "../outside.txt"
        (self.root / "outside.txt").write_bytes(self.content)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "escapes archive root"):
            verify_manifest(self.manifest, self.archive)

    def test_missing_required_manifest_field_is_rejected(self):
        del self.data["policy_version"]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "policy_version"):
            verify_manifest(self.manifest, self.archive)

    def test_duplicate_json_keys_are_rejected(self):
        self.manifest.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            verify_manifest(self.manifest, self.archive)

    def test_declared_byte_length_is_checked(self):
        self.data["source_records"][0]["byte_length"] += 1
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "byte_length mismatch"):
            verify_manifest(self.manifest, self.archive)


if __name__ == "__main__":
    unittest.main()
