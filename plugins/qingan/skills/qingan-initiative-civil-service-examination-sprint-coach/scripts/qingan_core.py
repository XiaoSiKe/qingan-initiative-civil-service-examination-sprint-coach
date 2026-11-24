#!/usr/bin/env python3
"""Local-first state engine for Qing'an Initiative."""

from __future__ import print_function

import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import shutil
import tempfile
import uuid
from collections import Counter, defaultdict
from pathlib import Path


SCHEMA_VERSION = 1
REVIEW_INTERVALS = (1, 3, 7, 14, 30)
MIN_PRIORITY_ATTEMPTS = 15
VALID_EXAM_TYPES = {"national", "province", "institution"}
VALID_LIFE_MODES = {"campus", "working", "full-time", "caregiving", "flexible"}
LIFE_MODE_GUIDANCE = {
    "campus": "课程与实验先占位；空堂做专项小组，晚间整块做申论或模考，考试周主动降载",
    "working": "工作日优先短回测，周末安排整块训练；加班后不机械补欠账",
    "full-time": "设置明确开始、午间恢复和停止点；用完成质量而不是学习时长判断进度",
    "caregiving": "优先可中断、低启动成本任务；突发照护后重排，不追补全部欠账",
    "flexible": "先按当前可用时间生成临时计划，用一周完成率校准真实生活约束",
}
VALID_RATINGS = {"again", "hard", "good", "easy"}
VALID_ERROR_TYPES = {
    "knowledge",
    "recognition",
    "reading",
    "reasoning",
    "calculation",
    "strategy",
    "careless",
    "unknown",
}


class QinganError(Exception):
    """Expected user-facing error."""


