---
name: unclekk-harness
slug: unclekk-harness
displayName: UncleKK Harness 大幅减少AI幻觉
version: 1.0.7
summary: 把规划/执行/审计串成可审计、可恢复、可暂停的 6 阶段端到端流水线（INGEST→PLAN→EXEC→REVIEW→AUDIT→SETTLE），通过声明证据链与三阶段对抗审计大幅减少 AI 幻觉。 Chains planning/execution/audit into an auditable, resumable, pausable 6-stage end-to-end pipeline (INGEST→PLAN→EXEC→REVIEW→AUDIT→SETTLE); claim-evidence chains + 3-stage adversarial audit drastically reduce AI hallucination.
description: 'Orchestrates tasks into auditable, resumable pipelines.

  '
license: MIT
author: KK大叔 (UncleKK)
metadata:
  agent_created: true
  based_on: unclekk-roadmap-planner + unclekk-react-loop + unclekk-aris-assurance
---

# unclekk-harness (UncleKK Harness)

把 unclekk-roadmap-planner（拆任务）、unclekk-react-loop（边想边做）、unclekk-aris-assurance（对抗审计）串成一条**端到端自动流水线**。

Chains unclekk-roadmap-planner (task decomposition), unclekk-react-loop (think-while-doing), and unclekk-aris-assurance (adversarial audit) into one **end-to-end automated pipeline**.

> 一句话：Hermes 给一个模糊目标，harness 自动走完"规划 → 执行 → 聚合 → 审计 → 输出"，中间关键节点才让人确认。

> In one sentence: Hermes provides a vague goal, and the harness automatically runs through "plan → execute → aggregate → audit → output", pausing for human confirmation only at key checkpoints.

## 这是什么 (What This Is)

harness 是 **orchestrator，不是 executor**。它只负责调度、状态管理、原子写、DAG 校验、审计骨架生成；真正的 LLM 调用和工具执行由宿主 Agent（Hermes / WorkBuddy）完成。

The harness is an **orchestrator, not an executor**. It is only responsible for scheduling, state management, atomic writes, DAG validation, and audit-skeleton generation; the actual LLM calls and tool execution are performed by the host Agent (Hermes / WorkBuddy).

```
INGEST → PLAN → EXEC → REVIEW → AUDIT → SETTLE
  ①       ②      ③       ④       ⑤        ⑥
  接目标  拆任务  逐任务   聚产出  抗审计   输出交付
  +       +       +        +       +        +
  roadmap  validate  react   collect  aris   final
```

## 什么时候用 (When To Use)

- 用户给了一个**模糊但复杂**的目标（"写一份竞品报告""调研 XX 能不能用"）
  - The user gives a **vague but complex** goal ("write a competitor report", "research whether XX is usable").
- 任务明显需要**多步骤、有先后依赖或可以并行**
  - The task clearly requires **multiple steps, with sequential dependencies or possible parallelism**.
- 怕方向跑偏或做到一半才发现漏了关键步骤
  - Fear of going off-track or discovering missing critical steps halfway through.
- 需要**可审计、可暂停、可恢复**的执行记录
  - Need an **auditable, pausable, resumable** execution record.

## 什么时候不用 (When NOT To Use)

以下场景硬套 6 阶段 harness 反而增加 overhead，应降级为更轻的工具：

In the following scenarios, forcing the 6-stage harness adds overhead; degrade to a lighter tool instead:

- **单步任务**：只需执行一个动作并收口的（查一个接口、跑一次命令、生成一段代码），直接用 `react-loop` 即可，不必引入 planner + aggregator 多层编排
  - **Single-step task**: Only needs to perform one action and close it out (query an API, run one command, generate some code). Just use `react-loop` directly; no need to introduce planner + aggregator multi-layer orchestration.
- **3 步以内的小 DAG**：步骤数量少、依赖关系一眼可见、不需要跨轮次证据汇聚时，单独用 `roadmap-planner` 或手动列出步骤执行就够了
  - **Small DAG within 3 steps**: When the number of steps is small, dependencies are obvious at a glance, and cross-round evidence aggregation isn't needed, using `roadmap-planner` alone or manually listing steps to execute is sufficient.
- **步骤已明确的机械任务**：任务目标和执行步骤已明确、不需要拆解、不需要对产出做交叉验证的，别硬套 6 阶段——harness 的价值在于「拆解 + 汇聚 + 审计」，没有这些需求就属于过度工程化
  - **Mechanical tasks with clear steps**: When the task goal and execution steps are already clear, no decomposition or cross-validation of outputs is needed—don't force the 6-stage approach. The harness's value lies in "decomposition + aggregation + audit"; lacking these needs makes it over-engineering.
- **目标模糊到 LLM 都拆不出 subtasks**：此时先和宿主 Agent 对话澄清目标，而不是急着建 harness 状态
  - **Goal too vague for even the LLM to decompose into subtasks**: In this case, first clarify the goal through dialogue with the host Agent, rather than rushing to build harness state.
- **任务会随时中断且恢复成本高**：harness 依赖 state.json 恢复，如果 workspace 随时被清空，用内存中的草稿比持久化状态更实际
  - **Task may interrupt at any time with high recovery cost**: The harness relies on state.json for recovery; if the workspace can be cleared at any time, in-memory drafts are more practical than persisted state.

## 使用边界量化约束 (Quantitative Usage Boundaries)

以下为**建议上限**（非硬性代码拦截）。超出建议值时，按「什么时候不用」降级或拆分任务，避免流水线 overhead 失控或被单次 state 撑爆：

