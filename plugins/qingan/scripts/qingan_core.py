#!/usr/bin/env python3
"""Local-first state engine for Qing'an Initiative."""

from __future__ import print_function

import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections import Counter, defaultdict
from pathlib import Path


SCHEMA_VERSION = 1
REVIEW_INTERVALS = (1, 3, 7, 14, 30)
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


def atomic_json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(path))
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


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


def read_json_lines(path):
    records = []
    invalid = []
    if not path.exists():
        return records, invalid
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("JSON value is not an object")
                records.append(value)
            except (json.JSONDecodeError, ValueError) as exc:
                invalid.append({"line": line_number, "error": str(exc)})
    return records, invalid


def append_json_line(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(encoded + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def normalize_module(value):
    if not isinstance(value, str) or not value.strip():
        raise QinganError("module 不能为空")
    return value.strip()


def normalize_timestamp(value=None):
    if value is None:
        return utc_now()
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise QinganError("timestamp 必须是 ISO-8601 时间")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()


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
    if not isinstance(minutes, (int, float)) or minutes < 0 or minutes > 1440:
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
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "kind": "study_session",
        "timestamp": normalize_timestamp(payload.get("timestamp")),
        "module": normalize_module(payload.get("module")),
        "duration_minutes": float(minutes),
        "planned_tasks": planned_tasks,
        "completed_tasks": completed_tasks,
        "attempts": attempts,
        "correct_answers": correct_answers,
        "note": str(payload.get("note", ""))[:1000],
    }
    if event["planned_tasks"] < 0 or event["completed_tasks"] < 0:
        raise QinganError("任务数量不能为负数")
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
    timestamp = normalize_timestamp(payload.get("timestamp"))
    event_date = dt.datetime.fromisoformat(timestamp).date()
    session_id = payload.get("session_id")
    if session_id:
        existing, _ = read_json_lines(root / "events.jsonl")
        valid_session = any(
            item.get("kind") == "study_session" and item.get("event_id") == session_id
            for item in existing
        )
        if not valid_session:
            raise QinganError("session_id 未指向已有学习会话")
    tags = payload.get("tags", [])
    if not isinstance(tags, list):
        raise QinganError("tags 必须是数组")
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "kind": "question_attempt",
        "timestamp": timestamp,
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
    if duration is not None and (not isinstance(duration, (int, float)) or duration < 0):
        raise QinganError("duration_seconds 必须是非负数字")
    attachment = payload.get("attachment_path")
    if attachment:
        event["attachment_path"] = store_attachment(root, attachment, question_id)
    append_json_line(root / "events.jsonl", event)
    return event


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
            if event.get("rating") in {"good", "easy"}:
                state["successful_dates"].append(event["timestamp"][:10])
            state["status"] = event.get("status", state["status"])
    return states


def rate_review(root, question_id, rating, when=None):
    load_profile(root)
    if rating not in VALID_RATINGS:
        raise QinganError("rating 必须是 again、hard、good 或 easy")
    events, _ = read_json_lines(root / "events.jsonl")
    states = latest_review_state(events)
    if question_id not in states:
        raise QinganError("找不到该 question_id")
    state = states[question_id]
    current = int(state["stage"])
    if rating == "again":
        stage = 0
    elif rating == "hard":
        stage = current
    elif rating == "good":
        stage = min(current + 1, len(REVIEW_INTERVALS) - 1)
    else:
        stage = min(current + 2, len(REVIEW_INTERVALS) - 1)
    timestamp = normalize_timestamp(when)
    event_date = dt.datetime.fromisoformat(timestamp).date()
    successful_dates = set(state["successful_dates"])
    if rating in {"good", "easy"}:
        successful_dates.add(event_date.isoformat())
    status = "stable" if len(successful_dates) >= 2 and stage >= 2 else "retesting"
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "kind": "review_result",
        "timestamp": timestamp,
        "question_id": question_id,
        "module": state.get("module"),
        "rating": rating,
        "review_stage": stage,
        "status": status,
        "next_due": (event_date + dt.timedelta(days=REVIEW_INTERVALS[stage])).isoformat(),
    }
    append_json_line(root / "events.jsonl", event)
    return event


def due_reviews(root, on_date=None, limit=10):
    load_profile(root)
    day = parse_date(on_date) if on_date else dt.date.today()
    events, invalid = read_json_lines(root / "events.jsonl")
    states = latest_review_state(events)
    due = []
    for state in states.values():
        if state["status"] == "stable" or not state.get("next_due"):
            continue
        if parse_date(state["next_due"]) <= day:
            due.append(state)
    due.sort(key=lambda item: (item["next_due"], item.get("module") or ""))
    return {"date": day.isoformat(), "due": due[: max(0, limit)], "invalid_lines": invalid}


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


