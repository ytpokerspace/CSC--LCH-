import copy
import unittest

from csc_lch_lossless import CODEC, decode_text, encode_text, packet_json_size


class LosslessCodecTests(unittest.TestCase):
    def test_exact_round_trip_preserves_whitespace_unicode_negation_and_units(self):
        samples = [
            "",
            "  keep leading and trailing spaces  \n\n",
            "Do NOT delete this. Never remove the exception; do not infer missing data.",
            "0.5 kg != 5 kg; -12.50%; 2026-11-18; ID: OPS-4417",
            "Emoji: 🧠 🧊 🧪; combining: e\u0301; CJK: 漢字",
            "line one\r\nline two\nline three\tend",
        ]
        for original in samples:
            with self.subTest(original=original):
                packet = encode_text(original)
                self.assertEqual(decode_text(packet), original)
                self.assertEqual(packet["codec"], CODEC)
                self.assertEqual(packet["original_bytes"], len(original.encode("utf-8")))

    def test_deterministic_packet(self):
        text = "same input => same packet"
        self.assertEqual(encode_text(text), encode_text(text))

    def test_json_round_trip(self):
        import json
        original = "Negation: don't change 3.5 ms. 🧠"
        packet = json.loads(json.dumps(encode_text(original)))
        self.assertEqual(decode_text(packet), original)
        self.assertGreater(packet_json_size(packet), 0)

    def test_rejects_checksum_tampering(self):
        packet = encode_text("original")
        packet["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "checksum"):
            decode_text(packet)

    def test_rejects_bad_payload(self):
        packet = encode_text("original")
        packet["payload_b64"] = "%%%not-base64%%%"
        with self.assertRaisesRegex(ValueError, "base64"):
            decode_text(packet)

    def test_rejects_wrong_size_metadata(self):
        packet = encode_text("abc")
        packet["original_bytes"] = 99
        with self.assertRaisesRegex(ValueError, "length"):
            decode_text(packet)

    def test_rejects_truncated_payload(self):
        packet = encode_text("text " * 200)
        packet["payload_b64"] = packet["payload_b64"][:-4]
        with self.assertRaises(ValueError):
            decode_text(packet)

    def test_rejects_oversized_output_before_expansion(self):
        packet = encode_text("large enough for a cap test")
        with self.assertRaisesRegex(ValueError, "oversized"):
            decode_text(packet, max_output_bytes=2)

    def test_rejects_non_string_input_and_invalid_level(self):
        with self.assertRaises(TypeError):
            encode_text(12)
        with self.assertRaises(ValueError):
            encode_text("text", level=10)


if __name__ == "__main__":
    unittest.main()