| 维度 | 建议上限 | 超出时的建议 |
|------|----------|--------------|
| 目标文本长度 | ≤ 2000 字符 | 拆成多个独立 harness 实例，或先澄清目标 |
| subtasks 数量 | ≤ 50 个 | 超出说明拆解过细，先合并 / 分层 |
| DAG 最大深度 | ≤ 8 层 | 过深说明任务可再分层为子 harness |
| 单 subtask 产出 | ≤ 50,000 字符 | 落盘到 workspace 文件，state 只存引用 |
| state.json 体积 | ≤ 5 MB | 把大产出外置到 workspace，state 仅存指针 |
| condition 表达式 | ≤ 200 字符，仅白名单函数 | 超限说明逻辑过重，改由宿主 Agent 侧预计算 |
| 并行组（parallel_group） | 仅作分组标记，不真并行 | 真并行由宿主 Agent 另起独立 state 处理 |

> 这些上限来自设计经验（原子写内存占用、JSON 可读性、人审负担）；harness 当前**不强制拦截**，真正会硬拦截的是 `validate`（字段齐全）与 stage-gate（阶段前置）。

## 6 阶段传送带 (The 6-Stage Conveyor)

| # | 阶段 | 命令 | 作用 | 检查点 |
|---|------|------|------|--------|
| 1 | INGEST | `ingest --goal "..." --workspace "..." --out harness_state.json` | 接自然语言目标，生成 roadmap skeleton（1 个 placeholder subtask） | 无 |
| 1.5 | FILL | 宿主 Agent 用 LLM 把 skeleton 的 subtasks 填实（多步 + 依赖 + success_criteria） | 必须完成才能 plan——validate 要求全部字段非空 | 🛑 确认 subtasks 完整后再 plan |
| 2 | PLAN | `plan --state harness_state.json` | 校验 DAG 无环/依赖合法/字段齐全，输出拓扑序 | 🛑 用户确认后继续 |
| 3 | EXEC | `exec` | 返回下一步子任务 + react-loop prompt 模板 | 无（Agent 自行执行） |
| — | complete | `complete --id N --output "..."` | 宿主 Agent 执行后标记完成，产出自动传下游 | 无 |
| — | error | `error --id N --msg "..."` | 标记任务失败 | 无 |
| 4 | REVIEW | `review` | 聚合所有 done 任务的产出 | 无 |
| 5 | AUDIT | `audit` | 生成 integrity_checklist / claim_ledger / claim_audit_report 三个审计骨架 | 无 |
| 6 | SETTLE | `settle --final-output "..."` | 写最终产物 + 输出完整 summary | 无 |

| # | Stage | Command | Role | Checkpoint |
|---|-------|---------|------|------------|
| 1 | INGEST | `ingest --goal "..." --workspace "..." --out harness_state.json` | Accepts a natural-language goal, generates a roadmap skeleton (1 placeholder subtask) | None |
| 1.5 | FILL | The host Agent uses LLM to fill in the skeleton's subtasks (multi-step + dependencies + success_criteria) | Must be completed before plan—validate requires all fields non-empty | 🛑 Confirm subtasks are complete before planning |
| 2 | PLAN | `plan --state harness_state.json` | Validates DAG acyclicity / legal dependencies / complete fields, outputs topological order | 🛑 Continue after user confirmation |
| 3 | EXEC | `exec` | Returns the next subtask + react-loop prompt template | None (Agent executes itself) |
| — | complete | `complete --id N --output "..."` | Host Agent marks completion after execution; output is automatically passed downstream | None |
| — | error | `error --id N --msg "..."` | Marks task failure | None |
| 4 | REVIEW | `review` | Aggregates outputs of all done tasks | None |
| 5 | AUDIT | `audit` | Generates three audit skeletons: integrity_checklist / claim_ledger / claim_audit_report | None |
| 6 | SETTLE | `settle --final-output "..."` | Writes the final artifact + outputs a complete summary | None |

## 可选扩展：meta-skill 优化层 (Optional Extension: meta-skill Optimization Layer)

harness 是 orchestrator，不直接调用 LLM 也不评分。但宿主 Agent 可以在流水线的关键节点嵌入 **darwin-skill**（9 维 rubric 评分 + 棘轮）和 **skill-evolver**（策略多样化探索 + 对比式更新 + 独立审计），形成"执行 + 自优化"的双层闭环。

The harness is an orchestrator; it does not directly call the LLM nor score. But the host Agent can embed **darwin-skill** (9-dimension rubric scoring + ratchet) and **skill-evolver** (strategy-diversified exploration + comparative update + independent audit) at key pipeline nodes, forming a two-layer closed loop of "execution + self-optimization".

### 嵌入点 (Embedding Points)

```
INGEST → FILL → PLAN → [EXEC 循环] → REVIEW → AUDIT → SETTLE
                              │            │          │
                              │            │          └─→ 沉淀到 skill-library
                              │            │
                              │            └─→ 独立审计（aris-assurance）
                              │
                              └─→ 每轮后 darwin 评分该 task 产出
```

### 各阶段可嵌入的 meta-skill (Meta-skills Embeddable at Each Stage)

