# 青岸计划·考公冲刺教练

面向只剩数周到数月备考时间的大学生，把考公训练做成一个可执行、可复盘的闭环：诊断、计划、专项训练、错题复盘、间隔回测和周度调参。

本仓库是 Codex 插件市场源。插件本体位于 [`plugins/qingan-gongkao-coach`](plugins/qingan-gongkao-coach)，包含 10 个可按意图自动触发的 Agent Skills 和一个零第三方依赖的本地效率管理引擎。

## 安装

发布 `v0.1.0` 后，可在 Codex 中运行：

```bash
codex plugin marketplace add XiaoSiKe/qingan-gongkao-coach --ref v0.1.0
codex plugin add qingan-gongkao-coach@qingan
```

也可以从 GitHub Release 下载 ZIP。其他兼容 Agent Skills 的客户端可复制插件内 `skills/` 下的所需目录。

## 开发验证

```bash
python3 plugins/qingan-gongkao-coach/scripts/validate.py
python3 -m unittest discover -s plugins/qingan-gongkao-coach/tests -v
python3 plugins/qingan-gongkao-coach/scripts/build_release.py
```

完整使用、数据和来源说明见[插件 README](plugins/qingan-gongkao-coach/README.md)。

## 原则

- 最新政策、公告、法律和时政必须查官方来源。
- 模拟题不冒充真题，申论训练分不冒充官方评分。
- 看不清的截图和残缺题面不补全猜测。
- 不打包付费课程、盗版题库、无许可证内容或教师课程转写。
- 学习记录默认只保存在用户本机，项目不采集遥测。

MIT License。第三方来源和吸收边界见 [`THIRD_PARTY_NOTICES.md`](plugins/qingan-gongkao-coach/THIRD_PARTY_NOTICES.md)。
