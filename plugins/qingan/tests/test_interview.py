import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "qingan-initiative-civil-service-examination-sprint-coach" / "scripts"))
from qingan_core import QinganError
from qingan_interview import interview_history, record_interview


class InterviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.first = {
            "question": "线上已提交、窗口说缺件，怎么协调？",
            "criterion": "核实冲突，并给清楚的下一步",
            "evidence": "找后台沟通",
            "feedback": "补出核对依据。",
            "modality": "transcript",
            "result": "partial",
            "event_id": "initial",
        }

    def test_unmeasured_text_feedback_keeps_first_answer_link(self):
        initial = record_interview(self.root, self.first)["record"]
        rewrite = record_interview(self.root, {
            "revises": initial["record_id"], "evidence": "查提交回执和缺件提示",
            "feedback": "给出核实依据和补件清单。", "result": "met",
        })["record"]
        history = interview_history(self.root, rewrite["record_id"])
        self.assertEqual([row["result"] for row in history["records"]], ["partial", "met"])
        self.assertEqual(rewrite["criterion"], self.first["criterion"])
        self.assertEqual(rewrite["revises"], "initial")
        self.assertIsNone(initial["duration_seconds"])
        self.assertFalse((self.root / "profile.json").exists())

    def test_unsupported_claims_and_changed_revision_criterion_are_rejected(self):
        for invalid in ({"delivery": {"pace": "偏快"}}, {"response": "完整原稿"}):
            with self.assertRaises(QinganError):
                record_interview(self.root, {**self.first, **invalid})
        self.assertFalse((self.root / "interview.jsonl").exists())
        record_interview(self.root, self.first)
        self.assertTrue(record_interview(self.root, self.first)["duplicate"])
        with self.assertRaises(QinganError):
            record_interview(self.root, {**self.first, "event_id": "revision",
                                        "revises": "initial", "criterion": "另一个判据"})
        self.assertEqual(len(interview_history(self.root, "initial")["records"]), 1)