| 节点 | 嵌入的 meta-skill | 作用 | 是否必须 |
|------|-------------------|------|----------|
| EXEC 每轮后 | **darwin-skill** dim8 实测表现评分 | 每个子任务执行完后，用 9 维 rubric 打该 task 产出，记录到 `references/results.md` | 可选 |
| AUDIT 阶段 | **aris-assurance** 独立审计 | 已有内置，宿主 Agent + 异族 reviewer 跑三阶段声明审计 | 可选 |
| SETTLE 后 | **内置 unclekk-skill-library** `record + optimize` | 把本次流水线整体方案存库（task_type = "pipeline"），用 `optimize` 棘轮提升下次复用质量；调用本 harness 的 `unclekk-skill-library/scripts/library.py` | 可选 |
| 全流水线后 | **skill-evolver** 策略多样化探索 | 对本流水线做 3 个策略变体对比，生成改进补丁并独立审计 | 按需 |

| Node | Embedded meta-skill | Role | Required |
|------|---------------------|------|----------|
| After each EXEC round | **darwin-skill** dim8 measured-performance scoring | After each subtask executes, score its output with the 9-dimension rubric, recorded to `references/results.md` | Optional |
| AUDIT stage | **aris-assurance** independent audit | Built-in; host Agent + heterogeneous reviewer runs three-stage claim audit | Optional |
| After SETTLE | **built-in unclekk-skill-library** `record + optimize` | Stores the entire pipeline plan into the library (task_type = "pipeline"), uses `optimize` ratchet to improve next reuse quality; calls this harness's `unclekk-skill-library/scripts/library.py` | Optional |
| After full pipeline | **skill-evolver** strategy-diversified exploration | Produces 3 strategy variants for comparison on this pipeline, generates improvement patches and independently audits | As needed |

### 操作示例 (Operation Example)

```bash
# 1. EXEC 某任务后，用 darwin 给该 task 产出评分
#    宿主 Agent 自己读该 task 的 output，对照 9 维 rubric 打分
#    分数记录到 workspace/dim8_scores.json：
#    {"task_id": 1, "dim8_score": 7, "dimension_detail": "executability", "eval_mode": "full"}

# 2. 本技能自带的进化记录（不需要额外脚本）
#    宿主 Agent 把 9 维评分写入 references/results.md 和 references/evolution-log.md：
#    timestamp <tab> commit <tab> skill <tab> old_score <tab> new_score <tab> status
#    <tab> dimension <tab> note <tab> eval_mode

# 3. 宿主 Agent 可在其他 skill（如 skill-library）复用本次流水线方案；
#    该脚本/路径由宿主自行决定，本 harness 不依赖也不硬编码任何外部脚本
```

### 评分与进化记录 (Scoring and Evolution Records)

harness 自身的进化记录在 `references/evolution-log.md`（含 9 维 rubric 评分、策略变体对比、独立审计结果），格式与 darwin-skill 的 `results.tsv` 对齐。

The harness's own evolution records are in `references/evolution-log.md` (including 9-dimension rubric scores, strategy-variant comparisons, independent audit results), aligned in format with darwin-skill's `results.tsv`.

```
references/results.md  —  每轮进化：old_score → new_score，维度增量，eval_mode
references/evolution-log.md  —  进化日志：策略变体、补丁内容、审计结果
```

宿主 Agent 在 EXEC 各轮后也可写 `workspace/dim8_scores.json`（纯 JSON，harness 不依赖它），供 skill-library 的 `optimize` 作为新分依据。

The host Agent may also write `workspace/dim8_scores.json` after each EXEC round (pure JSON, the harness does not depend on it), to serve as a new-score basis for skill-library's `optimize`.

### 内置技能库 unclekk-skill-library (Built-in Skill Library unclekk-skill-library)

harness 现已**内置**技能库能力，作为本技能的子目录 `unclekk-skill-library/`（与独立的 `skill-library` 技能同源，纯拷贝、可独立演进）。宿主 Agent 在 SETTLE 后直接调用内置库的 `record` / `optimize`，把本次流水线方案沉淀进库并棘轮提升，无需依赖外部 `skill-library` 已安装。

The harness now has **built-in** skill-library capability as a subdirectory `unclekk-skill-library/` (same origin as the standalone `skill-library` skill, a pure copy that can evolve independently). After SETTLE, the host Agent directly calls the built-in library's `record` / `optimize` to deposit this pipeline plan into the library and ratchet it up, without depending on an externally installed `skill-library`.

调用路径（相对 harness 根目录）：

Call paths (relative to harness root):

```bash
# SETTLE 后，把本次流水线方案存入内置库（task_type 建议 "pipeline"）
python unclekk-skill-library/scripts/library.py add \
  --task-type "pipeline" \
  --description "模糊复杂目标的端到端流水线" \
  --approach "INGEST→PLAN→EXEC→REVIEW→AUDIT→SETTLE" \
  --dimensions "拆解,执行,汇聚,审计,沉淀" --tags "unclekk,harness" --score 0.85

# 复用：新任务查库命中方案
python unclekk-skill-library/scripts/library.py find --query "模糊复杂目标"

# 棘轮提升：跑完后回写验证分
python unclekk-skill-library/scripts/library.py record --id <id> --score <new>
python unclekk-skill-library/scripts/library.py optimize
```

设计原则：内置库是 harness 的**资源**，harness 自身不调它（orchestrator 不调 LLM/不评分）；宿主 Agent 在 SETTLE 后自行调用。内置库的 `--store` 默认写 harness 工作区内的库文件，具体路径由宿主 Agent 通过 `--store` 显式指定，harness 不硬编码。

