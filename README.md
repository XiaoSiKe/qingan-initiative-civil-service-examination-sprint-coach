<div align="center">

# 🌊 青岸计划·考公冲刺教练

### Qing'an Initiative · Civil Service Examination Sprint Coach

**把有限的备考时间，变成每天都能完成、每周都能校准的上岸路径。**

[![CI](https://github.com/XiaoSiKe/qingan-initiative-civil-service-examination-sprint-coach/actions/workflows/ci.yml/badge.svg)](https://github.com/XiaoSiKe/qingan-initiative-civil-service-examination-sprint-coach/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/XiaoSiKe/qingan-initiative-civil-service-examination-sprint-coach?color=2F6F5E)](https://github.com/XiaoSiKe/qingan-initiative-civil-service-examination-sprint-coach/releases)
[![Agent Skill](https://img.shields.io/badge/Agent-Skill-6C47FF)](#-安装)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-black)](LICENSE)

1 个统一 Skill · 10 条内部能力路由 · 40 个行为场景 · 本地学习档案

</div>

---

青岸不是一份“看起来很努力”的日程表，也不是把十个助手堆到你的 Skill 列表里。

它是一个面向大学生的考公冲刺教练：你只需要描述眼前的问题——“还有 80 天怎么排”“这道削弱题为什么错”“帮我批改申论”——同一个 Skill 会自动选择对应训练协议，把计划、练习、反馈、错题和回测接成闭环。

```text
诊断起点 → 确定优先级 → 今日三项 → 单题训练 → 错因卡 → 间隔回测 → 周度调参
```

## 🧭 它能帮你做什么

| 场景 | 青岸会做什么 | 交付结果 |
|---|---|---|
| 🩺 首次诊断 | 结合考试日期、时间预算、模考与薄弱项建立临时基线 | 当前阶段、唯一主攻方向、第一周动作 |
| ⏱️ 冲刺管理 | 根据剩余天数和真实训练数据动态调参 | 今日三个训练块、周计划、保持项与暂停项 |
| 📚 资料整理 | 读取 PDF、讲义、笔记和题册，保留来源与页码 | 模块索引、学习卡、增量更新判断 |
| 🔁 错题复盘 | 沿知识、识别、审题、推理/计算、策略定位第一断点 | 错因卡、最小修正、二刷日期 |
| 📝 言语理解 | 用文本结构、语境和选项比较替代“凭语感” | 证据链、干扰项机制、下次检查 |
| 🧩 图形推理 | 先观察事实，再验证位置、样式、属性、数量与空间假设 | 可复核规律、反例检查、选项排除 |
| 🧠 判断推理 | 形式化定义、类比、条件、真假与论证关系 | 判据、关系链、选项作用强度 |
| 📊 资料与数量 | 先定关系和精度，再选估算、代入、赋值或方程 | 考场解法、误差边界、止损策略 |
| 🏛️ 政治与常识 | 区分稳定知识和易变事实，最新内容核对官方原文 | 易混辨析、选项排错、来源与核验日期 |
| ✍️ 申论 | 从材料找点、归类、组织和表达，不先套模板 | 材料映射、证据化批改、最小修改版 |

### 一个 Skill，为什么还能覆盖这些能力？

青岸采用渐进式加载：入口只保留共同规则和路由；识别到当前任务后，只读取相关的内部协议。用户看到的是一个 Skill，模型也不会把十个学科说明同时塞进上下文。

```text
你的自然语言请求
       ↓
青岸统一入口
       ↓
意图判断 ── 错题/计划/资料优先于学科关键词
       ↓
只加载本次需要的 1–2 份训练协议
       ↓
完成解题、训练、批改、计划或记录
```

## 🚀 安装

安装到当前项目：

```bash
npx skills add XiaoSiKe/qingan-initiative-civil-service-examination-sprint-coach \
  --skill qingan-initiative-civil-service-examination-sprint-coach -y
```

希望所有项目都能使用：

```bash
npx skills add XiaoSiKe/qingan-initiative-civil-service-examination-sprint-coach \
  --skill qingan-initiative-civil-service-examination-sprint-coach -g -y
```

在 Codex 中也可以按插件安装：

```bash
codex plugin marketplace add XiaoSiKe/qingan-initiative-civil-service-examination-sprint-coach --ref v0.2.0
codex plugin add qingan-initiative-civil-service-examination-sprint-coach@qingan
```

安装后新开一个会话，直接说“青岸计划，我还有 60 天省考，每周能学 20 小时”即可。更新已安装版本可运行 `npx skills update`。

<details>
<summary><strong>♻️ 从 v0.1.0 升级：清理旧的多 Skill 安装</strong></summary>

v0.2.0 更换了插件与 Skill 标识。为了避免旧入口继续显示，请先移除 v0.1.0，再安装新版。

如果此前通过 Codex 插件安装：

```bash
codex plugin remove qingan-gongkao-coach@qingan
codex plugin marketplace remove qingan
codex plugin marketplace add XiaoSiKe/qingan-initiative-civil-service-examination-sprint-coach --ref v0.2.0
codex plugin add qingan-initiative-civil-service-examination-sprint-coach@qingan
```

如果此前通过 `npx skills` 安装，运行 `npx skills remove`（全局安装则运行 `npx skills remove -g`），在交互列表中选中旧的 `qingan-*` 项全部移除，然后执行上面的新版 `npx skills add` 命令。

</details>

## 💬 直接这样使用

```text
青岸计划，我大四，距离国考还有 83 天，每周能学 18 小时，先帮我诊断。

我最近资料分析正确率 65%，判断推理 78%，申论还没完整写过，安排今天三项。

这道资料分析错题我选了 A，参考答案是 C，帮我找第一个错误断点并安排二刷。

根据我上传的讲义做一组言语学习卡，保留页码，先别给自测答案。

批改这道申论概括题：逐点对应材料，没有可靠评分依据就不要报精确分。
```

青岸会自动判断内部路径。你不需要记忆子模块名字，也不会在 Codex 里看到一排“青岸·某某教练”。

## 🗓️ 四阶段冲刺

| 剩余时间 | 默认重心 | 不做什么 |
|---|---|---|
| 61 天以上 | 方法基础、专项诊断、首次基线 | 用海量收藏代替训练 |
| 31–60 天 | 高频弱项、间隔回测、模块限时 | 每天平均用力 |
| 8–30 天 | 整卷模拟、时间策略、重复错因修复 | 大规模扩张新体系 |
| 0–7 天 | 已学高频、错题回测、考场流程 | 临时追逐偏难怪题 |

阶段只是默认值。真实错题、正确率、用时和任务完成率会继续修正优先级；没有足够数据时，青岸会明确标记“临时计划”，不会制造精确提分预测。

## ⚙️ 本地效率管理

可选的本地引擎使用 Python 3.9+，不依赖第三方包。它记录学习事件而不是覆盖历史，并从事件重建日计划、周报和错题回测状态。

```bash
cd plugins/qingan-initiative-civil-service-examination-sprint-coach

python3 scripts/qingan.py init \
  --exam-type national \
  --exam-date 2026-11-29 \
  --hours-per-week 20

python3 scripts/qingan.py today
python3 scripts/qingan.py week-plan
python3 scripts/qingan.py weekly
python3 scripts/qingan.py review-due
```

默认数据目录为 `~/.qingan-gongkao/`，也可通过 `QINGAN_DATA_DIR` 或 `--data-dir` 指定。只有用户明确要求建档、打卡、收录错题或登记资料时才写入；普通讲题不会自动保存。

<details>
<summary><strong>📌 记录一次学习会话</strong></summary>

```json
{
  "timestamp": "2026-09-09T12:00:00+08:00",
  "module": "资料分析",
  "duration_minutes": 45,
  "planned_tasks": 2,
  "completed_tasks": 2,
  "attempts": 20,
  "correct_answers": 16,
  "note": "增长率限时训练"
}
```

```bash
python3 scripts/qingan.py record-session --json session.json
```

</details>

<details>
<summary><strong>🔁 记录错题并完成二刷</strong></summary>

```json
{
  "module": "判断推理",
  "subtype": "削弱加强",
  "question": "用户提供的题干",
  "user_answer": "A",
  "correct_answer": "C",
  "error_type": "reasoning",
  "confidence": "high",
  "diagnosis": "把选项真实性当成了削弱作用",
  "correction": "先写论点与缺口，再比较选项作用",
  "source_type": "user-material",
  "source_ref": "错题册第 12 页"
}
```

```bash
python3 scripts/qingan.py record-error --json error.json
python3 scripts/qingan.py rate-review --question-id QUESTION_ID --rating good
```

回测等级为 `again`、`hard`、`good`、`easy`；复习间隔为 1、3、7、14、30 天。至少两个不同日期的成功回测才会标记稳定。

</details>

## 🛡️ 可信度与边界

- `[官方]`：国家公务员局、中国政府网、中央部委或省级主管部门的当前原文。
- `[用户材料]`：保留文件、页码或题目位置，不把培训材料自动当官方答案。
- `[许可开源方法]`：只吸收已登记、许可证兼容且经过独立重写的方法。
- `[AI仿题]`：必须明确标记，不冒充真题。
- `[推断待核]`：证据不足或需要当前信息核验。

看不清的截图、残缺题面和模糊数字不会被补全猜测；申论训练分不冒充官方评分；项目不收录盗版题库、付费课程转写或来源不明的大规模材料。

## 🔒 数据与隐私

权威数据是本地的 `profile.json`、追加式 `events.jsonl` 与 `materials/index.jsonl`。损坏记录会被跳过并报告，不覆盖原文件；迁移和档案更新前会自动备份。项目没有账号系统、云端后台或遥测。

## ✅ 质量与发布

```bash
python3 plugins/qingan-initiative-civil-service-examination-sprint-coach/scripts/validate.py
python3 -m unittest discover -s plugins/qingan-initiative-civil-service-examination-sprint-coach/tests -v
python3 plugins/qingan-initiative-civil-service-examination-sprint-coach/scripts/check_upstreams.py --offline
python3 plugins/qingan-initiative-civil-service-examination-sprint-coach/scripts/build_release.py
```

验证覆盖单 Skill 结构、10 条内部路由、40 个正例/冲突/负例场景、学习档案、日周计划、错题间隔回测、材料哈希、损坏数据容错、跨平台兼容和可复现发布包。

方法来源、许可证和吸收边界见 [第三方声明](plugins/qingan-initiative-civil-service-examination-sprint-coach/THIRD_PARTY_NOTICES.md)，参与维护见 [贡献指南](plugins/qingan-initiative-civil-service-examination-sprint-coach/CONTRIBUTING.md)。

---

<div align="center">

🌱 不追求“今天学了很多”，只追求“下一次能独立做对”。

MIT License

</div>
