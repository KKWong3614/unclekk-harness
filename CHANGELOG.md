# Changelog

## v1.0.5 — 2026-07-30
独立审计长第 4 轮（NEEDS_REVISION → 主 Hermes 抽验修复）
- P0-1: validate 拦截 `[LLM:` placeholder，INGEST→PLAN skeleton 现在报错而非放行（修复文档与代码语义裂缝）
- P0-2: SKILL.md 文档 33→39 测试数系统性修正（自测/文件结构/变更记录三处对齐）
- P1-2: SKILL.md stage 字段枚举补充 `init`/`recovered`
- 新增 2 项测试（39/39）

## v1.0.4 — 2026-07-27
独立审计长第 3 轮（触顶确认）
- stage-gate 前置检查（review 必须 exec/review 阶段，settle 必须 review/audit + 非空 final-output）
- --final-output 空阻断
- +4 测试（37/37）；失败模式表 #10
- 真实 Δ = +0.63（<2），触顶判定触发

## v1.0.4-remediation — 2026-07-27
触顶后修复
- _load(recover=True) 死代码 → 激活 --recover CLI flag
- stage_exec JSONDecodeError/ValueError → _recover_state_from_log
- +4 测试（37/37）

## v1.0.3 — 2026-07-27
独立审计长第 2 轮
- workspace abspath 归一 + 可写性验证
- executor_prompt workspace 约束对齐
- 修复 ## 文件结构重复标题
- +2 测试

## v1.0.2 — 2026-07-27
独立审计长第 1 轮
- condition 沙箱属性链防护
- 删除 library.py 死引用
- +10 测试

## v1.0.1 — 2026-07-26
首轮优化
- 失败模式四列表
- 反例黑名单
- 否定性章节
- condition AST allowlist 沙箱
- state 恢复路径（_recover_state_from_log）
- audit 填充指导 6 个

## v1.0.0 — 2026-07-26
初版
- 6 阶段传送带（INGEST → PLAN → EXEC → REVIEW → AUDIT → SETTLE）
- 17 项回归测试
- 2 个 prompt 模板（executor + reviewer）
- 端到端 CLI 验证