Design principle: the built-in library is a **resource** of the harness; the harness itself does not call it (the orchestrator does not call LLM / does not score); the host Agent calls it on its own after SETTLE. The built-in library's `--store` defaults to writing the library file within the harness workspace; the specific path is explicitly specified by the host Agent via `--store`, and the harness does not hardcode it.

### 设计约束 (Design Constraints)

- harness 不调 darwin/skill-evolver——宿主 Agent 自己调用
  - The harness does not call darwin/skill-evolver—the host Agent calls them itself.
- `workspace/dim8_scores.json` 是可选文件，harness 不读它、不依赖它
  - `workspace/dim8_scores.json` is an optional file; the harness does not read or depend on it.
- 内置 `unclekk-skill-library` 的 `--store` 路径由宿主 Agent 自行指定，harness 不硬编码
  - The built-in `unclekk-skill-library`'s `--store` path is specified by the host Agent itself; the harness does not hardcode it.

---

## 使用方式 (Usage)

辅助命令：

Auxiliary commands:

- `status` — 查看当前阶段、done/pending/error 计数
  - `status` — View current stage, done/pending/error counts.
- `--state` — 所有命令默认用 `harness_state.json`，可覆盖
  - `--state` — All commands default to `harness_state.json`, overridable.

### 最小示例 (Minimal Example)

```bash
# 1. 初始化
python scripts/harness.py ingest \
  --goal "写一份 X 平台竞品分析" \
  --workspace "/path/to/workspace" \
  --out harness_state.json

# 2. 规划
python scripts/harness.py plan --state harness_state.json
# → 输出 ok:true + 拓扑序 + "🛑 CHECKPOINT: confirm and continue"
# → 宿主 Agent 用 LLM 把 roadmap 的 subtasks 填实

# 3. 执行（循环）
python scripts/harness.py exec --state harness_state.json
# → 返回 next_tasks，每项含 prompt_template（react-loop 格式）
# → Agent 按 prompt_template 执行 Thought/Action/Observation
# → 执行完后标记完成：
python scripts/harness.py complete \
  --state harness_state.json \
  --id 1 \
  --output "结果摘要..."
# → 再调 exec 拿下一步

# 4. 聚合
python scripts/harness.py review --state harness_state.json

# 5. 审计
python scripts/harness.py audit \
  --state harness_state.json \
  --output-dir "/path/to/workspace"
# → 生成 integrity_checklist.md / claim_ledger.md / claim_audit_report.md
# → 宿主 Agent + 异族 Reviewer 填充台账并跑三阶段审计

# 6. 交付
python scripts/harness.py settle \
  --state harness_state.json \
  --final-output "# 最终报告内容..."

# 查看状态
python scripts/harness.py status --state harness_state.json
```

### Python 嵌入用法 (Embed in Python)

除了命令行，harness.py 也是纯函数式模块，可直接 `import` 调用（仅依赖 stdlib），适合在宿主 Agent 的代码里编排：

```python
import sys
sys.path.insert(0, "scripts")
import harness as H
H.ingest(goal="...", workspace="...", out="harness_state.json")
H.plan("harness_state.json")
nxt = H.exec("harness_state.json")
H.complete("harness_state.json", task_id=1, output="...")
H.review("harness_state.json")
H.audit("harness_state.json", output_dir="...")
H.settle("harness_state.json", final_output="# ...")
```

CLI 与 Python API 行为完全一致，按需选择。

### 真实任务端到端流程 (Real-Task End-to-End Flow)

```
1. ingest  → 生成 roadmap skeleton（宿主 Agent 用 LLM 填 subtasks）
2. plan    → validate DAG（环/依赖/字段齐全）→ 🛑 确认
3. exec    → 拿下一步任务 → Agent react-loop 执行 → complete
   重复 exec / complete 直到 exec 返回 "ALL TASKS DONE"
4. review  → 聚合所有任务产出
5. audit   → 生成审计骨架 → Agent + reviewer 对抗式填充
6. settle  → 写 final_output.md + 完整 summary
```

> 📚 **完整可复制案例**：见 [`references/end-to-end-example.md`](references/end-to-end-example.md)（从 ingest 到 settle 的逐阶段命令 + state 样例）。
> 📚 **常见问题集中解答**：见 [`references/faq.md`](references/faq.md)。

## 文件结构 (File Structure)

```
unclekk-harness/
├── SKILL.md                              # 本技能定义
├── CHANGELOG.md                          # 变更记录
├── scripts/
│   ├── harness.py                        # 6 阶段核心（零依赖）
│   └── test_harness.py                   # 回归测试（39 项）
├── templates/
│   ├── executor_prompt.md
│   └── reviewer_prompt.md
├── references/
│   ├── harness-integration.md            # 集成说明
│   ├── evolution-log.md                  # 进化日志：策略变体、补丁、独立审计
│   ├── results.md                        # 每轮 9 维评分增量（darwin 对齐）
│   └── audit-layers.md                   # 6 层深度审计方法论（独立审计长用）
└── unclekk-skill-library/                # 内置技能库（Voyager 式，自包含，与独立 skill-library 同源）
    ├── SKILL.md                          # 技能库定义与 find/record/optimize 用法
    ├── scripts/
    │   ├── library.py                    # 核心库（add/find/record/optimize/list/stats）
    │   └── test_library.py               # 回归测试
    ├── references/
    │   └── schema.md                     # 库条目 schema 说明
    ├── CHANGELOG.md
    ├── LICENSE.md
    └── README.md
```

## harness_state.json 字段 (harness_state.json Fields)

