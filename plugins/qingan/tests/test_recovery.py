import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "qingan-initiative-civil-service-examination-sprint-coach" / "scripts"))
from qingan_core import QinganError, append_json_line, init_profile, read_json_lines
from qingan_recovery import recover_events


class RecoveryTests(unittest.TestCase):
    def test_legacy_no_newline_and_lossless_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_profile(root, "province", "2030-05-01", 10)
            path = root / "events.jsonl"
            a = {"kind": "question_attempt", "event_id": "old", "schema_version": 1}
            b = {"kind": "study_session", "event_id": "new", "schema_version": 1}
            raw_a = json.dumps(a).encode()
            raw_b = json.dumps(b).encode()
            path.write_bytes(raw_a)
            append_json_line(path, b)
            self.assertEqual(read_json_lines(path), ([a, b], []))
            broken = raw_a + raw_b + b"\n"
            path.write_bytes(broken)
            with self.assertRaises(QinganError):
                append_json_line(path, {"kind": "study_session"})
            self.assertEqual(path.read_bytes(), broken)
            result = recover_events(root)
            self.assertTrue(result["changed"])
            self.assertEqual(Path(result["backup"]).read_bytes(), broken)
            self.assertEqual(read_json_lines(path), ([a, b], []))
            self.assertFalse(recover_events(root)["changed"])

    def test_incomplete_event_suffix_is_left_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_profile(root, "province", "2030-05-01", 10)
            path = root / "events.jsonl"
            damaged = b'{"schema_version":1,"kind":"study_session","event_id":"one"}{"kind":'
            path.write_bytes(damaged)
            with self.assertRaises(QinganError):
                recover_events(root)
            self.assertEqual(path.read_bytes(), damaged)


    def test_append_validation_keeps_legacy_encodings_and_bad_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            old = b'\xef\xbb\xbf{"kind":"old"}\n\n{"kind":"second"}'
            path.write_bytes(old)
            append_json_line(path, {"kind": "new"})
            self.assertEqual([row["kind"] for row in read_json_lines(path)[0]], ["old", "second", "new"])
            broken = path.read_bytes() + b'{"kind":"\xff"}\n'
            path.write_bytes(broken)
            self.assertEqual(read_json_lines(path)[1][0]["line"], 5)
            with self.assertRaises(QinganError):
                append_json_line(path, {"kind": "blocked"})
            self.assertEqual(path.read_bytes(), broken)
