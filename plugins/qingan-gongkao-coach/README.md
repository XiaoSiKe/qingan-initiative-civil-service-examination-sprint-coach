# 青岸计划·考公冲刺教练

青岸是一组面向大学生的考公冲刺 Skills，重点不是堆知识，而是把有限时间转化为可验证训练：

```text
诊断 → 今日三项任务 → 单题训练 → 错因卡 → 间隔回测 → 周度调参
```

## 包含的 Skills

- `qingan-gongkao-coach`：总教练与跨模块路由
- `qingan-sprint-manager`：倒计时、日周计划和效率复盘
- `qingan-materials`：用户资料、题册和讲义整理
- `qingan-mistake-review`：截图/文字错题诊断与二刷
- `qingan-verbal`：言语理解与逻辑填空
- `qingan-figure`：图形推理与空间重构
- `qingan-logic`：定义、类比和逻辑判断
- `qingan-data-quant`：资料分析与数量关系
- `qingan-politics`：政治理论、常识、公基和时政
- `qingan-shenlun`：申论提点、组织、表达与批改

直接说“我还有 80 天考国考，每周能学 25 小时”，总教练会建立冲刺路径。明确问“这道削弱题为什么错”，则直接进入逻辑或错题复盘，无需记 Skill 名。

## 本地效率管理

运行环境为 Python 3.9+，不依赖第三方包。默认数据目录是 `~/.qingan-gongkao/`，可用 `QINGAN_DATA_DIR` 覆盖。

```bash
python3 scripts/qingan.py init \
  --exam-type national \
  --exam-date 2026-11-29 \
  --hours-per-week 25

python3 scripts/qingan.py status
python3 scripts/qingan.py update-profile --exam-date 2027-03-15 --hours-per-week 20
python3 scripts/qingan.py today
python3 scripts/qingan.py weekly
python3 scripts/qingan.py review-due
```

初始化只执行一次。临时讲题不会自动建档；只有用户明确要求记录、打卡或收录错题时才写入本地数据。

### 记录学习会话

```json
{
  "timestamp": "2026-09-09T12:00:00+08:00",
  "module": "资料分析",
  "duration_minutes": 45,
  "planned_tasks": 1,
  "completed_tasks": 1,
  "attempts": 20,
  "correct_answers": 16,
  "note": "增长率限时训练"
}
```

```bash
python3 scripts/qingan.py record-session --json session.json
```

### 记录错题

```json
{
  "module": "判断推理",
  "subtype": "削弱加强",
  "question": "用户提供的题干",
  "user_answer": "A",
  "correct_answer": "C",
  "error_type": "reasoning",
  "confidence": "high",
  "diagnosis": "把选项真实性当成了对论证的削弱作用",
  "correction": "先写论点与缺口，再比较选项作用",
  "source_type": "user-material",
  "source_ref": "错题册第 12 页"
}
```

```bash
python3 scripts/qingan.py record-error --json error.json
```

记录后返回稳定的 `question_id`。到期回测后执行：

```bash
python3 scripts/qingan.py rate-review \
  --question-id QUESTION_ID \
  --rating good
```

评分值为 `again`、`hard`、`good` 或 `easy`。复习间隔为 1、3、7、14、30 天；至少两个不同日期的成功回测才会标记稳定。

如果错题来自刚记录的整场练习，把 `record-session` 返回的 `event_id` 写入错题 JSON 的 `session_id`。周报会用整场成绩计算正确率，同时保留逐题错因，但不会重复计算该题。不存在的 `session_id` 会被拒绝。

## 数据与隐私

权威数据是 `profile.json`、追加式 `events.jsonl` 和 `materials/index.jsonl`。统计由事件重建；损坏行会被跳过并报告，不覆盖原文件。迁移前自动备份到 `backups/`。错题图片只在明确记录且提供 `attachment_path` 时复制到本地。

没有文件系统的客户端使用聊天模式：Skill 会输出可复制状态块，但不会假装已经持久化。项目没有云端后台、账号系统或遥测。

## 可信度边界

- `[官方]`：国家公务员局、中国政府网、中央部委或省级主管部门。
- `[用户材料]`：标注文件、页码或题目位置。
- `[许可开源方法]`：仅使用已登记且许可证兼容的内容。
- `[AI仿题]`：绝不称为真题。
- `[推断待核]`：证据不足或需要最新核验。

本项目不保证分数或录用结果。发现内容错误，请使用“内容纠错”Issue，并附来源、发布日期和适用考试。

## 开发与发布

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/check_upstreams.py --offline
python3 scripts/build_release.py
```

发布包只包含插件运行所需文件，不包含测试、缓存、用户数据或凭据。