```json
{
  "schema": "1.0",
  "goal": "目标",
  "workspace": "工作目录绝对路径",
  "stage": "init|ingest|plan|exec|review|audit|settled|recovered",
  "mode": "complex",
  "context": {},
  "worker_pool": {},
  "subtasks": [
    {
      "subtask_id": 1,
      "subtask_description": "这步做什么",
      "exact_input": "精确输入（可引用上一步产出）",
      "expected_output": "期望产出",
      "success_criteria": "如何判断完成",
      "desired_auxiliary_tools": ["search", "browser"],
      "depends_on": [],
      "parallel_group": "collect",
      "condition": "len(outputs.get(5, '')) > 50",
      "assigned_worker": "researcher-1",
      "status": "pending|running|done|skipped|error",
      "output": ""
    }
  ],
  "execution_log": [],
  "aggregated_outputs": {},
  "audit": {
    "integrity_checklist": "path/to/file",
    "claim_ledger": "path/to/file",
    "claim_audit_report": "path/to/file"
  },
  "checkpoint_ok": false
}
```

## 设计约束 (Design Constraints)

- **零依赖**：只用 stdlib（json/argparse/os/pathlib/time/sys），不引入第三方包
  - **Zero dependencies**: Only uses stdlib (json/argparse/os/pathlib/time/sys), no third-party packages.
- **原子写**：所有 state 写入走 temp + rename，防止写入中途崩溃导致状态损坏
  - **Atomic writes**: All state writes go through temp + rename, preventing state corruption from a crash mid-write.
- **沙箱 condition**：`condition` 表达式只读 `outputs`/`context`/`goal`，仅开放 `len`/`bool`/`str`/`int`/`float`/`any`/`all`，禁 `__builtins__` 和副作用
  - **Sandboxed condition**: The `condition` expression only reads `outputs`/`context`/`goal`, only exposes `len`/`bool`/`str`/`int`/`float`/`any`/`all`, and forbids `__builtins__` and side effects.
- **单进程写入**：harness_state.json 同一时刻只能由一个 Agent 操作，无跨进程锁
  - **Single-process writes**: harness_state.json can only be operated on by one Agent at a time; no cross-process lock.
- **不改 core**：harness 不修改 unclekk- 三个源技能的代码，只做协调
  - **No core changes**: The harness does not modify the code of the three unclekk- source skills; it only coordinates.

## 与三个 unclekk 技能的集成关系 (Integration Relationship with the Three unclekk Skills)

| 源技能 | 集成点 | harness 怎么用它 |
|--------|--------|------------------|
| roadmap-planner | INGEST + PLAN | 复用 Roadmap schema、DAG 拓扑排序、condition 沙箱 |
| react-loop | EXEC | 每步 exec 返回含 `prompt_template` 的 react-loop 三段式 |
| aris-assurance | AUDIT | 生成三阶段审计骨架（integrity_checklist / claim_ledger / audit_report） |

| Source skill | Integration point | How harness uses it |
|--------------|-------------------|---------------------|
| roadmap-planner | INGEST + PLAN | Reuses Roadmap schema, DAG topological sort, condition sandbox |
| react-loop | EXEC | Each exec step returns a react-loop three-part `prompt_template` |
| aris-assurance | AUDIT | Generates three-stage audit skeletons (integrity_checklist / claim_ledger / audit_report) |

harness 不调 LLM、不真并行、不动态装卸 MCP —— 这些交给宿主 Agent。

The harness does not call LLM, does not truly parallelize, does not dynamically load/unload MCP — these are handed to the host Agent.

## 失败模式（三段式 fallback）(Failure Modes — Three-Stage Fallback)

> 现象 → 触发原因 → 一线修复 → 仍失败兜底。遇到即降级，不让流水线在坏状态上继续滚。

> Symptom → Trigger cause → First-line fix → Fallback if still failing. Downgrade on encounter; don't let the pipeline keep rolling in a bad state.

| # | 现象 | 触发原因 | 一线修复 | 仍失败兜底 |
|---|------|----------|----------|------------|
| 1 | `plan` 报 `validate` 错误（缺 description / success_criteria） | INGEST 后宿主 Agent 没填 subtasks 就直接 plan | ingest 与 plan 之间先用 LLM 把全部 subtasks 补齐 | 手动编辑 state，补全 missing 字段后重跑 plan |
| 2 | `complete` 报 "Dependency not done" | 下游任务在其上游未 done 时就被 complete | 按拓扑序先 complete 上游链，再 complete 下游 | 用 `status` 查卡在哪个节点，把上游逐个标 done |
| 3 | `exec` 返回 `ALL TASKS DONE` 后继续 exec 无反应 | 所有任务已 done，再 exec 只会回 complete 状态，不报错 | 停止 exec 循环，进入 review | 若预期还有任务未跑，检查是否有任务被误标 done 或 condition 被静默跳过 |
| 4 | `condition` 求值用非法函数 | condition 表达式用了白名单外的标识符或语法错 | 改成只用 `outputs`/`goal`/`context` + `len`/`bool`/`str`/`int`/`float`/`any`/`all` | 直接把 `condition` 设为 `null` 强制走执行分支 |
| 5 | audit 生成的 ledger 是骨架，不是结论 | audit 阶段只生成占位 .md，没告诉 Agent 怎么填 | 用 `reviewer_prompt.md` 的步骤指导填充 ledger | 若 reviewer 模板缺失，手动从 `aggregated_outputs` 里逐条提取声明并填入 ledger |
| 6 | workspace 路径不存在或写不了 | ingest 传的 workspace 路径不可写或目录不存在 | audit 阶段用绝对路径，目录必须存在 | 用 `--store` / 指定其他可写路径重建库 |
| 7 | `settle` 的 `--final-output` 为空或过短 | 宿主 Agent 没传最终产物内容 | 传完整的 markdown 内容（`# 最终报告内容...`） | 手动把产出写入 `workspace/final_output.md`，再跑 settle |
| 8 | state.json 被手动破坏（缺 subtasks / execution_log 字段） | 非原子写并发写入或人为编辑导致 JSON 合法但字段缺失 | 从 execution_log 重建任务状态（`_load(recover=True)`） | 若完全不可恢复，用 `ingest` 重生成 skeleton，从最近 checkpoint 继续 |
| 9 | 并发两个 Agent 同时 step/complete 同一 state.json | 本技能只保证原子写，无跨进程文件锁 | 串行操作，或每个 Agent 用独立的 `--state` 文件 | 若已发生冲突，检查 `edits` / `execution_log` 时间戳定位哪个更新被覆盖 |
| 10 | `review`/`settle` 被提前调用（跳过了前序阶段） | 宿主 Agent 未走完 exec → review 顺序就直接 review/settle | `review` 要求 stage 为 exec/review；`settle` 要求 review/audit + `--final-output` 非空；阶段前置检查失败即报错并原地中止 | 补齐缺失阶段（exec 全量完成 / review / audit）后重跑 |

