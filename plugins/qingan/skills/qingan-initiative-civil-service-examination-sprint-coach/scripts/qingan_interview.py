"""Read and write local, excerpt-only interview feedback."""

import uuid

from qingan_core import QinganError, append_json_line, read_json_lines, utc_now


FIELDS = {
    "question", "criterion", "evidence", "feedback", "result",
    "modality", "duration_seconds", "delivery", "revises", "event_id",
}
DELIVERY = {
    "transcript": set(),
    "audio": {"pace", "pause", "tone"},
    "video": {"pace", "pause", "tone", "eye_contact", "gesture"},
}
RESULTS = {"needs_revision", "partial", "met"}


def _text(payload, key, limit):
    value = payload.get(key)
    if not isinstance(value, str) or not 0 < len(value.strip()) <= limit:
        raise QinganError("%s 必须是 1 到 %d 个字符的文本" % (key, limit))
    return value.strip()


def _read(root):
    return read_json_lines(root / "interview.jsonl")


def record_interview(root, payload):
    if not isinstance(payload, dict) or set(payload) - FIELDS:
        raise QinganError("面试只能保存题目、判据、短摘句与反馈等登记字段，不接收作答全文")
    rows, _ = _read(root)
    by_id = {row.get("record_id"): row for row in rows}
    parent_id = _text(payload, "revises", 120) if "revises" in payload else None
    parent = by_id.get(parent_id) if parent_id else None
    if parent_id and parent is None:
        raise QinganError("找不到要复评的初答记录，请先核对 interview-history")

    question = _text(payload, "question", 1800) if "question" in payload or not parent else parent["question"]
    criterion = _text(payload, "criterion", 240) if "criterion" in payload or not parent else parent["criterion"]
    if parent and (parent["question"] != question or parent["criterion"] != criterion):
        raise QinganError("二答需沿用原题和原判据；更换题目或判据时请单独登记")

    modality = payload.get("modality", "transcript")
    if not isinstance(modality, str) or modality not in DELIVERY:
        raise QinganError("modality 必须是 transcript、audio 或 video")
    delivery = payload.get("delivery", {})
    if not isinstance(delivery, dict) or not set(delivery).issubset(DELIVERY[modality]):
        raise QinganError("当前作答材料无法支撑这些声音或仪态观察")
    delivery = {key: _text(delivery, key, 160) for key in delivery}
    duration = payload.get("duration_seconds")
    if duration is not None and (type(duration) is not int or not 1 <= duration <= 3600):
        raise QinganError("duration_seconds 仅填写已测得的 1–3600 秒整数")
    result = payload.get("result")
    if not isinstance(result, str) or result not in RESULTS:
        raise QinganError("result 使用 needs_revision、partial 或 met")

    record_id = _text(payload, "event_id", 120) if "event_id" in payload else uuid.uuid4().hex
    row = {
        "record_id": record_id,
        "session_id": parent["session_id"] if parent else record_id,
        "revises": parent_id,
        "question": question,
        "criterion": criterion,
        "evidence": _text(payload, "evidence", 160),
        "feedback": _text(payload, "feedback", 600),
        "result": result,
        "modality": modality,
        "duration_seconds": duration,
        "delivery": delivery,
    }
    previous = by_id.get(record_id)
    if previous:
        if any(previous.get(key) != value for key, value in row.items()):
            raise QinganError("该 event_id 已保存不同的面试记录")
        return {"saved": False, "duplicate": True, "record": previous}
    row["recorded_at"] = utc_now()
    append_json_line(root / "interview.jsonl", row)
    return {"saved": True, "record": row}


def interview_history(root, record_id):
    rows, invalid = _read(root)
    target = next((row for row in rows if row.get("record_id") == record_id), None)
    if target is None:
        raise QinganError("找不到面试记录 ID")
    records = [row for row in rows if row.get("session_id") == target["session_id"]]
    return {
        "session_id": target["session_id"], "criterion": target["criterion"],
        "question": target["question"], "records": records, "invalid_lines": invalid,
        "comparison_basis": "按同题、同判据对照内容证据；声音和仪态受各稿材料类型限制。",
    }