def parse_date(value):
    if isinstance(value, str) and len(value) == 10 and value[4] == value[7] == "-":
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            pass
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise QinganError("日期必须使用 YYYY-MM-DD 格式")


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def data_root(explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("QINGAN_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".qingan-gongkao"


def ensure_layout(root):
    root.mkdir(parents=True, exist_ok=True)
    for name in ("attachments", "backups", "exports", "materials"):
        (root / name).mkdir(exist_ok=True)


def atomic_write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(path))
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def atomic_json_write(path, value):
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    atomic_write_bytes(path, (rendered + "\n").encode("utf-8"))


def load_profile(root):
    path = root / "profile.json"
    if not path.exists():
        raise QinganError("尚未初始化，请先运行 qingan.py init")
    try:
        with path.open("r", encoding="utf-8") as handle:
            profile = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise QinganError("profile.json 无法读取：%s" % exc)
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise QinganError("数据版本不兼容，请先运行 qingan.py migrate")
    return profile


def normalize_study_days(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise QinganError("study_days_per_week 必须是 1 到 7 的整数")
    if days < 1 or days > 7:
        raise QinganError("study_days_per_week 必须是 1 到 7 的整数")
    return days


def normalize_life_mode(value):
    if value not in VALID_LIFE_MODES:
        raise QinganError("life_mode 必须是 campus、working、full-time、caregiving 或 flexible")
    return value


def init_profile(
    root,
    exam_type,
    exam_date,
    hours_per_week,
    province=None,
    study_days_per_week=6,
    life_mode="flexible",
):
    if exam_type not in VALID_EXAM_TYPES:
        raise QinganError("不支持的考试类型")
    exam_day = parse_date(exam_date)
    if hours_per_week <= 0 or hours_per_week > 168:
        raise QinganError("每周学习时间必须大于 0 且不超过 168 小时")
    ensure_layout(root)
    path = root / "profile.json"
    if path.exists():
        raise QinganError("档案已经存在；如需修改，请编辑档案而不是覆盖历史")
    profile = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "exam_type": exam_type,
        "exam_date": exam_day.isoformat(),
        "hours_per_week": float(hours_per_week),
        "province": province or None,
        "study_days_per_week": normalize_study_days(study_days_per_week),
        "life_mode": normalize_life_mode(life_mode),
        "baseline": {},
    }
    atomic_json_write(path, profile)
    (root / "events.jsonl").touch(exist_ok=True)
    (root / "materials" / "index.jsonl").touch(exist_ok=True)
    return profile


def update_profile(
    root,
    exam_type=None,
    exam_date=None,
    hours_per_week=None,
    province=None,
    study_days_per_week=None,
    life_mode=None,
):
    profile = load_profile(root)
    if all(
        value is None
        for value in (exam_type, exam_date, hours_per_week, province, study_days_per_week, life_mode)
    ):
        raise QinganError("至少提供一项要更新的档案字段")
    updated = dict(profile)
    if exam_type is not None:
        if exam_type not in VALID_EXAM_TYPES:
            raise QinganError("不支持的考试类型")
        updated["exam_type"] = exam_type
    if exam_date is not None:
        updated["exam_date"] = parse_date(exam_date).isoformat()
    if hours_per_week is not None:
        if hours_per_week <= 0 or hours_per_week > 168:
            raise QinganError("每周学习时间必须大于 0 且不超过 168 小时")
        updated["hours_per_week"] = float(hours_per_week)
    if province is not None:
        updated["province"] = province or None
    if study_days_per_week is not None:
        updated["study_days_per_week"] = normalize_study_days(study_days_per_week)
    if life_mode is not None:
        updated["life_mode"] = normalize_life_mode(life_mode)
    ensure_layout(root)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = root / "backups" / ("profile-%s.json" % stamp)
    shutil.copy2(str(root / "profile.json"), str(backup))
    updated["updated_at"] = utc_now()
    atomic_json_write(root / "profile.json", updated)
    return {"profile": updated, "backup": str(backup)}


def _parse_json_lines(data, *, retain_records=True, question_id=None):
    records = []
    invalid = []
    for line_number, raw in enumerate(io.BytesIO(data), 1):
        line = raw.removesuffix(b"\n")
        if not line.strip():
            continue
        try:
            # Generated rows are UTF-8 objects. Let the JSON decoder handle older
            # encodings and BOM-prefixed rows as it did before.
            payload = (
                line.decode("utf-8") if line.startswith(b"{") and b"\x00" not in line[:4] else line
            )
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise ValueError("JSON value is not an object")
            if retain_records and (question_id is None or value.get("question_id") == question_id):
                records.append(value)
        except (UnicodeDecodeError, ValueError) as exc:
            invalid.append({"line": line_number, "error": str(exc)})
            if not retain_records:
                break
    return records, invalid


def read_json_lines(path):
    if not path.exists():
        return [], []
    return _parse_json_lines(path.read_bytes())


def append_json_line(path, value):
    _append_json_line(path, value)


def _append_json_line(path, value, *, validated_snapshot=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    with path.open("a+b", buffering=0) as handle:
        handle.seek(0)
        existing = handle.read()
        if validated_snapshot is not None:
            if existing != validated_snapshot:
                raise QinganError("日志刚有新记录，请重试本次回测。")
        else:
            _, invalid = _parse_json_lines(existing, retain_records=False)
            if invalid:
                suffix = "；如为粘连的完整事件，可用 recover-events 修复" if path.name == "events.jsonl" else ""
                raise QinganError("%s 有损坏行，已暂停写入%s" % (path.name, suffix))
        separator = b"\n" if existing and not existing.endswith(b"\n") else b""
        row = separator + encoded + b"\n"
        if handle.write(row) != len(row):
            raise QinganError("%s 发生不完整写入，请保留文件并检查日志" % path.name)
        os.fsync(handle.fileno())


def normalize_module(value):
    if not isinstance(value, str) or not value.strip():
        raise QinganError("module 不能为空")
    return value.strip()


def timestamp_and_study_date(value=None):
    if value is None:
        now = dt.datetime.now().astimezone()
        return now.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat(), now.date()
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise QinganError("timestamp 必须是 ISO-8601 时间")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat(), parsed.date()


def question_fingerprint(payload):
    explicit = payload.get("question_id")
    if explicit:
        return str(explicit)
    basis = "|".join(
        str(payload.get(key, "")).strip().lower()
        for key in ("module", "subtype", "question", "source_ref")
    )
    if not basis.replace("|", ""):
        return str(uuid.uuid4())
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]


def store_attachment(root, source_path, question_id):
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise QinganError("attachment_path 不存在或不是文件")
    suffix = source.suffix.lower()[:10]
    destination = root / "attachments" / (question_id + suffix)
    if not destination.exists():
        shutil.copy2(str(source), str(destination))
    return str(destination)


def record_session(root, payload):
    load_profile(root)
    minutes = payload.get("duration_minutes")
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not 0 <= minutes <= 1440:
        raise QinganError("duration_minutes 必须是 0 到 1440 的数字")
    try:
        attempts = int(payload.get("attempts", 0))
        correct_answers = int(payload.get("correct_answers", 0))
        planned_tasks = int(payload.get("planned_tasks", 0))
        completed_tasks = int(payload.get("completed_tasks", 0))
    except (TypeError, ValueError):
        raise QinganError("任务数、作答数和正确数必须是整数")
    if attempts < 0 or correct_answers < 0 or correct_answers > attempts:
        raise QinganError("attempts 与 correct_answers 必须满足 0 <= 正确数 <= 作答数")
    comparison_key = payload.get("comparison_key")
    if comparison_key is not None and (
        not isinstance(comparison_key, str) or not 0 < len(comparison_key.strip()) <= 120
        or not minutes or not attempts
    ):
        raise QinganError("comparison_key 需要非空口径名（最多 120 字符）、作答题量和实际计时")
    timestamp, event_date = timestamp_and_study_date(payload.get("timestamp"))
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "kind": "study_session",
        "timestamp": timestamp,
        "study_date": event_date.isoformat(),
        "module": normalize_module(payload.get("module")),
        "duration_minutes": float(minutes),
        "comparison_key": comparison_key.strip() if comparison_key else None,
        "planned_tasks": planned_tasks,
        "completed_tasks": completed_tasks,
        "attempts": attempts,
        "correct_answers": correct_answers,
        "note": str(payload.get("note", ""))[:1000],
    }
    if not 0 <= completed_tasks <= planned_tasks:
        raise QinganError("任务数量必须满足 0 <= 完成数 <= 计划数")
    append_json_line(root / "events.jsonl", event)
    return event