| # | Symptom | Trigger cause | First-line fix | Fallback if still failing |
|---|---------|---------------|----------------|---------------------------|
| 1 | `plan` reports `validate` error (missing description / success_criteria) | After INGEST, host Agent ran plan without filling subtasks | Use LLM to fill all subtasks between ingest and plan | Manually edit state, fill missing fields, rerun plan |
| 2 | `complete` reports "Dependency not done" | Downstream task was completed while its upstream was not done | Complete upstream chain in topological order first, then downstream | Use `status` to find the stuck node, mark upstream as done one by one |
| 3 | After `exec` returns `ALL TASKS DONE`, further exec has no response | All tasks done; further exec only returns complete status, no error | Stop exec loop, enter review | If tasks were expected but not run, check if any task was mistakenly marked done or condition silently skipped |
| 4 | `condition` evaluation uses illegal function | condition expression used an identifier outside whitelist or syntax error | Change to only use `outputs`/`goal`/`context` + `len`/`bool`/`str`/`int`/`float`/`any`/`all` | Set `condition` to `null` to force the execution branch |
| 5 | audit-generated ledger is a skeleton, not conclusions | audit stage only generates placeholder .md, doesn't tell Agent how to fill | Use `reviewer_prompt.md` steps to guide ledger filling | If reviewer template missing, manually extract claims one by one from `aggregated_outputs` and fill ledger |
| 6 | workspace path doesn't exist or isn't writable | ingest passed a workspace path that's not writable or directory doesn't exist | Use absolute path in audit stage; directory must exist | Use `--store` / specify another writable path to rebuild the library |
| 7 | `settle`'s `--final-output` is empty or too short | Host Agent didn't pass final artifact content | Pass complete markdown content (`# 最终报告内容...`) | Manually write output to `workspace/final_output.md`, then run settle |
| 8 | state.json manually corrupted (missing subtasks / execution_log fields) | Non-atomic concurrent writes or manual editing caused JSON valid but fields missing | Rebuild task state from execution_log (`_load(recover=True)`) | If fully unrecoverable, use `ingest` to regenerate skeleton, continue from latest checkpoint |
| 9 | Two Agents concurrently step/complete the same state.json | This skill only guarantees atomic writes, no cross-process file lock | Serial operation, or each Agent uses independent `--state` file | If conflict occurred, check `edits` / `execution_log` timestamps to locate which update was overwritten |
| 10 | `review`/`settle` called prematurely (skipping prior stages) | Host Agent didn't complete exec → review order before directly reviewing/settling | `review` requires stage exec/review; `settle` requires review/audit + non-empty `--final-output`; stage pre-check failure raises error and aborts in place | Complete missing stages (exec all done / review / audit) then rerun |

## 反例与黑名单（不要这样做）(Anti-Patterns and Blacklist — Don't Do These)

> 每条反模式都来自真实踩坑记录，不要重蹈覆辙。

> Each anti-pattern comes from real pitfall records; don't repeat them.

