import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import qingan_core as core  # noqa: E402


class QinganCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "data"
        core.init_profile(self.root, "national", "2030-11-30", 25)

    def tearDown(self):
        self.temp.cleanup()

    def test_init_and_phase_boundaries(self):
        status = core.status(self.root, today="2030-09-01")
        self.assertEqual(status["phase"], "foundation-and-targeting")
        self.assertEqual(core.status(self.root, today="2030-10-15")["phase"], "targeted-improvement")
        self.assertEqual(core.status(self.root, today="2030-11-10")["phase"], "mock-and-repair")
        self.assertEqual(core.status(self.root, today="2030-11-25")["phase"], "final-recall")

    def test_init_refuses_overwrite(self):
        with self.assertRaises(core.QinganError):
            core.init_profile(self.root, "province", "2031-01-01", 20)

    def test_profile_update_creates_backup(self):
        result = core.update_profile(
            self.root,
            exam_date="2031-03-15",
            hours_per_week=18,
            study_days_per_week=5,
            life_mode="campus",
        )
        self.assertEqual(result["profile"]["exam_date"], "2031-03-15")
        self.assertEqual(result["profile"]["hours_per_week"], 18.0)
        self.assertEqual(result["profile"]["study_days_per_week"], 5)
        self.assertEqual(result["profile"]["life_mode"], "campus")
        self.assertTrue(Path(result["backup"]).is_file())
        plan = core.today_plan(self.root, today="2030-09-01")
        self.assertEqual(plan["daily_budget_minutes"], 216)
        self.assertIn("课程", plan["schedule_guidance"])

    def test_invalid_life_constraints_are_rejected(self):
        with self.assertRaises(core.QinganError):
            core.update_profile(self.root, study_days_per_week=0)
        with self.assertRaises(core.QinganError):
            core.update_profile(self.root, life_mode="always-on")

    def test_session_metrics_and_weekly_priority(self):
        session = core.record_session(self.root, {
            "timestamp": "2030-09-02T10:00:00+00:00",
            "module": "资料分析",
            "duration_minutes": 45,
            "planned_tasks": 2,
            "completed_tasks": 1,
            "attempts": 20,
            "correct_answers": 14,
        })
        core.record_error(self.root, {
            "timestamp": "2030-09-02T10:20:00+00:00",
            "session_id": session["event_id"],
            "module": "资料分析",
            "question": "sample",
            "error_type": "calculation",
        })
        report = core.weekly_report(self.root, end_date="2030-09-07")
        self.assertEqual(report["current"]["attempts"], 20)
        self.assertEqual(report["current"]["correct"], 14)
        self.assertEqual(report["current"]["by_module"]["资料分析"]["errors"], 6)
        self.assertEqual(report["current"]["accuracy"], 0.7)
        self.assertEqual(report["current"]["completion_rate"], 0.5)
        self.assertEqual(report["priority_module"], "资料分析")

    def test_review_schedule_and_stability_gate(self):
        error = core.record_error(self.root, {
            "timestamp": "2030-09-01T08:00:00+00:00",
            "module": "判断推理",
            "subtype": "削弱加强",
            "question": "stable identity",
            "error_type": "reasoning",
        })
        self.assertEqual(error["next_due"], "2030-09-02")
        first = core.rate_review(self.root, error["question_id"], "good", "2030-09-02T08:00:00+00:00")
        self.assertEqual(first["review_stage"], 1)
        self.assertEqual(first["status"], "retesting")
        second = core.rate_review(self.root, error["question_id"], "good", "2030-09-05T08:00:00+00:00")
        self.assertEqual(second["review_stage"], 2)
        self.assertEqual(second["status"], "stable")
        self.assertEqual(core.due_reviews(self.root, "2030-12-01")["due"], [])

    def test_again_resets_review_stage(self):
        error = core.record_error(self.root, {"module": "言语理解", "question": "q", "error_type": "reading"})
        core.rate_review(self.root, error["question_id"], "easy", "2030-09-02T08:00:00+00:00")
        reset = core.rate_review(self.root, error["question_id"], "again", "2030-09-03T08:00:00+00:00")
        self.assertEqual(reset["review_stage"], 0)
        self.assertEqual(reset["next_due"], "2030-09-04")

    def test_corrupt_event_line_is_reported_not_overwritten(self):
        path = self.root / "events.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write("not-json\n")
        result = core.doctor(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(len(core.status(self.root)["invalid_lines"]), 1)
        self.assertIn("not-json", path.read_text(encoding="utf-8"))

    def test_register_material_hashes_local_file(self):
        material = Path(self.temp.name) / "notes.md"
        material.write_text("original material", encoding="utf-8")
        record = core.register_material(self.root, {"path": str(material), "kind": "notes", "confidence": "high"})
        self.assertEqual(len(record["sha256"]), 64)
        self.assertEqual(record["title"], "notes.md")

    def test_export_markdown_and_csv(self):
        core.record_session(self.root, {"module": "申论", "duration_minutes": 30, "attempts": 1, "correct_answers": 1})
        output = Path(self.temp.name) / "exports"
        markdown = core.export_data(self.root, output, "markdown")
        csv_result = core.export_data(self.root, output, "csv")
        self.assertTrue(Path(markdown["path"]).is_file())
        self.assertTrue(Path(csv_result["path"]).is_file())
        report_text = Path(markdown["path"]).read_text(encoding="utf-8")
        self.assertIn("青岸计划学习报告", report_text)
        self.assertIn("本周正确率：100.0%", report_text)

    def test_migrate_always_creates_backup_before_noop(self):
        result = core.migrate(self.root)
        backup = Path(result["backup"])
        self.assertFalse(result["changed"])
        self.assertTrue((backup / "profile.json").is_file())
        self.assertTrue((backup / "events.jsonl").is_file())

    def test_today_plan_has_exactly_three_blocks(self):
        result = core.today_plan(self.root, today="2030-11-25")
        self.assertEqual(result["phase"], "final-recall")
        self.assertEqual(len(result["blocks"]), 3)
        self.assertEqual(result["blocks"][-1]["kind"], "exam-routine")
        self.assertEqual(result["daily_budget_minutes"], 250)
        self.assertEqual(sum(item["duration_minutes"] for item in result["blocks"]), 250)
        self.assertTrue(all(item["done_when"] for item in result["blocks"]))

    def test_v01_profile_without_optional_life_constraints_still_works(self):
        profile_path = self.root / "profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile.pop("study_days_per_week")
        profile.pop("life_mode")
        core.atomic_json_write(profile_path, profile)
        result = core.today_plan(self.root, today="2030-11-25")
        self.assertEqual(result["study_days_per_week"], 6)
        self.assertEqual(result["life_mode"], "flexible")
        self.assertEqual(result["daily_budget_minutes"], 250)

    def test_minimum_day_preserves_rhythm_without_creating_debt(self):
        result = core.minimum_day_plan(self.root, today="2030-11-25", minutes=17)
        self.assertEqual(result["minutes"], 17)
        self.assertEqual(len(result["blocks"]), 3)
        self.assertEqual(sum(item["duration_minutes"] for item in result["blocks"]), 17)
        self.assertIn("不追欠账", result["message"])
        self.assertIn("不要求追回", result["done_when"])
        self.assertIn("真实生活约束", result["schedule_guidance"])

    def test_week_plan_uses_one_focus_one_maintenance_and_one_review_lane(self):
        core.record_session(self.root, {
            "timestamp": "2030-09-02T10:00:00+00:00",
            "module": "资料分析",
            "duration_minutes": 45,
            "attempts": 20,
            "correct_answers": 12,
        })
        core.record_session(self.root, {
            "timestamp": "2030-09-03T10:00:00+00:00",
            "module": "言语理解",
            "duration_minutes": 30,
            "attempts": 10,
            "correct_answers": 9,
        })
        result = core.week_plan(self.root, end_date="2030-09-07")
        self.assertEqual(result["evidence"], "recent-training-data")
        self.assertEqual(result["lanes"][0]["module"], "资料分析")
        self.assertEqual(result["lanes"][1]["module"], "言语理解")
        self.assertEqual(sum(item["minutes"] for item in result["lanes"]), 1500)

    def test_passed_exam_does_not_generate_training_blocks(self):
        result = core.today_plan(self.root, today="2030-12-01")
        self.assertEqual(result["phase"], "exam-passed")
        self.assertEqual(result["blocks"], [])
        self.assertIn("考试日期已过", result["required_action"])

    def test_invalid_tags_are_rejected(self):
        with self.assertRaises(core.QinganError):
            core.record_error(self.root, {"module": "言语理解", "question": "q", "tags": "not-a-list"})

    def test_unknown_session_link_is_rejected(self):
        with self.assertRaises(core.QinganError):
            core.record_error(self.root, {
                "module": "判断推理",
                "question": "q",
                "session_id": "missing-session",
            })


class QinganCliTests(unittest.TestCase):
    def test_cli_init_and_doctor(self):
        with tempfile.TemporaryDirectory() as temp:
            command = [
                sys.executable,
                str(SCRIPTS / "qingan.py"),
                "--data-dir",
                temp,
                "init",
                "--exam-type",
                "national",
                "--exam-date",
                "2030-11-30",
                "--hours-per-week",
                "20",
            ]
            initialized = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(json.loads(initialized.stdout)["schema_version"], 1)
            checked = subprocess.run(
                [sys.executable, str(SCRIPTS / "qingan.py"), "--data-dir", temp, "doctor"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertTrue(json.loads(checked.stdout)["ok"])
            planned = subprocess.run(
                [sys.executable, str(SCRIPTS / "qingan.py"), "--data-dir", temp, "week-plan", "--end-date", "2030-09-07"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=dict(os.environ, PYTHONIOENCODING="cp1252"),
            )
            self.assertEqual(len(json.loads(planned.stdout)["lanes"]), 3)
            minimum = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "qingan.py"),
                    "--data-dir",
                    temp,
                    "minimum-day",
                    "--date",
                    "2030-09-07",
                    "--minutes",
                    "15",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(json.loads(minimum.stdout)["minutes"], 15)


if __name__ == "__main__":
    unittest.main()