def record_error(root, payload):
    load_profile(root)
    error_type = payload.get("error_type", "unknown")
    if error_type not in VALID_ERROR_TYPES:
        raise QinganError("error_type 不在允许范围内")
    confidence = payload.get("confidence", "low")
    if confidence not in {"high", "medium", "low"}:
        raise QinganError("confidence 必须是 high、medium 或 low")
    question_id = question_fingerprint(payload)
    timestamp, event_date = timestamp_and_study_date(payload.get("timestamp"))
    session_id = payload.get("session_id")
    if session_id:
        existing, _ = read_json_lines(root / "events.jsonl")
        linked_session = next((
            item for item in existing
            if item.get("kind") == "study_session" and item.get("event_id") == session_id
        ), None)
        if linked_session is None:
            raise QinganError("session_id 未指向已有学习会话")
        if normalize_module(payload.get("module")) != linked_session.get("module"):
            raise QinganError("错题模块必须与关联学习会话一致；跨模块错题请单独记录")
    tags = payload.get("tags", [])
    if not isinstance(tags, list):
        raise QinganError("tags 必须是数组")
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "kind": "question_attempt",
        "timestamp": timestamp,
        "study_date": event_date.isoformat(),
        "question_id": question_id,
        "module": normalize_module(payload.get("module")),
        "subtype": str(payload.get("subtype", "unknown"))[:100],
        "question": str(payload.get("question", ""))[:5000],
        "user_answer": payload.get("user_answer"),
        "correct_answer": payload.get("correct_answer"),
        "correct": False,
        "duration_seconds": payload.get("duration_seconds"),
        "error_type": error_type,
        "confidence": confidence,
        "diagnosis": str(payload.get("diagnosis", ""))[:2000],
        "correction": str(payload.get("correction", ""))[:2000],
        "source_type": str(payload.get("source_type", "unknown"))[:100],
        "source_ref": str(payload.get("source_ref", ""))[:1000],
        "session_id": session_id,
        "tags": [str(item)[:80] for item in tags][:20],
        "review_stage": 0,
        "next_due": (event_date + dt.timedelta(days=REVIEW_INTERVALS[0])).isoformat(),
    }
    duration = event["duration_seconds"]
    if duration is not None and (not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0):
        raise QinganError("duration_seconds 必须是非负数字")
    attachment = payload.get("attachment_path")
    if attachment:
        event["attachment_path"] = store_attachment(root, attachment, question_id)
    append_json_line(root / "events.jsonl", event)
    return event


def event_study_date(event):
    return event.get("study_date") or event.get("timestamp", "")[:10]


def latest_review_state(events):
    states = {}
    for event in events:
        question_id = event.get("question_id")
        if not question_id:
            continue
        if event.get("kind") == "question_attempt" and event.get("correct") is False:
            states[question_id] = {
                "question_id": question_id,
                "module": event.get("module"),
                "subtype": event.get("subtype"),
                "question": event.get("question"),
                "stage": int(event.get("review_stage", 0)),
                "next_due": event.get("next_due"),
                "successful_dates": [],
                "status": "retesting",
            }
        elif event.get("kind") == "review_result" and question_id in states:
            state = states[question_id]
            state["stage"] = int(event.get("review_stage", state["stage"]))
            state["next_due"] = event.get("next_due")
            if event.get("rating") == "again":
                state["successful_dates"] = []
            elif event.get("rating") in {"good", "easy"}:
                success_day = event_study_date(event)
                if success_day not in state["successful_dates"]:
                    state["successful_dates"].append(success_day)
            state["status"] = event.get("status", state["status"])
    return states


def rate_review(root, question_id, rating, when=None):
    load_profile(root)
    if rating not in VALID_RATINGS:
        raise QinganError("rating 必须是 again、hard、good 或 easy")
    path = root / "events.jsonl"
    try:
        snapshot = path.read_bytes()
    except FileNotFoundError:
        snapshot = b""
    events, invalid = _parse_json_lines(snapshot, question_id=question_id)
    states = latest_review_state(events)
    if question_id not in states:
        raise QinganError("找不到该 question_id")
    state = states[question_id]
    current = int(state["stage"])
    timestamp, event_date = timestamp_and_study_date(when)
    successful_dates = set(state["successful_dates"])
    same_day_success = rating in {"good", "easy"} and event_date.isoformat() in successful_dates
    if rating == "again":
        stage = 0
        successful_dates.clear()
    elif rating == "hard" or same_day_success:
        stage = current
    elif rating == "good":
        stage = min(current + 1, len(REVIEW_INTERVALS) - 1)
    else:
        stage = min(current + 2, len(REVIEW_INTERVALS) - 1)
    if rating in {"good", "easy"}:
        successful_dates.add(event_date.isoformat())
    status = "stable" if len(successful_dates) >= 2 and stage >= 2 else "retesting"
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "kind": "review_result",
        "timestamp": timestamp,
        "study_date": event_date.isoformat(),
        "question_id": question_id,
        "module": state.get("module"),
        "rating": rating,
        "review_stage": stage,
        "status": status,
        "next_due": (
            state["next_due"] if same_day_success
            else (event_date + dt.timedelta(days=REVIEW_INTERVALS[stage])).isoformat()
        ),
    }
    _append_json_line(path, event, validated_snapshot=snapshot if not invalid else None)
    return event


def due_reviews(root, on_date=None, limit=10):
    load_profile(root)
    day = parse_date(on_date) if on_date else dt.date.today()
    events, invalid = read_json_lines(root / "events.jsonl")
    due = _due_review_rows(events, day, limit)
    return {"date": day.isoformat(), "due": due, "invalid_lines": invalid}


def _due_review_rows(events, day, limit):
    due = []
    for state in latest_review_state(events).values():
        if state["status"] == "stable" or not state.get("next_due"):
            continue
        if parse_date(state["next_due"]) <= day:
            due.append(state)
    due.sort(key=lambda item: (item["next_due"], item.get("module") or ""))
    return due[: max(0, limit)]


