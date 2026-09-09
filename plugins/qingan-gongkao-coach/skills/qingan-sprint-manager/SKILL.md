---
name: qingan-sprint-manager
description: 管理大学生考公冲刺时间与训练效率。用于只剩几天或几个月、制定日周计划、今天学什么、学习打卡、进度查询、周复盘、薄弱模块排序和计划调整。不要用它直接讲解一道具体题。
license: MIT
metadata:
  version: "0.1.0"
  language: zh-CN
---

# 青岸冲刺管理

把备考数据转成下一步行动，而不是输出漂亮但无法执行的时间表。

## 工作流

1. 读取考试日期、每周可用时间、最近训练和到期错题。
2. 运行 `python3 <plugin-root>/scripts/qingan.py status`、`today` 或 `weekly`。
3. 按剩余天数选择阶段，并只安排三个优先块：到期回测、最高收益弱项、限时综合训练。
4. 周度复盘比较本周与前一周，说明继续、加码、降级或暂停哪一项。
5. 用户明确打卡时，用 `record-session --json` 记录并保留返回的 `event_id`；随后记录该场错题时将它作为 `session_id`，避免重复计数。闲聊和临时建议不自动写入。

详细规则见 [references/sprint-protocol.md](references/sprint-protocol.md)。

## 输出要求

- 先给剩余天数、当前阶段和本周唯一主攻方向。
- 每项任务写清时长上限、题量或交付物、完成判据。
- 数据不足时写“临时计划”，不要制造精确提升预测。
- 计划落后时重排剩余任务，不把欠账机械搬到第二天。
- 任何建议都不得挤占睡眠或正常上课等基本约束。