def attempt_metrics(events, start, end):
    attempts = []
    sessions = []
    reviews = []
    for event in events:
        stamp = event.get("timestamp", "")[:10]
        try:
            day = parse_date(stamp)
        except QinganError:
            continue
        if start <= day <= end:
            if event.get("kind") == "question_attempt":
                attempts.append(event)
            elif event.get("kind") == "study_session":
                sessions.append(event)
            elif event.get("kind") == "review_result":
                reviews.append(event)
    by_module = defaultdict(lambda: {"attempts": 0, "correct": 0, "errors": 0})
    error_types = Counter()
    for event in attempts:
        if event.get("session_id"):
            continue
        module = event.get("module") or "unknown"
        by_module[module]["attempts"] += 1
        if event.get("correct") is True:
            by_module[module]["correct"] += 1
        else:
            by_module[module]["errors"] += 1
            error_types[event.get("error_type", "unknown")] += 1
    for event in sessions:
        module = event.get("module") or "unknown"
        session_attempts = int(event.get("attempts", 0))
        session_correct = int(event.get("correct_answers", 0))
        by_module[module]["attempts"] += session_attempts
        by_module[module]["correct"] += session_correct
        by_module[module]["errors"] += session_attempts - session_correct
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
        "review_count": len(reviews),
        "by_module": normalized_modules,
        "error_types": dict(error_types),
    }


def weekly_report(root, end_date=None):
    profile = load_profile(root)
    end = parse_date(end_date) if end_date else dt.date.today()
    start = end - dt.timedelta(days=6)
    previous_end = start - dt.timedelta(days=1)
    previous_start = previous_end - dt.timedelta(days=6)
    events, invalid = read_json_lines(root / "events.jsonl")
    current = attempt_metrics(events, start, end)
    previous = attempt_metrics(events, previous_start, previous_end)
    weak = sorted(
        current["by_module"].items(),
        key=lambda item: (
            -item[1]["errors"],
            item[1]["accuracy"] if item[1]["accuracy"] is not None else 1.0,
            -item[1]["attempts"],
            item[0],
        ),
    )
    priority = weak[0][0] if weak and weak[0][1]["errors"] else None
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "exam_date": profile["exam_date"],
        "current": current,
        "previous": previous,
        "priority_module": priority,
        "priority_reason": (
            "本周错误数优先；并列时比较正确率与样本量" if priority else "尚无足够错题数据，先建立基线"
        ),
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
    report = weekly_report(root, end_date=end_date)
    info = status(root, today=end_date)
    current = report["current"]
    previous = report["previous"]
    attempts = current["attempts"]
    minutes = current["study_minutes"]
    completion = current["completion_rate"]
    accuracy = current["accuracy"]
    module_count = len(current["by_module"])
    correct_per_hour = (
        round(current["correct"] / (minutes / 60.0), 2)
        if minutes and module_count == 1
        else None
    )
    accuracy_delta = metric_delta(current, previous, "accuracy")

    evidence_checks = {
        "enough_current_attempts": attempts >= 30,
        "has_study_time": minutes > 0,
        "has_task_completion_data": current["planned_tasks"] > 0,
        "has_previous_baseline": previous["attempts"] >= 20,
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
            "note": "只在本周只有一个模块时返回；用于同类训练纵向比较，不跨模块排名",
        },
        "review_loop": {
            "reviews_this_week": current["review_count"],
            "open_reviews": info["open_review_count"],
            "status": "open-loop" if info["open_review_count"] and not current["review_count"] else "active",
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
    elif info["open_review_count"] and not current["review_count"]:
        bottleneck = "review-loop"
        next_action = "先清理到期错题并记录回测结果，暂不扩张新题型"
    elif accuracy_delta is not None and accuracy_delta < -0.05:
        bottleneck = "method"
        next_action = "正确率在可比周期中下降；选择错误最多的一个题型，回到识别信号和固定步骤后做近变式"
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
            "completion_rate_delta": metric_delta(current, previous, "completion_rate"),
            "study_minutes_delta": metric_delta(current, previous, "study_minutes"),
        },
        "bottleneck": bottleneck,
        "next_action": next_action,
        "warning": "这是一份训练过程诊断，不是能力分数；样本条件变化时不要直接比较。",
    }