| # | 反模式 | 后果 | 正确做法 |
|---|--------|------|----------|
| 1 | INGEST 后不填 subtasks 直接 plan | validate 报错，流水线在第 2 阶段就卡住 | ingest 和 plan 之间必须让宿主 Agent 用 LLM 把 subtasks 填充完整 |
| 2 | 跨进程并发操作同一个 state.json | 原子写防不住并发，可能导致更新丢失或字段损坏 | 同一 state 必须由单一 Agent 顺序调用；多个 Agent 用独立的 `--state` |
| 3 | `condition` 写副作用代码（文件 I/O / 网络请求） | 沙箱虽禁 `__builtins__`，但白名单外的标识符会静默 return False，导致任务被 skip | 只用 `outputs`/`goal`/`context` + 白名单函数，不做副作用操作 |
| 4 | `complete` 时跳过上游依赖 | 下游任务拿不到上游产出，产出空洞，审计环节必爆 | 严格按拓扑序执行：上游 done 或 skipped 后才能 complete 下游 |
| 5 | audit 后不填充 ledger 直接 settle | final_output.md 没有经过审计，声明无证据支撑，审计形同虚设 | settle 前必须完成三阶段声明审计（integrity → 映射 → 交叉审计） |
| 6 | workspace 用相对路径 | audit 生成的 .md 散落到意外位置，最终产物不可追溯 | 用 `--workspace` 传绝对路径，目录提前确认存在 |
| 7 | exec 返回 ALL TASKS DONE 后还继续调 exec | 无副作用但浪费时间，且容易让宿主 Agent 误以为流水线卡住了 | 收到 "ALL TASKS DONE" 立即转 review，不再调 exec |
| 8 | 把 `settle --final-output` 留空 | final_output.md 写入空字符串，交付产物为空 | 传完整的 markdown 内容，harness 会写入 workspace/final_output.md |
| 9 | 把 harness 当自动执行框架宣传 | 违背 orchestrator/executor 边界，用户对预期产出的认知与事实不符 | 诚实声明：harness 只调度、不调 LLM、不写代码、不真并行、不动态装卸 MCP |
| 10 | 单步任务强行用 harness | 引入 plan/audit/settle 多层 overhead，2 分钟的事变成 20 分钟 | 单步任务直接用 react-loop；3 步以内小 DAG 用 roadmap-planner 单独用 |

| # | Anti-pattern | Consequence | Correct approach |
|---|--------------|-------------|------------------|
| 1 | Not filling subtasks after INGEST then directly planning | validate errors, pipeline stuck at stage 2 | Between ingest and plan, host Agent must use LLM to fill subtasks completely |
| 2 | Cross-process concurrent operation on same state.json | Atomic writes can't prevent concurrency, may cause lost updates or field corruption | Same state must be called sequentially by a single Agent; multiple Agents use independent `--state` |
| 3 | `condition` writes side-effect code (file I/O / network requests) | Although sandbox forbids `__builtins__`, identifiers outside whitelist silently return False, causing task to be skipped | Only use `outputs`/`goal`/`context` + whitelist functions; no side-effect operations |
| 4 | Skipping upstream dependencies when `complete` | Downstream task can't get upstream output, output hollow, audit stage bound to break | Strictly execute in topological order: upstream must be done or skipped before completing downstream |
| 5 | Settle without filling ledger after audit | final_output.md not audited, claims lack evidence, audit becomes useless | Before settle, must complete three-stage claim audit (integrity → mapping → cross-audit) |
| 6 | workspace uses relative path | .md generated by audit scattered to unexpected locations, final artifact untraceable | Use `--workspace` with absolute path, confirm directory exists in advance |
| 7 | Continue calling exec after exec returns ALL TASKS DONE | No side effects but wastes time, easily makes host Agent think pipeline is stuck | On receiving "ALL TASKS DONE" immediately switch to review, no more exec |
| 8 | Leave `settle --final-output` empty | final_output.md writes empty string, deliverable empty | Pass complete markdown content; harness writes to workspace/final_output.md |
| 9 | Promote harness as an auto-execution framework | Violates orchestrator/executor boundary; user's expectations diverge from reality | Honestly state: harness only schedules, doesn't call LLM, doesn't write code, doesn't truly parallelize, doesn't dynamically load/unload MCP |
| 10 | Force harness on single-step task | Introduces plan/audit/settle multi-layer overhead; 2-minute thing becomes 20 minutes | Single-step task uses react-loop directly; small DAG within 3 steps uses roadmap-planner alone |

## 自测 (Self-Test)

```bash
cd skills/unclekk-harness
python scripts/test_harness.py -v
# 预期：39/39 passed
```

## 变更记录 (Changelog)

- v1.0.5 (2026-07-30) 独立审计长第 4 轮：skeleton placeholder 阻断（validate 拦截 `[LLM:`）+ 文档 33→39 测试数修正 + stage 枚举补充 init/recovered
  - v1.0.5 (2026-07-30) Independent-auditor round 4: skeleton placeholder blocking (validate intercepts `[LLM:`) + doc test count correction 33→39 + stage enum supplemented with init/recovered.
- v1.0.4 (2026-07-27) 独立审计长第 3 轮：stage-gate 前置检查 + --final-output 空阻断 + 37 项测试 + 触顶确认
  - v1.0.4 (2026-07-27) Independent-auditor round 3: stage-gate pre-check + --final-output empty blocking + 37 tests + top-trigger confirmation.
- v1.0.3 (2026-07-27) 独立审计长第 2 轮：workspace abspath 归一 + 可写性验证 + executor_prompt 对齐
  - v1.0.3 (2026-07-27) Independent-auditor round 2: workspace abspath normalization + writability verification + executor_prompt alignment.
- v1.0.2 (2026-07-27) 独立审计长第 1 轮：condition 沙箱属性链防护 + 死引用清理 + 10 项新测试
  - v1.0.2 (2026-07-27) Independent-auditor round 1: condition sandbox attribute-chain protection + dead-reference cleanup + 10 new tests.
- v1.0.1 (2026-07-26) 首轮优化：失败模式四列表 + 反例黑名单 + 否定性章节 + 6 个审计填充指导
  - v1.0.1 (2026-07-26) First-round optimization: four-column failure-mode table + anti-pattern blacklist + negated sections + 6 audit-filling guides.