def phase_for(days_left):
    if days_left < 0:
        return "exam-passed"
    if days_left <= 7:
        return "final-recall"
    if days_left <= 30:
        return "mock-and-repair"
    if days_left <= 60:
        return "targeted-improvement"
    return "foundation-and-targeting"


def _attempt_metrics(events):
    attempts = []
    sessions = []
    reviews = []
    for event in events:
        kind = event.get("kind")
        if kind == "question_attempt":
            attempts.append(event)
        elif kind == "study_session":
            sessions.append(event)
        elif kind == "review_result":
            reviews.append(event)
    by_module = defaultdict(lambda: {"attempts": 0, "correct": 0, "errors": 0})
    error_types = Counter()
    patterns = defaultdict(dict)
    for event in attempts:
        module = event.get("module") or "unknown"
        if event.get("correct") is False:
            error_type = event.get("error_type", "unknown")
            error_types[error_type] += 1
            key = (event.get("subtype") or "unknown", error_type)
            if event.get("question_id") and error_type != "unknown":
                patterns[(module, key)][event["question_id"]] = event
        if event.get("session_id"):
            continue
        by_module[module]["attempts"] += 1
        if event.get("correct") is True:
            by_module[module]["correct"] += 1
        else:
            by_module[module]["errors"] += 1
    groups = defaultdict(lambda: {"attempts": 0, "correct": 0, "minutes": 0.0})
    session_correct_total = 0
    for event in sessions:
        module = event.get("module") or "unknown"
        session_attempts = int(event.get("attempts", 0))
        session_correct = int(event.get("correct_answers", 0))
        by_module[module]["attempts"] += session_attempts
        by_module[module]["correct"] += session_correct
        by_module[module]["errors"] += session_attempts - session_correct
        session_correct_total += session_correct
        key = event.get("comparison_key")
        if key and session_attempts and event.get("duration_minutes", 0) > 0:
            group = groups[(module, key)]
            group["attempts"] += session_attempts
            group["correct"] += session_correct
            group["minutes"] += float(event["duration_minutes"])
    planned = sum(int(item.get("planned_tasks", 0)) for item in sessions)
    completed = sum(int(item.get("completed_tasks", 0)) for item in sessions)
    normalized_modules = {}
    for module, values in by_module.items():
        normalized = dict(values)
        normalized["accuracy"] = (
            round(float(values["correct"]) / values["attempts"], 4)
            if values["attempts"]
            else None
        )
        normalized_modules[module] = normalized
    by_module_patterns = defaultdict(list)
    for (module, (subtype, error_type)), questions in patterns.items():
        latest = max(questions.values(), key=lambda row: row.get("timestamp", ""))
        by_module_patterns[module].append({
            "subtype": subtype, "error_type": error_type, "distinct_questions": len(questions),
            "latest_at": latest.get("timestamp"),
            "diagnosis": latest.get("diagnosis"), "correction": latest.get("correction"),
        })
    for items in by_module_patterns.values():
        items.sort(key=lambda item: (item["distinct_questions"], item["latest_at"] or ""), reverse=True)
    total_attempts = sum(value["attempts"] for value in by_module.values())
    total_correct = sum(value["correct"] for value in by_module.values())
    return {
        "attempts": total_attempts,
        "correct": total_correct,
        "accuracy": round(float(total_correct) / total_attempts, 4) if total_attempts else None,
        "study_minutes": sum(float(item.get("duration_minutes", 0)) for item in sessions),
        "planned_tasks": planned,
        "completed_tasks": completed,
        "completion_rate": round(float(completed) / planned, 4) if planned else None,
        "review_count": len({(row.get("question_id"), event_study_date(row)) for row in reviews}),
        "by_module": normalized_modules,
        "error_types": dict(error_types),
        "error_patterns": dict(by_module_patterns),
        "session_correct": session_correct_total,
        "comparison_groups": [
            dict(totals, module=module, comparison_key=key)
            for (module, key), totals in sorted(groups.items())
        ],
    }


