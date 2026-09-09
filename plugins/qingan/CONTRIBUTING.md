# Contributing

## 内容变更

涉及政策、法律、报名、考试大纲或时政的 PR 必须提供官方来源、发布日期、适用考试和核验日期。行业整理必须明确标为非官方口径。

涉及外部仓库时，先更新 `sources/upstreams.json`，说明许可证、固定提交和吸收模式。GPL、AGPL、未声明许可证、课程转写、OCR 讲义和来源不明题库不得复制进本仓库。

## 行为变更

修改 Skill 触发条件时，在 `evals/scenarios.json` 增加正例、口语化正例和冲突/负例。修改状态引擎时增加对应单元测试，并验证旧数据仍可读取或提供备份迁移。

## 提交前

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/check_upstreams.py --offline
python3 scripts/build_release.py
```