- v1.0.0 (2026-07-26) 初版：6 阶段传送带 + 17 项回归测试 + 两个 prompt 模板 + 端到端 CLI 验证
  - v1.0.0 (2026-07-26) Initial version: 6-stage conveyor + 17 regression tests + two prompt templates + end-to-end CLI verification.

## 深度审计操作规范 (Deep Audit Operation Spec)

`references/audit-layers.md` 定义了 6 层深度审计方法论，并包含 **"主 Agent 后处理"**章节——审计长报告返回后主 Hermes 必须执行的 6 步收口流程（抽验→补跑 suite→P0→P1→P2修复→ad-hoc 验证→更新变更文件→收口）。任何触发深度审计的轮次都必须严格按此执行，不得跳过抽验或 ad-hoc 验证。

`references/audit-layers.md` defines the 6-layer deep-audit methodology and includes the **"Main Agent Post-processing"** section—the 6-step closure flow that main Hermes must execute after the auditor's report returns (sampling check → rerun suite → P0 → P1 → P2 fixes → ad-hoc verification → update change files → closure). Any round that triggers deep audit must strictly follow this; do not skip sampling checks or ad-hoc verification.

## 经验沉淀 (Lessons Learned)

20260726-001 unclekk-harness 落地 | 类别: 发现 | 教训: 从概念到 v1.0 落地 4 个 Phase 实际工作量 6-7 小时。Phase 1 核心 harness.py 34KB 964 行零依赖 stdlib 单文件，6 阶段 + 2 辅助命令；Phase 2 两个 prompt 模板（executor react-loop + reviewer ARIS）；Phase 3 自测 17/17 + CLI 端到端全流程跑通；Phase 4 SKILL.md + 本经验沉淀。两个真实 bug：(1) ingest 骨架 success_criteria 为空导致 plan validate 失败；(2) next_steps 返回的 dict 里 parallel_group 键总是存在导致误入并行分支。修复后全部解决。 | 规则: 落地新 orchestrator 类 skill 必须 (1) 先跑 CLI 全流程验证而非只跑单元测试；(2) condition 求值用沙箱 eval 禁 __builtins__；(3) 原子写用 temp + rename；(4) prompt 模板和代码分离，代码不改时模板可独立更新

20260726-001 unclekk-harness landed | Category: Discovery | Lesson: From concept to v1.0 landing, 4 Phases took 6–7 hours of actual work. Phase 1 core harness.py 34KB 964-line zero-dependency stdlib single file, 6 stages + 2 auxiliary commands; Phase 2 two prompt templates (executor react-loop + reviewer ARIS); Phase 3 self-test 17/17 + CLI end-to-end full flow passed; Phase 4 SKILL.md + this lesson log. Two real bugs: (1) ingest skeleton success_criteria empty caused plan validate failure; (2) the `parallel_group` key always present in the dict returned by `next_steps` caused erroneous entry into parallel branch. All resolved after fix. | Rule: Landing a new orchestrator-class skill must (1) first run CLI full-flow verification rather than only unit tests; (2) condition evaluation uses sandboxed eval forbidding `__builtins__`; (3) atomic writes use temp + rename; (4) prompt templates separated from code, templates independently updatable when code unchanged.

20260726-002 Darwin + SkillEvolver 集成 darwin/skill-evolver 元技能 | 类别: 发现 | 教训: darwin 和 skill-evolver 不是 unclekk 规划体系的组成部分，而是元技能（meta-skill）——输入是技能文件，输出是更好的技能文件，跟"帮我写报告"无关。集成只能是文档层面：告诉宿主 Agent 怎么在 harness 流水线的关键节点嵌入 darwin（9维评分）+ skill-evolver（策略多样化探索+对比更新+独立审计）+ skill-library（record+optimize 棘轮）。三层闭环：EXEC 每轮后 darwin dim8 评分 → AUDIT 阶段 aris-assurance 独立审计 → SETTLE 后 skill-library 沉淀+optimize。设计铁律：harness 不调 meta-skill，宿主 Agent 自己调用；workspace/dim8_scores.json 是可选文件，harness 不读它。本轮优化从 74→92，+18。 | 规则: (1) meta-skill 集成必须是文档指导型，不是代码嵌入型（orchestrator 不调 LLM 不调评分）；(2) skill-library 路径由宿主 Agent 自行指定，harness 不硬编码；(3) 独立审计必须用 delegate_task(role=leaf)，主 Agent 只生成补丁不读审计报告原文

20260726-002 Darwin + SkillEvolver integration darwin/skill-evolver meta-skill | Category: Discovery | Lesson: darwin and skill-evolver are not part of the unclekk planning system, but meta-skills—input is a skill file, output is a better skill file, unrelated to "help me write a report". Integration can only be at the documentation level: tell the host Agent how to embed darwin (9-dimension scoring) + skill-evolver (strategy-diversified exploration + comparative update + independent audit) + skill-library (record+optimize ratchet) at key pipeline nodes. Three-layer loop: after each EXEC round darwin dim8 scoring → AUDIT stage aris-assurance independent audit → after SETTLE skill-library deposit + optimize. Design iron rule: harness does not call meta-skill, host Agent calls it itself; `workspace/dim8_scores.json` is optional, harness doesn't read it. This round improved from 74→92, +18. | Rule: (1) meta-skill integration must be documentation-guidance type, not code-embedded type (orchestrator doesn't call LLM or scoring); (2) skill-library path specified by host Agent itself, harness doesn't hardcode; (3) independent audit must use delegate_task(role=leaf), main Agent only generates patches and doesn't read the audit report text.
