# 6 层深度审计方法论

用于独立第三方审计长对 orchestrator 类 skill 做全维度深度审计。
由独立 leaf agent 执行，主 Agent 零预读、零评分、零方向。

---

## L0 — 否定性假设门禁（P0 命中即 FAIL）

问 3 个问题：
1. 是否依赖已不存在的外部服务/工具？
2. 是否引用了跨生态的 Agent 专有工具名？
3. 是否假设了特定 runtime（Hermes vs WorkBuddy vs Claude Code）的存在？

扫 8 条架构红线：
- 双存储冗余
- 向量搜索缺失
- 过度工程化（脚本数 > 功能数 × 3）
- 与已有 skill 功能重叠 > 50%
- API 凭据暴露
- 条件代码路径不可达
- 测试覆盖 < 50%
- 文档与实际代码不符

P0 命中任意一条 → 结论 FAIL，跳过后续 L1-L5。

## L1 — 清单审计（grep-able，零方差）

逐项 PASS/FAIL + 证据：
- 所有引用 scripts/templates/references 文件名逐个确认存在
- 命令行示例参数名与 argparse 注册一致
- 所有 CLI 子命令在 main() 里有 dispatch
- 所有阶段名称与 stage_* 函数名一致
- 所有 Python 示例代码语法正确、能实际运行
- SKILL.md 版本号与 frontmatter version 一致
- evolution-log.md 所有版本有 results.tsv 条目
- SKILL.md JSON schema 与 harness.py 实际输出一致

## L2 — 序数评分（0-3 级制）

0=缺失，1=表面存在，2=可用，3=生产级。每维度带证据引用（文件:行号）。

维度：安全、完整性、可执行性、可追溯性、文档一致性、测试覆盖。

## L3 — TRACE 验证（端到端流程追踪）

- 每阶段：输入格式 → 函数签名 → 输出格式 三者一致
- _atomic_write 确实用了 temp+rename
- _load(recover=True) 路径可触发且可恢复
- condition 沙箱 allowlist 只允许白名单标识符
- CLI 未匹配命令有 fallback

## L4 — 跨 runtime 集成测试

实际执行全部 CLI 命令并验证输出。重点：
- condition 沙箱（合法条件 + 非法属性链逃逸）
- state 恢复（valid / missing fields / corrupt JSON）
- 空 --final-output 阻断
- stage-gate（跨阶段调用拒绝）

## L5 — 版本 diff 与退化检测

- 对比当前版本与初版的核心差异
- 检查功能退化（旧功能不可用）
- 检查 results.tsv 分数趋势（棘轮是否成立：新分 >= 旧分）

## 输出要求

- L0-L5 每层详细结果 + PASS/FAIL + 证据
- 总评：PASS / NEEDS_REVISION / REJECT
- P0/P1/P2 问题列表（# | 问题 | 严重度 | 证据 | 建议修改）
- 不修改任何文件

## 触发条件

- 用户要求"深度审计"某个 skill
- skill 经历过多轮优化需要最终验收
- 需要触顶确认（连续 2 轮 Δ<2）

---

## 主 Agent 后处理（审计长报告返回后）

独立审计长出具报告 ≠ 修复完成。主 Agent 收到报告后按以下顺序处理，缺一不可。

### 第 1 步：主 Hermes 抽验关键发现

对审计长报告中的 **P0 问题逐条重现实测**，不能直接采信。
- 每个 P0 跑一次真实 CLI / AST 分析 / 文件 grep，验证问题确实存在且描述准确
- 若某条经抽验为**误判**，注明"已抽验为误判，原因：xxx"，不修但留痕
- P1/P2 由主 Agent 自行决定，不必全部抽验

真实案例（2026-07-30，v1.0.5）：审计长 P0-2 "33 vs 37 测试数不一致"和 P0-1
"skeleton plan 不报错"经抽验均成立已修；P2-2 "results.tsv 无 v1.0.1 行"经抽验为误判
（tsv 第 3 行已有 v1.0.1 old=74→new=92），留痕不修。

### 第 2 步：补跑全量回归测试

主 Agent 亲自跑 python scripts/test_*.py -v，不依赖审计长输出。
记录实际 pass/fail 数量。若修复引入新 break，立即回退。

### 第 3 步：按 P0 → P1 → P2 顺序修复

P0 必须全部修复后进入 P1。每修一条，重跑全量回归确认不破。

### 第 4 步：ad-hoc 验证脚本（覆盖变更行为）

为本轮修复引入的变更单独写一个 focused 验证脚本，而非只依赖全量 suite。
- 文件名：`<TEMP>/hermes-verify-<skill>-<version>.py`（用 TEMP 环境变量确定目录，OS-safe）
- 只覆盖本轮变动的代码路径，不重写 suite
- 脚本声明 "ad-hoc verification (targeted, NOT full suite)"
- 完成后清理，不留残渣

为什么不能只靠全量 suite：suite 验证"现有功能没坏"，ad-hoc 验证"新修复本身正确"。

真实案例（2026-07-30）：hermes-verify-harness-v105.py 覆盖 P0-1 的 4 个输入
（placeholder 被拦 / 真实描述通过 / CLI plan ok:false / 填实后 plan 通过），5/5 passed。

### 第 5 步：更新变更文件

- CHANGELOG.md（若不存在则新建）+ evolution-log.md + results.tsv
- 版本号递增，变更描述精确到"修了什么 bug"
- results.tsv 每行必须对应真实 old→new 分数变动，无对应行即虚构断言

### 第 6 步：最终收口

全量 suite 通过 + ad-hoc 通过并清理 + 报告注明总评/抽验误判数/修复条数/新增测试数。
