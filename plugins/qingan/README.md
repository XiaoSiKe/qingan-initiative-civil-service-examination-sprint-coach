# 🌊 青岸计划·考公冲刺教练

## 一万年太久，只争朝夕！

**Qing'an Initiative · Civil Service Examination Sprint Coach**

一个以大学生日常为默认场景、同时适配所有考生的统一考公 Skill。它会在内部自动选择诊断、生活适配、计划、资料、错题、情绪韧性、言语、图推、逻辑、数资、政治常识或申论协议；用户只需面对“青岸计划”这一个入口。

```text
诊断 → 今日三项 → 单题训练 → 错因卡 → 间隔回测 → 周度调参
```

## ✨ 核心能力

| 能力 | 结果 |
|---|---|
| 冲刺诊断与计划 | 阶段、唯一主攻方向、三个可完成训练块 |
| 大学生与通用适配 | 课程/实习/论文/工作/照护约束、碎片任务与整块任务 |
| 学科专项训练 | 证据链、最小修正、立即变式与间隔回测 |
| 资料与错题管理 | 可追溯索引、错因卡、二刷状态 |
| 学习方法系统 | 检索、间隔、交错、自我解释、冲刺卡和短轮自测 |
| 情绪韧性系统 | 接住低谷、停止羞辱式激励、最低可行训练日 |
| 申论批改 | 材料位置映射、遗漏/错位诊断、最小修改版 |
| 时政与制度核验 | 当前官方原文、发布日期、适用范围 |
| 本地效率引擎 | 日计划、周计划、周报、复习队列与导出 |

## 💬 使用示例

```text
青岸计划，我还有 60 天省考，每周 20 小时，帮我建立冲刺路径。
这道削弱题我选了 B，为什么错？帮我安排二刷。
根据上传的讲义生成有页码来源的学习卡，先不要给答案。
批改我的申论概括题；材料不全时不要报精确分。
今天模考掉了很多分，我很难受。先别加码，帮我找回一点掌控感。
```

## ♻️ 从旧版升级

如果仍使用 v0.1.0，请先运行 `codex plugin remove qingan-gongkao-coach@qingan` 移除旧插件，再安装当前统一入口。v0.2.0 用户使用同一插件标识更新即可。若使用 `npx skills`，可运行 `npx skills update`；旧的多 Skill 安装需要先通过 `npx skills remove`（全局安装加 `-g`）清除。

## ⚙️ 本地效率引擎

Python 3.9+，无第三方依赖。默认保存到 `~/.qingan-gongkao/`，也可使用 `QINGAN_DATA_DIR` 或 `--data-dir` 覆盖。

```bash
python3 scripts/qingan.py init --exam-type national --exam-date 2026-11-29 --hours-per-week 20
python3 scripts/qingan.py today
python3 scripts/qingan.py week-plan
python3 scripts/qingan.py minimum-day --minutes 20
python3 scripts/qingan.py weekly
python3 scripts/qingan.py review-due
```

临时讲题不自动建档；只有用户明确要求记录时才写入。数据采用追加式事件存储，损坏行不会覆盖原文件，档案更新与迁移前会备份。

## 🧠 方法与来源

青岸重点研究了 [`cxs885187-create/--skill`](https://github.com/cxs885187-create/--skill) 的材料分级、骨架先行、专题卡、短轮自测、自评校准、受挫熔断和增量更新思路，并围绕大学生考公冲刺独立实现。该来源没有独立许可证文件，因此只作概念研究，不复制其指令和模板。

学习系统结合检索练习、分散练习、交错练习、费曼式自我解释、康奈尔问题区、刻意练习、双编码与实施意图；策略系统把实事求是、实践—认识—再实践、抓主要矛盾、具体问题具体分析、集中优势各个击破和战略持久/局部速决转化为训练动作。完整依据与边界在统一 Skill 的 `learning-and-strategy.md`。

## ❤️ 情绪支持

低分、拖延、过载或自我怀疑时，青岸先回应具体处境，再把任务缩到 10–20 分钟的小闭环；完成即可停止，不把欠账搬到明天。持续耗竭时优先现实支持，出现安全风险时停止备考推动。本 Skill 不替代心理治疗或危机服务。

## 🛡️ 训练边界

- 最新报名、职位、政策、法律、大纲和时政必须核对官方原文。
- 模拟题标记 `[AI仿题]`，申论参考分不冒充官方评分。
- 图片、题干、选项或材料不完整时不补全猜测。
- 不收录付费课程转写、盗版题库或来源不明的大规模材料。
- 不承诺精确提分或录用结果。

## ✅ 开发验证

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/check_upstreams.py --offline
python3 scripts/build_release.py
```

项目采用 MIT License。外部方法来源与许可证边界见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