def _priority_for_week(current, previous):
    """Choose a weak module using rates from a sufficiently sized training sample."""
    cohort_by_module = {}
    previous_cohorts = {
        (row["module"], row["comparison_key"]): row
        for row in previous["comparison_groups"] if row["attempts"] >= MIN_PRIORITY_ATTEMPTS
    }
    for row in current["comparison_groups"]:
        present = cohort_by_module.get(row["module"])
        if row["attempts"] >= MIN_PRIORITY_ATTEMPTS and (not present or row["attempts"] > present["attempts"]):
            cohort_by_module[row["module"]] = row

    candidates = []
    for module, stats in current["by_module"].items():
        cohort = cohort_by_module.get(module)
        sample = cohort or stats
        attempts = sample["attempts"]
        correct = sample["correct"]
        if not attempts or correct == attempts:
            continue
        patterns = current["error_patterns"].get(module, [])
        pattern = patterns[0] if patterns else None
        key = cohort["comparison_key"] if cohort else None
        rate = correct * 60 / cohort["minutes"] if cohort else None
        prior = previous_cohorts.get((module, key))
        prior_rate = prior["correct"] * 60 / prior["minutes"] if prior else None
        speed_change = (rate - prior_rate) / prior_rate if prior_rate else None
        candidates.append({
            "module": module,
            "basis": "timed-cohort" if cohort else "unmatched-observation",
            "comparison_key": key,
            "attempts": attempts,
            "correct": correct,
            "miss_rate": round(1 - correct / attempts, 4),
            "correct_per_hour": round(rate, 2) if rate is not None else None,
            "relative_speed_change": round(speed_change, 4) if speed_change is not None else None,
            "first_error": pattern,
        })

    supported = [item for item in candidates if item["attempts"] >= MIN_PRIORITY_ATTEMPTS]
    timed = [item for item in supported if item["basis"] == "timed-cohort"]

    def rank(item):
        pattern = item["first_error"]
        recurrence = max(0, (pattern["distinct_questions"] if pattern else 0) - 1)
        decline = min(0.0, item["relative_speed_change"] or 0.0)
        return (-item["miss_rate"], -recurrence, decline, -item["attempts"], item["module"])

    strongest = sorted(timed or supported, key=rank)
    diagnostic = min(candidates, key=rank)["module"] if candidates and not strongest else None
    if not strongest:
        return None, diagnostic, "现有样本未能确认弱项，先用一次短测建立基线。"
    priority = strongest[0]
    source = ("同口径限时组" if priority["basis"] == "timed-cohort" else "近期练习观察，口径尚未核齐")
    return priority, None, (
        "%s：%d/%d 道正确，错率 %.0f%%。用重复错因和同类计时变化校准。"
        % (source, priority["correct"], priority["attempts"], priority["miss_rate"] * 100)
    )


def weekly_report(root, end_date=None):
    profile = load_profile(root)
    end = parse_date(end_date) if end_date else dt.date.today()
    events, invalid = read_json_lines(root / "events.jsonl")
    return _weekly_report(profile, end, events, invalid)


def _weekly_report(profile, end, events, invalid):
    start = end - dt.timedelta(days=6)
    previous_end = start - dt.timedelta(days=1)
    previous_start = previous_end - dt.timedelta(days=6)
    current_events = []
    previous_events = []
    for event in events:
        try:
            day = parse_date(event_study_date(event))
        except QinganError:
            continue
        if start <= day <= end:
            current_events.append(event)
        elif previous_start <= day <= previous_end:
            previous_events.append(event)
    current = _attempt_metrics(current_events)
    previous = _attempt_metrics(previous_events)
    priority, diagnostic_module, priority_reason = _priority_for_week(current, previous)
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "exam_date": profile["exam_date"],
        "current": current,
        "previous": previous,
        "priority_module": priority["module"] if priority else None,
        "priority_reason": priority_reason,
        "priority_evidence": priority,
        "diagnostic_module": diagnostic_module,
        "invalid_lines": invalid,
    }


def metric_delta(current, previous, key):
    current_value = current.get(key)
    previous_value = previous.get(key)
    if current_value is None or previous_value is None:
        return None
    return round(float(current_value) - float(previous_value), 4)


def efficiency_report(root, end_date=None):
    """Evaluate the learning process without inventing a composite score."""
    profile = load_profile(root)
    day = parse_date(end_date) if end_date else dt.date.today()
    events, invalid = read_json_lines(root / "events.jsonl")
    report = _weekly_report(profile, day, events, invalid)
    open_reviews = sum(
        state["status"] != "stable" for state in latest_review_state(events).values()
    )
    current = report["current"]
    previous = report["previous"]
    attempts = current["attempts"]
    minutes = current["study_minutes"]
    completion = current["completion_rate"]
    accuracy = current["accuracy"]
    module_count = len(current["by_module"])
    correct_per_hour = (
        round(current["session_correct"] / (minutes / 60.0), 2)
        if minutes and module_count == 1 else None
    )
    prior_groups = {
        (item["module"], item["comparison_key"]): item
        for item in previous["comparison_groups"] if item["attempts"] >= 20
    }
    comparisons = []
    for item in current["comparison_groups"]:
        prior = prior_groups.get((item["module"], item["comparison_key"]))
        if not prior or item["attempts"] < 20:
            continue
        delta = item["correct"] / item["attempts"] - prior["correct"] / prior["attempts"]
        speed_change = item["correct"] / item["minutes"] - prior["correct"] / prior["minutes"]
        comparisons.append({
            "module": item["module"],
            "comparison_key": item["comparison_key"],
            "current_attempts": item["attempts"],
            "previous_attempts": prior["attempts"],
            "accuracy_delta": round(delta, 4),
            "correct_per_hour_delta": round(speed_change * 60, 2),
        })
    accuracy_delta = comparisons[0]["accuracy_delta"] if len(comparisons) == 1 else None
    declining = min(comparisons, key=lambda item: item["accuracy_delta"], default=None)

    evidence_checks = {
        "enough_current_attempts": attempts >= 30,
        "has_study_time": minutes > 0,
        "has_task_completion_data": current["planned_tasks"] > 0,
        "has_previous_baseline": bool(comparisons),
    }
    evidence_count = sum(1 for value in evidence_checks.values() if value)
    confidence = "high" if evidence_count == 4 else "medium" if evidence_count >= 2 else "low"

    dimensions = {
        "execution": {
            "value": completion,
            "status": "no-data" if completion is None else "observed",
        },
        "accuracy": {
            "value": accuracy,
            "status": (
                "no-data"
                if accuracy is None
                else "multiple-comparisons"
                if len(comparisons) > 1
                else "no-baseline"
                if accuracy_delta is None
                else "declined"
                if accuracy_delta < -0.05
                else "improved"
                if accuracy_delta > 0.05
                else "similar"
            ),
        },
        "time_efficiency": {
            "correct_per_hour": correct_per_hour,
            "note": "使用同一模块的已计入会话汇总；跨周纵向变化见同口径对照。",
        },
        "review_loop": {
            "reviews_this_week": current["review_count"],
            "open_reviews": open_reviews,
            "status": "open-loop" if open_reviews and not current["review_count"] else "active",
        },
        "coverage": {
            "modules_with_evidence": module_count,
            "status": "narrow" if module_count < 2 else "visible",
        },
    }

    if attempts < 20 or not minutes:
        bottleneck = "evidence"
        next_action = "先完成一组带计时、题量和正确数的基线训练，再评价效率"
    elif completion is not None and completion < 0.6:
        bottleneck = "execution"
        next_action = "下周缩小任务量并保留完成判据，先让计划完成率回到可持续区间"
    elif open_reviews and not current["review_count"]:
        bottleneck = "review-loop"
        next_action = "先清理到期错题并记录回测结果，暂不扩张新题型"
    elif declining is not None and declining["accuracy_delta"] < -0.05:
        bottleneck = "method"
        next_action = "先检查 %s（%s）中错误最多的题型，再做同口径近变式。" % (
            declining["module"], declining["comparison_key"],
        )
    elif module_count < 2:
        bottleneck = "coverage"
        next_action = "补一个非主攻模块的小样本，避免用单一模块代表整体状态"
    else:
        bottleneck = "time-strategy"
        next_action = "保持当前方法，用同类训练比较单位时间正确数和止损执行"

    return {
        "period": report["period"],
        "confidence": confidence,
        "evidence_checks": evidence_checks,
        "dimensions": dimensions,
        "trend": {
            "accuracy_delta": accuracy_delta,
            "matched_groups": comparisons,
            "completion_rate_delta": metric_delta(current, previous, "completion_rate"),
            "study_minutes_delta": metric_delta(current, previous, "study_minutes"),
        },
        "bottleneck": bottleneck,
        "priority_module": report["priority_module"],
        "priority_evidence": report["priority_evidence"],
        "diagnostic_module": report["diagnostic_module"],
        "next_action": next_action,
        **({"invalid_lines": invalid} if invalid else {}),
        "warning": "这是一份训练过程诊断，不是能力分数；样本条件变化时不要直接比较。",
    }


