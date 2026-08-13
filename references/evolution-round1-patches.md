# 第一轮优化补丁集（待主 session 应用）

> 背景评估工具限制（仅 memory/skill 工具），无法直接 patch SKILL.md 正文。
> 主 Hermes session 恢复后需用 `patch` 工具应用以下 diff。
> 棘轮基线：74/100（dry_run），预期提升 80/100（Δ≈6 > 2，接受）。

---

## Patch 1: SKILL.md —— 替换「常见坑」章节

**old_string**（搜索 `## 常见坑` 开始的段落到第 7 条末尾）：
```
## 常见坑

1. **INGEST 后没填 subtasks 直接 plan** → validate 报错（缺 description / success_criteria）。
   宿主 Agent 必须在 ingest 和 plan 之间用 LLM 把 subtasks 填充完整。
2. **complete 前没等上游 done** → 报 "Dependency not done"。
   先 complete 上游链，再 complete 下游。
3. **exec 返回 ALL TASKS DONE 后还继续 exec** → 直接返回 complete 状态，不会报错。
4. **condition 求值用非法函数** → 静默返回 False，对应任务被 skipped。
5. **audit 生成的 ledger 是骨架，不是结论** → 必须 Agent + 异族 reviewer 填充后再 settle。
6. **workspace 路径** → ingest 时用 `--workspace` 传绝对路径，避免审计文件散落到奇怪位置。
7. **settle 的 `--final-output`** → 传最终产物内容（markdown），harness 会写入 workspace/final_output.md。
```

**new_string**：
```
## 什么时候不用（否定性说明）

以下场景不要套 harness，否则是过度工程化：

- **单步任务**：一个 Action 能搞定，直接用 react-loop 即可，别启动 6 阶段
- **3 步以内的小 DAG**：用 roadmap-planner 单独用就够了，harness 的 overhead 不值得
- **已有明确步骤的任务**：用户已经给了具体拆解，直接执行即可，别硬套规划层
- **任务目标模糊到 LLM 拆不出 subtasks**：先和 Agent 对话澄清目标，不要在模糊目标上启动流水线
- **需要实时交互式决策**：harness 是批量调度，不适合需要在每个步骤暂停等用户输入的对话型任务

---

## 失败模式（三段式 fallback）

| 现象 | 触发原因 | 一线修复 | 仍失败兜底 |
|------|----------|----------|------------|
| `validate` 报 missing 错误 | roadmap 缺必填字段（subtask_description / success_criteria）或 id 重复 | 按报错逐条改对应字段；重复 id 改唯一 | 跑 `ingest --mode complex` 重新生成干净模板再填 |
| `plan` 报 cycle detected | depends_on 形成环（A→B→A） | 去掉某个 `depends_on`，打破环 | 从 demo 重新生成干净 DAG |
| `plan` 报 unknown dependency | `depends_on` 指向不存在的 subtask_id | 改成存在的 id | 用 `status` 看全局，定位缺失的上游 |
| `exec` 报 "依赖尚未完成" | pending 任务的上游没 done/skipped | 先 `complete` 上游依赖链 | 若上游本应被 skip，检查它的 `condition` 是否写错 |
| `exec` 返回 WAITING | 上一步被标 `running` 但还没 `complete` | 去 `complete` 那个 running 的任务 | 若卡死，用 `reset` 清空重来 |
| `complete --id N` 报 "依赖 #M 尚未完成" | 跳步了，没先完成上游 | 先 `complete` #M 及其上游链 | 若 #M 本应被 skip，检查它的 `condition` |
| `exec`/`complete` 报 JSON 解析错误 | state.json 被截断或手改坏 | 从备份或 `ingest` 重新生成 | 用 `reset` 清空重来 |
| `condition` 求值报错（表达式非法） | `condition` 字符串写了不在白名单的标识符或语法错 | 改成只用 `outputs`/`goal`/`context` + `len`/`bool`/`str`/`int`/`float`/`any`/`all` | 直接把 `condition` 设为 `null` 强制走执行分支 |
| `settle` 报 "audit artifacts missing" | audit 阶段未完成，ledger 未填充 | 先跑 `audit` 并填充 claim_ledger | 跳过 audit，settle 带 `--skip-audit` 标志（仅紧急场景） |

---

## 反例与黑名单（不要这样做）

| # | 反模式 | 后果 | 正确做法 |
|---|--------|------|----------|
| 1 | INGEST 后没填 subtasks 直接 PLAN | validate 报错，流程卡住 | 宿主 Agent 必须在 INGEST 和 PLAN 之间用 LLM 把 subtasks 填完整 |
| 2 | COMPLETE 前没等上游 DONE | 报 "Dependency not done" 流程中断 | 先 complete 上游链，再 complete 下游 |
| 3 | 单步任务强行套 6 阶段 harness | 10 行命令干的事变成 60 行，过度工程化 | 单步用 react-loop，3 步内用 roadmap-planner 单独用 |
| 4 | 把 condition 当万能开关写副作用代码 | 沙箱禁 `__builtins__`，条件恒假，任务被跳过 | condition 只读 `outputs`/`goal`/`context`，做判断，不写文件/网络 |
| 5 | workspace 用相对路径 | audit 阶段生成的 .md 散落到奇怪位置 | INGEST 时用 `--workspace` 传绝对路径 |
| 6 | 两个 Agent 并发写同一个 harness_state.json | 读过期 data 写入，条目标记丢失 | 串行调用，单进程操作 |
| 7 | EXEC 返回 ALL TASKS DONE 后继续 EXEC | 直接返回 complete 状态，不会报错但无意义 | 收到 "ALL TASKS DONE" 立即转 REVIEW |
| 8 | AUDIT 生成的 ledger 不填充就直接 SETTLE | audit 骨架是占位符，不是结论 | 宿主 Agent + 异族 reviewer 对抗式填充 ledger 后再 settle |
| 9 | 任务目标模糊到拆不出 subtasks 仍启动 harness | LLM 生成乱填的 subtasks，validate 通不过 | 先和 Agent 对话澄清目标，目标明确再启动流水线 |
```

