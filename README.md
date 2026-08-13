# UncleKK Harness 端到端流水线编排

> 把规划/执行/审计串成可审计、可恢复、可暂停的 6 阶段端到端流水线（INGEST→PLAN→EXEC→REVIEW→AUDIT→SETTLE）。

Orchestrates tasks into auditable, resumable pipelines.

## 安装

将此技能克隆到你的 WorkBuddy 技能目录：

```bash
git clone https://github.com/KKWong3614/unclekk-harness.git "$HOME/.workbuddy/skills/unclekk-harness"
```

或下载 Release 中的 zip，解压到技能目录即可。

## 目录结构

```
unclekk-harness/
├── SKILL.md      # 技能主文件（含 frontmatter）
├── README.md     # 本文件
├── LICENSE       # MIT 许可证
├── references/   # 参考文档（如有）
├── scripts/      # 可执行脚本（如有）
└── templates/    # 模板（如有）
```

## 版本

当前版本：`1.0.5`

## 许可证

[MIT](LICENSE) © 2026 KK大叔 (UncleKK)
