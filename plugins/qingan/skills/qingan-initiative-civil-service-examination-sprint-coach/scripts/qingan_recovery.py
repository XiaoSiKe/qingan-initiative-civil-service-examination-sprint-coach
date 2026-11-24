"""Lossless restoration of concatenated, otherwise complete study events."""

import hashlib
import json

from qingan_core import QinganError, atomic_write_bytes, load_profile, read_json_lines


def _complete_events(raw):
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise QinganError("日志不是完整的 UTF-8，不能无损拆分") from exc
    decoder = json.JSONDecoder()
    position = 0
    events = []
    identifiers = set()
    while position < len(content):
        if content[position].isspace():
            position += 1
            continue
        try:
            row, position = decoder.raw_decode(content, position)
        except (ValueError, TypeError) as exc:
            raise QinganError("日志包含无法完整解析的内容，已保留原件") from exc
        identifier = row.get("event_id") if isinstance(row, dict) else None
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise QinganError("日志包含缺少标识或重复标识的记录，不能自动判定")
        if not isinstance(row.get("kind"), str) or row.get("schema_version") != 1:
            raise QinganError("日志包含无法确认格式的事件，不能自动恢复")
        identifiers.add(identifier)
        events.append(row)
    return events


def recover_events(root):
    load_profile(root)
    path = root / "events.jsonl"
    if not path.is_file():
        raise QinganError("找不到 events.jsonl")
    rows, invalid = read_json_lines(path)
    if not invalid:
        return {"changed": False, "records": len(rows), "backup": None}
    original = path.read_bytes()
    rows = _complete_events(original)
    rendered = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    payload = rendered.encode("utf-8")
    if path.read_bytes() != original:
        raise QinganError("核对期间日志已变化，请重新检查")
    digest = hashlib.sha256(original).hexdigest()
    backup = root / "backups" / "recovery" / f"events.{digest}.jsonl.bak"
    if backup.exists() and backup.read_bytes() != original:
        raise QinganError("恢复备份与原始日志冲突")
    if not backup.exists():
        atomic_write_bytes(backup, original)
    atomic_write_bytes(path, payload)
    return {"changed": True, "records": len(rows), "backup": str(backup)}