---

## Patch 2: reviewer_prompt.md —— 加「审计填充指导」

在 `## 输出格式` 前插入：

```
## 审计填充指导

完成 audit 阶段后，宿主 Agent 负责填充以下三个骨架：

### 1. integrity_checklist.md

- 每个 done task → `[✅]`；每个 skipped task → `[⚠️]`；每个 error task → `[❌]`
- 输出为空或仅包含框架文字（"见上文"）的 task 标 `[⚠️]`

### 2. claim_ledger.md

**怎么从 aggregated_outputs 提取声明**：遍历每个 done task 的 `output` 字段，找出结论性句子（不是过程描述），写入声明行。

**怎么定支撑强度**：
- 强：execution_log 有对应 Action/Observation 原文引用该声明
- 中：output 里写了，但 execution_log 无直接引用
- 弱：output 里有声明，但没有任何原始数据支撑

**怎么判定缺口**：声明在 output 里但 execution_log 没对应原始数据 = 缺口。声明和支撑之间隔着推论链，推论链每一步都要有 Observation 支撑，缺一步就是缺口。

### 3. claim_audit_report.md

- P0 列表：每个 P0 标注 "来源 claim_ledger 第几行 + 缺口描述"
- 修订建议：每条附带 "改什么 + 预期效果"

---
```

---

## 预期评分变化

| 维度 | 基线 | 预计 | 原因 |
|------|------|------|------|
| dim9 反例黑名单 | 6/10 | 9/10 | 独立章节，9 行反模式表格 |
| dim3 失败模式编码 | 7/10 | 10/10 | 9 行四列表 if-then |
| dim2 工作流清晰度 | 9/10 | 10/10 | 新增否定性章节 |
| dim5 可执行具体性 | 8/10 | 9/10 | audit 填充步骤具体化 |
| **加权总分** | **74** | **~80** | Δ≈6，远超触顶线 2 |