def status(root, today=None):
    profile = load_profile(root)
    day = parse_date(today) if today else dt.date.today()
    exam_day = parse_date(profile["exam_date"])
    days_left = (exam_day - day).days
    events, invalid = read_json_lines(root / "events.jsonl")
    review_states = latest_review_state(events)
    return {
        "profile": profile,
        "days_left": days_left,
        "phase": phase_for(days_left),
        "event_count": len(events),
        "open_review_count": sum(1 for value in review_states.values() if value["status"] != "stable"),
        "stable_review_count": sum(1 for value in review_states.values() if value["status"] == "stable"),
        "invalid_lines": invalid,
    }


def today_plan(root, today=None):
    info = status(root, today=today)
    day = parse_date(today) if today else dt.date.today()
    if info["phase"] == "exam-passed":
        return {
            "date": day.isoformat(),
            "phase": info["phase"],
            "days_left": info["days_left"],
            "blocks": [],
            "required_action": "考试日期已过，请运行 update-profile 更新档案后再生成训练计划",
        }
    due = due_reviews(root, day.isoformat(), limit=20)["due"]
    report = weekly_report(root, end_date=day.isoformat())
    priority = report.get("priority_module") or "当前最弱模块"
    study_days = normalize_study_days(info["profile"].get("study_days_per_week", 6))
    life_mode = info["profile"].get("life_mode", "flexible")
    normalize_life_mode(life_mode)
    daily_budget = max(3, int(round(float(info["profile"]["hours_per_week"]) * 60 / study_days)))
    review_minutes = min(max(1, len(due) * 5), max(1, daily_budget // 4))
    weakness_minutes = max(1, int(round((daily_budget - review_minutes) * 0.6)))
    transfer_minutes = daily_budget - review_minutes - weakness_minutes
    blocks = [
        {
            "kind": "due-review",
            "duration_minutes": review_minutes,
            "task": "完成 %d 道到期错题回测" % len(due),
            "done_when": "逐题给出回测评级；无到期题时完成方法主动回忆",
        },
        {
            "kind": "weakness",
            "duration_minutes": weakness_minutes,
            "task": "训练 %s，并记录第一个错误环节" % priority,
            "done_when": "达到预设时间上限并留下可回测的最小修正",
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
        "blocks": blocks,
    }


def minimum_day_plan(root, today=None, minutes=20):
    """Return a deliberately small plan for a low-energy or overloaded day."""
    info = status(root, today=today)
    day = parse_date(today) if today else dt.date.today()
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
    due = due_reviews(root, day.isoformat(), limit=3)["due"]
    report = weekly_report(root, end_date=day.isoformat())
    priority = report.get("priority_module") or "最熟悉的已学模块"
    life_mode = info["profile"].get("life_mode", "flexible")
    normalize_life_mode(life_mode)
    settle_minutes = min(3, max(1, budget // 8))
    recall_minutes = min(max(1, len(due) * 3), max(1, (budget - settle_minutes) // 3))
    action_minutes = budget - settle_minutes - recall_minutes
    return {
        "date": day.isoformat(),
        "phase": info["phase"],
        "minutes": budget,
        "message": "今天不追欠账，只保住节奏；完成这一小轮就算有效训练。",
        "life_mode": life_mode,
        "schedule_guidance": LIFE_MODE_GUIDANCE[life_mode],
        "blocks": [
            {
                "kind": "settle",
                "duration_minutes": settle_minutes,
                "task": "放下总进度，只写出今天能控制的一件事",
            },
            {
                "kind": "gentle-recall",
                "duration_minutes": recall_minutes,
                "task": "回测 %d 道到期错题；无到期题时口述一个已学方法" % len(due),
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
    info = status(root, today=end_date)
    if info["phase"] == "exam-passed":
        return {
            "phase": info["phase"],
            "days_left": info["days_left"],
            "weekly_budget_minutes": 0,
            "lanes": [],
            "required_action": "考试日期已过，请更新档案后再生成周计划",
        }
    report = weekly_report(root, end_date=end_date)
    life_mode = info["profile"].get("life_mode", "flexible")
    normalize_life_mode(life_mode)
    modules = sorted(
        report["current"]["by_module"].items(),
        key=lambda item: (-item[1]["attempts"], item[0]),
    )
    focus = report["priority_module"] or "综合基线诊断"
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
        "evidence": "recent-training-data" if report["current"]["attempts"] else "temporary-baseline",
        "lanes": [
            {"kind": "focus", "module": focus, "minutes": focus_minutes},
            {"kind": "maintain", "module": maintenance, "minutes": maintenance_minutes},
            {"kind": "review-and-mock", "module": "到期回测与限时综合", "minutes": review_minutes},
        ],
        "pause": pause,
        "priority_reason": report["priority_reason"],
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
    for relative in ("profile.json", "events.jsonl", "materials/index.jsonl"):
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