def status(root, today=None):
    profile = load_profile(root)
    day = parse_date(today) if today else dt.date.today()
    info = _exam_progress(profile, day)
    events, invalid = read_json_lines(root / "events.jsonl")
    review_states = latest_review_state(events)
    return {
        **info,
        "event_count": len(events),
        "open_review_count": sum(1 for value in review_states.values() if value["status"] != "stable"),
        "stable_review_count": sum(1 for value in review_states.values() if value["status"] == "stable"),
        "invalid_lines": invalid,
    }


def _exam_progress(profile, day):
    days_left = (parse_date(profile["exam_date"]) - day).days
    return {"profile": profile, "days_left": days_left, "phase": phase_for(days_left)}


def today_plan(root, today=None, minutes=None):
    profile = load_profile(root)
    day = parse_date(today) if today else dt.date.today()
    info = _exam_progress(profile, day)
    if info["phase"] == "exam-passed":
        return {
            "date": day.isoformat(),
            "phase": info["phase"],
            "days_left": info["days_left"],
            "blocks": [],
            "required_action": "考试日期已过，请运行 update-profile 更新档案后再生成训练计划",
        }
    if minutes is not None and not 0 <= minutes <= 1440:
        raise QinganError("minutes 必须在 0 到 1440 之间")
    if minutes == 0:
        return {
            "date": day.isoformat(), "phase": info["phase"], "days_left": info["days_left"],
            "daily_budget_minutes": 0, "blocks": [], "required_action": "今天休息，保留到期回测。",
        }
    events, invalid = read_json_lines(root / "events.jsonl")
    due = _due_review_rows(events, day, limit=20)
    report = _weekly_report(profile, day, events, invalid)
    priority = report["priority_module"] or report["diagnostic_module"] or "一个待校准的模块"
    evidence = report["priority_evidence"]
    first_error = evidence.get("first_error") if evidence else None
    subtype = first_error.get("subtype") if first_error else None
    focus_label = "%s（%s）" % (priority, subtype) if subtype and subtype != "unknown" else priority
    verification = (
        first_error.get("correction") if first_error and first_error.get("correction")
        else "独立作答，记下首个错误环节和用时"
    )
    weakness_kind = "weakness" if evidence else "diagnostic"
    study_days = normalize_study_days(info["profile"].get("study_days_per_week", 6))
    life_mode = info["profile"].get("life_mode", "flexible")
    normalize_life_mode(life_mode)
    daily_budget = max(3, int(round(float(info["profile"]["hours_per_week"]) * 60 / study_days)))
    if minutes is not None:
        daily_budget = minutes
    if minutes is not None and daily_budget <= 10 and not due:
        return {
            "date": day.isoformat(), "phase": info["phase"], "days_left": info["days_left"],
            "study_days_per_week": study_days, "life_mode": life_mode,
            "schedule_guidance": LIFE_MODE_GUIDANCE[life_mode],
            "daily_budget_minutes": daily_budget, "priority_module": report["priority_module"],
            "priority_evidence": evidence,
            **({"invalid_lines": invalid} if invalid else {}),
            "blocks": [{
                "kind": weakness_kind,
                "duration_minutes": daily_budget,
                "task": "做一道 %s 小题，时间到即停" % focus_label,
                "done_when": verification,
            }],
        }
    review_minutes = min(max(1, len(due) * 5), max(1, daily_budget // 4))
    remainder = daily_budget - review_minutes
    weakness_minutes = max(1, int(round(remainder * 0.6))) if remainder else 0
    transfer_minutes = remainder - weakness_minutes
    review_count = min(len(due), max(1, review_minutes // 5))
    blocks = [
        {
            "kind": "due-review",
            "duration_minutes": review_minutes,
            "task": "回测至多 %d 道到期错题，时间到就停" % review_count
            if review_count else "闭卷口述一个已学方法",
            "question_ids": [item["question_id"] for item in due[:review_count]],
            "done_when": "逐题给出回测评级；无到期题时完成方法主动回忆",
        },
        {
            "kind": weakness_kind,
            "duration_minutes": weakness_minutes,
            "task": "训练 %s，并记录第一个错误环节" % focus_label,
            "done_when": verification,
        },
        {
            "kind": "timed-mix",
            "duration_minutes": transfer_minutes,
            "task": "完成一组限时综合题并记录用时",
            "done_when": "记录正确率、用时和是否执行止损",
        },
    ]
    if info["phase"] == "final-recall":
        blocks[2] = {
            "kind": "exam-routine",
            "duration_minutes": transfer_minutes,
            "task": "复核考场顺序、时间节点和已学高频内容",
            "done_when": "能脱离笔记复述流程且不新增学习体系",
        }
    return {
        "date": day.isoformat(),
        "phase": info["phase"],
        "days_left": info["days_left"],
        "study_days_per_week": study_days,
        "life_mode": life_mode,
        "schedule_guidance": LIFE_MODE_GUIDANCE[life_mode],
        "daily_budget_minutes": sum(item["duration_minutes"] for item in blocks),
        "priority_module": report["priority_module"],
        "priority_evidence": evidence,
        **({"invalid_lines": invalid} if invalid else {}),
        "blocks": [block for block in blocks if block["duration_minutes"] > 0],
    }


def minimum_day_plan(root, today=None, minutes=20):
    """Return a deliberately small plan for a low-energy or overloaded day."""
    profile = load_profile(root)
    day = parse_date(today) if today else dt.date.today()
    info = _exam_progress(profile, day)
    try:
        budget = int(minutes)
    except (TypeError, ValueError):
        raise QinganError("minutes 必须是 5 到 180 的整数")
    if budget < 5 or budget > 180:
        raise QinganError("minutes 必须是 5 到 180 的整数")
    if info["phase"] == "exam-passed":
        return {
            "date": day.isoformat(),
            "phase": info["phase"],
            "minutes": 0,
            "blocks": [],
            "required_action": "考试日期已过，请更新档案后再生成最低可行训练日",
        }
    events, invalid = read_json_lines(root / "events.jsonl")
    due = _due_review_rows(events, day, limit=3)
    report = _weekly_report(profile, day, events, invalid)
    priority = report.get("priority_module") or "最熟悉的已学模块"
    life_mode = info["profile"].get("life_mode", "flexible")
    normalize_life_mode(life_mode)
    settle_minutes = min(3, max(1, budget // 8))
    recall_minutes = min(max(1, len(due) * 3), max(1, (budget - settle_minutes) // 3))
    action_minutes = budget - settle_minutes - recall_minutes
    review_count = min(len(due), max(1, recall_minutes // 3))
    return {
        "date": day.isoformat(),
        "phase": info["phase"],
        "minutes": budget,
        "message": "今天不追欠账，只保住节奏；完成这一小轮就算有效训练。",
        "life_mode": life_mode,
        "schedule_guidance": LIFE_MODE_GUIDANCE[life_mode],
        **({"invalid_lines": invalid} if invalid else {}),
        "blocks": [
            {
                "kind": "settle",
                "duration_minutes": settle_minutes,
                "task": "放下总进度，只写出今天能控制的一件事",
            },
            {
                "kind": "gentle-recall",
                "duration_minutes": recall_minutes,
                "task": "回测至多 %d 道到期错题，时间到就停" % review_count
            if review_count else "闭卷口述一个已学方法",
            "question_ids": [item["question_id"] for item in due[:review_count]],
            },
            {
                "kind": "small-win",
                "duration_minutes": action_minutes,
                "task": "完成一小组 %s 熟悉题，达到时间即停止" % priority,
            },
        ],
        "done_when": "完成三个小块并记录一句真实感受，不要求追回落后进度",
    }


def week_plan(root, end_date=None):
    """Turn recent evidence into one focus, one maintenance lane, and one pause."""
    profile = load_profile(root)
    day = parse_date(end_date) if end_date else dt.date.today()
    info = _exam_progress(profile, day)
    if info["phase"] == "exam-passed":
        return {
            "phase": info["phase"],
            "days_left": info["days_left"],
            "weekly_budget_minutes": 0,
            "lanes": [],
            "required_action": "考试日期已过，请更新档案后再生成周计划",
        }
    events, invalid = read_json_lines(root / "events.jsonl")
    report = _weekly_report(profile, day, events, invalid)
    life_mode = info["profile"].get("life_mode", "flexible")
    normalize_life_mode(life_mode)
    modules = sorted(
        report["current"]["by_module"].items(),
        key=lambda item: (-item[1]["attempts"], item[0]),
    )
    focus = report["priority_module"] or report["diagnostic_module"] or "综合基线诊断"
    maintenance = next((name for name, _ in modules if name != focus), "已学稳定模块")
    budget = max(3, int(round(float(info["profile"]["hours_per_week"]) * 60)))
    focus_minutes = max(1, int(round(budget * 0.55)))
    maintenance_minutes = max(1, int(round(budget * 0.25)))
    review_minutes = budget - focus_minutes - maintenance_minutes
    if review_minutes < 1:
        focus_minutes -= 1
        review_minutes = 1
    pause = "新知识扩张" if info["days_left"] <= 30 else "无数据支撑的低优先级加练"
    return {
        "phase": info["phase"],
        "days_left": info["days_left"],
        "weekly_budget_minutes": budget,
        "life_mode": life_mode,
        "schedule_guidance": LIFE_MODE_GUIDANCE[life_mode],
        "evidence": "recent-training-data" if report["priority_module"] else "temporary-baseline",
        "priority_evidence": report["priority_evidence"],
        "diagnostic_module": report["diagnostic_module"],
        "lanes": [
            {"kind": "focus", "module": focus, "minutes": focus_minutes},
            {"kind": "maintain", "module": maintenance, "minutes": maintenance_minutes},
            {"kind": "review-and-mock", "module": "到期回测与限时综合", "minutes": review_minutes},
        ],
        "pause": pause,
        "priority_reason": report["priority_reason"],
        **({"invalid_lines": invalid} if invalid else {}),
    }


def register_material(root, payload):
    load_profile(root)
    title = str(payload.get("title", "")).strip()
    path_value = payload.get("path")
    url = payload.get("url")
    if not title and not path_value and not url:
        raise QinganError("资料至少需要 title、path 或 url 之一")
    digest = None
    normalized_path = None
    if path_value:
        path = Path(path_value).expanduser().resolve()
        if not path.is_file():
            raise QinganError("资料 path 不存在或不是文件")
        normalized_path = str(path)
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
    confidence = payload.get("confidence", "medium")
    if confidence not in {"high", "medium", "low"}:
        raise QinganError("confidence 必须是 high、medium 或 low")
    record = {
        "schema_version": SCHEMA_VERSION,
        "material_id": str(uuid.uuid4()),
        "registered_at": utc_now(),
        "title": title or (Path(normalized_path).name if normalized_path else str(url)),
        "path": normalized_path,
        "url": str(url) if url else None,
        "sha256": digest,
        "kind": str(payload.get("kind", "other"))[:80],
        "confidence": confidence,
        "scope_note": str(payload.get("scope_note", ""))[:1000],
    }
    append_json_line(root / "materials" / "index.jsonl", record)
    return record


def migrate(root):
    profile_path = root / "profile.json"
    if not profile_path.exists():
        raise QinganError("没有可迁移的档案")
    ensure_layout(root)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = root / "backups" / stamp
    backup.mkdir(parents=True, exist_ok=False)
    for relative in ("profile.json", "events.jsonl", "materials/index.jsonl", "interview.jsonl"):
        source = root / relative
        if source.exists():
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(destination))
    profile = load_profile(root)
    return {"schema_version": profile["schema_version"], "backup": str(backup), "changed": False}


def doctor(root):
    issues = []
    initialized = (root / "profile.json").exists()
    if initialized:
        try:
            load_profile(root)
        except QinganError as exc:
            issues.append(str(exc))
    _, invalid = read_json_lines(root / "events.jsonl")
    if invalid:
        issues.append("events.jsonl 有 %d 个损坏行，读取时已跳过" % len(invalid))
    return {
        "ok": not issues,
        "initialized": initialized,
        "data_dir": str(root),
        "schema_version": SCHEMA_VERSION,
        "issues": issues,
    }


def export_data(root, output_dir, output_format):
    load_profile(root)
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    events, invalid = read_json_lines(root / "events.jsonl")
    if output_format == "csv":
        path = output / "qingan-events.csv"
        fields = sorted({key for event in events for key in event.keys()})
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for event in events:
                writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in event.items()})
    elif output_format == "markdown":
        path = output / "qingan-report.md"
        info = status(root)
        report = weekly_report(root)
        lines = [
            "# 青岸计划学习报告",
            "",
            "- 距离考试：%s 天" % info["days_left"],
            "- 当前阶段：%s" % info["phase"],
            "- 本周学习：%s 分钟" % report["current"]["study_minutes"],
            "- 本周答题：%s 次" % report["current"]["attempts"],
            "- 本周正确率：%s" % (
                "数据不足"
                if report["current"]["accuracy"] is None
                else "%.1f%%" % (report["current"]["accuracy"] * 100)
            ),
            "- 任务完成率：%s" % (
                "数据不足"
                if report["current"]["completion_rate"] is None
                else "%.1f%%" % (report["current"]["completion_rate"] * 100)
            ),
            "- 优先模块：%s" % (report["priority_module"] or "数据不足"),
            "- 损坏记录行：%s" % len(invalid),
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
    else:
        raise QinganError("format 必须是 markdown 或 csv")
    return {"path": str(path), "events": len(events), "invalid_lines": invalid}
