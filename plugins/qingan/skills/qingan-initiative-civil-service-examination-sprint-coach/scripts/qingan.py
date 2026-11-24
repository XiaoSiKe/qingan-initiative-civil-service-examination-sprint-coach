#!/usr/bin/env python3
"""Command-line entry point for Qing'an Initiative."""

from __future__ import print_function

import argparse
import json
import sys

from qingan_core import (
    QinganError,
    data_root,
    doctor,
    due_reviews,
    efficiency_report,
    export_data,
    init_profile,
    migrate,
    minimum_day_plan,
    rate_review,
    record_error,
    record_session,
    register_material,
    status,
    today_plan,
    update_profile,
    week_plan,
    weekly_report,
)

from qingan_interview import interview_history, record_interview
from qingan_recovery import recover_events


def load_payload(source):
    try:
        if source == "-":
            return json.load(getattr(sys.stdin, "buffer", sys.stdin))
        with open(source, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QinganError("无法读取 JSON 输入：%s" % exc)


def emit(value, stream=None):
    """Write UTF-8 JSON even when a Windows console reports a legacy code page."""
    destination = stream or sys.stdout
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    binary = getattr(destination, "buffer", None)
    if binary is not None:
        binary.write(payload.encode("utf-8"))
        binary.flush()
    else:
        destination.write(payload)
        destination.flush()


def parser():
    result = argparse.ArgumentParser(description="青岸计划本地效率管理引擎")
    result.add_argument("--data-dir", help="覆盖 QINGAN_DATA_DIR 和默认数据目录")
    commands = result.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="初始化备考档案")
    init.add_argument("--exam-type", required=True, choices=("national", "province", "institution"))
    init.add_argument("--exam-date", required=True)
    init.add_argument("--hours-per-week", required=True, type=float)
    init.add_argument("--province")
    init.add_argument("--study-days-per-week", type=int, default=6)
    init.add_argument(
        "--life-mode",
        choices=("campus", "working", "full-time", "caregiving", "flexible"),
        default="flexible",
    )

    update = commands.add_parser("update-profile", help="备份后更新备考档案")
    update.add_argument("--exam-type", choices=("national", "province", "institution"))
    update.add_argument("--exam-date")
    update.add_argument("--hours-per-week", type=float)
    update.add_argument("--province")
    update.add_argument("--study-days-per-week", type=int)
    update.add_argument(
        "--life-mode",
        choices=("campus", "working", "full-time", "caregiving", "flexible"),
    )

    commands.add_parser("doctor", help="检查数据目录与记录完整性")
    status_parser = commands.add_parser("status", help="查看总体状态")
    status_parser.add_argument("--date")
    today = commands.add_parser("today", help="生成今天的三个优先训练块")
    today.add_argument("--date")
    today.add_argument("--minutes", type=int, help="今天实际还能学的分钟数，0 表示休息")
    week = commands.add_parser("week-plan", help="按证据生成主攻、保持与暂停项")
    week.add_argument("--end-date")
    minimum = commands.add_parser("minimum-day", help="生成低能量日的最低可行训练计划")
    minimum.add_argument("--date")
    minimum.add_argument("--minutes", type=int, default=20)

    session = commands.add_parser("record-session", help="追加学习会话")
    session.add_argument("--json", required=True, dest="json_source")
    error = commands.add_parser("record-error", help="追加错题与首次复习日期")
    error.add_argument("--json", required=True, dest="json_source")

    due = commands.add_parser("review-due", help="列出到期错题")
    due.add_argument("--date")
    due.add_argument("--limit", type=int, default=10)

    rate = commands.add_parser("rate-review", help="记录错题回测结果")
    rate.add_argument("--question-id", required=True)
    rate.add_argument("--rating", required=True, choices=("again", "hard", "good", "easy"))
    rate.add_argument("--timestamp")

    interview = commands.add_parser("record-interview", help="保存面试短证据和二答关系")
    interview.add_argument("--json", required=True, dest="json_source")
    interview_log = commands.add_parser("interview-history", help="按记录 ID 读面试初答与二答")
    interview_log.add_argument("--record-id", required=True)

    weekly = commands.add_parser("weekly", help="生成最近七天与前七天对比")
    weekly.add_argument("--end-date")
    evaluate = commands.add_parser("evaluate", help="评估执行、正确率、时间效率、回测与证据质量")
    evaluate.add_argument("--end-date")
    material = commands.add_parser("register-material", help="登记用户学习资料及哈希")
    material.add_argument("--json", required=True, dest="json_source")
    export = commands.add_parser("export", help="导出报告或事件数据")
    export.add_argument("--format", required=True, choices=("markdown", "csv"))
    export.add_argument("--output", required=True)
    commands.add_parser("migrate", help="备份并迁移数据")
    commands.add_parser("recover-events", help="无损恢复粘连的完整学习事件")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    root = data_root(args.data_dir)
    try:
        if args.command == "init":
            value = init_profile(
                root,
                args.exam_type,
                args.exam_date,
                args.hours_per_week,
                args.province,
                args.study_days_per_week,
                args.life_mode,
            )
        elif args.command == "update-profile":
            value = update_profile(
                root,
                args.exam_type,
                args.exam_date,
                args.hours_per_week,
                args.province,
                args.study_days_per_week,
                args.life_mode,
            )
        elif args.command == "doctor":
            value = doctor(root)
        elif args.command == "status":
            value = status(root, today=args.date)
        elif args.command == "today":
            value = today_plan(root, today=args.date, minutes=args.minutes)
        elif args.command == "week-plan":
            value = week_plan(root, end_date=args.end_date)
        elif args.command == "minimum-day":
            value = minimum_day_plan(root, today=args.date, minutes=args.minutes)
        elif args.command == "record-session":
            value = record_session(root, load_payload(args.json_source))
        elif args.command == "record-error":
            value = record_error(root, load_payload(args.json_source))
        elif args.command == "review-due":
            value = due_reviews(root, on_date=args.date, limit=args.limit)
        elif args.command == "rate-review":
            value = rate_review(root, args.question_id, args.rating, when=args.timestamp)
        elif args.command == "record-interview":
            value = record_interview(root, load_payload(args.json_source))
        elif args.command == "interview-history":
            value = interview_history(root, args.record_id)
        elif args.command == "weekly":
            value = weekly_report(root, end_date=args.end_date)
        elif args.command == "evaluate":
            value = efficiency_report(root, end_date=args.end_date)
        elif args.command == "register-material":
            value = register_material(root, load_payload(args.json_source))
        elif args.command == "export":
            value = export_data(root, args.output, args.format)
        elif args.command == "migrate":
            value = migrate(root)
        elif args.command == "recover-events":
            value = recover_events(root)
        else:
            raise QinganError("未知命令")
        emit(value)
        return 0
    except QinganError as exc:
        emit({"ok": False, "error": str(exc)}, stream=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
