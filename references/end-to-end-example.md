# 端到端实战示例 (End-to-End Worked Example)

> 一个从 `ingest` 到 `settle` 的完整可复制案例。所有命令均可直接照抄（改路径即可）。
> 目标：*"写一份 X 平台竞品分析，对比 A / B / C 三家"*。

## 0. 准备

```bash
HARNESS="C:/Users/user/.workbuddy/skills/@user_48f048de/unclekk-harness"
WS="C:/Users/user/WorkBuddy/2026-08-28/competitor-analysis"   # 绝对路径，提前建好
mkdir -p "$WS"
cd "$HARNESS"
```

## 1. INGEST — 接目标，生成 skeleton

```bash
python scripts/harness.py ingest \
  --goal "写一份 X 平台竞品分析，对比 A/B/C 三家产品的功能、定价、口碑" \
  --workspace "$WS" \
  --out "$WS/harness_state.json"
```

输出（节选）：

```json
{
  "schema": "1.0",
  "goal": "写一份 X 平台竞品分析，对比 A/B/C 三家产品的功能、定价、口碑",
  "workspace": "C:/Users/user/WorkBuddy/2026-08-28/competitor-analysis",
  "stage": "ingest",
  "subtasks": [
    { "subtask_id": 1, "subtask_description": "[LLM: 待填充]", "status": "pending", "output": "" }
  ],
  "checkpoint_ok": false
}
```

> ⚠️ skeleton 只有一个 `[LLM: 待填充]` 占位 subtask。必须先用 LLM 把它填实（见下一步），否则 `plan` 会报 validate 错误。

## 2. FILL — 宿主 Agent 用 LLM 填实 subtasks

宿主 Agent 把 skeleton 替换成真实拆解（多步 + 依赖 + success_criteria）：

```json
"subtasks": [
  { "subtask_id": 1, "subtask_description": "收集 A 产品资料（功能/定价/口碑）",
    "exact_input": "目标平台 X", "expected_output": "A 资料卡",
    "success_criteria": "覆盖功能、定价、口碑三栏", "depends_on": [], "status": "pending", "output": "" },
  { "subtask_id": 2, "subtask_description": "收集 B 产品资料", "depends_on": [], "status": "pending", "output": "" },
  { "subtask_id": 3, "subtask_description": "收集 C 产品资料", "depends_on": [], "status": "pending", "output": "" },
  { "subtask_id": 4, "subtask_description": "横向对比生成报告", "depends_on": [1,2,3], "status": "pending", "output": "" }
]
```

## 3. PLAN — 校验 DAG

```bash
python scripts/harness.py plan --state "$WS/harness_state.json"
```

输出：

```json
{ "ok": true, "topo": [1, 2, 3, 4], "🛑 CHECKPOINT": "confirm and continue" }
```

> 🛑 关键检查点：确认拓扑序与依赖无误后再继续。

## 4. EXEC → complete 循环

```bash
python scripts/harness.py exec --state "$WS/harness_state.json"
# → 返回 next_tasks: [1]，含 prompt_template（react-loop 三段式）
# 宿主 Agent 按模板执行 Thought/Action/Observation 收集 A 资料
python scripts/harness.py complete --state "$WS/harness_state.json" --id 1 --output "A 资料卡：功能…定价…口碑…"
# 继续 exec → 2 → complete → 3 → complete
python scripts/harness.py exec --state "$WS/harness_state.json"
# → next_tasks: [4]（依赖 1/2/3 已 done）
# 宿主 Agent 汇总生成报告
python scripts/harness.py complete --state "$WS/harness_state.json" --id 4 --output "# X 平台竞品分析\n…"
# 再 exec → "ALL TASKS DONE" → 停止，转 review
```

## 5. REVIEW — 聚合产出

```bash
python scripts/harness.py review --state "$WS/harness_state.json"
# → aggregated_outputs: {1:.., 2:.., 3:.., 4: 报告}
```

## 6. AUDIT — 生成审计骨架（关键：大幅减少 AI 幻觉）

```bash
python scripts/harness.py audit --state "$WS/harness_state.json" --output-dir "$WS"
# → 生成 3 个骨架文件：
#   integrity_checklist.md   — 声明 ↔ 证据 完整性清单
#   claim_ledger.md          — 每条声明的事实来源台账
#   claim_audit_report.md    — 三阶段对抗审计结果
```

> 这一步是「大幅减少 AI 幻觉」的核心：harness 只生成**骨架**，宿主 Agent + 异族 Reviewer 必须把每条声明映射到上游 task 的真实产出（claim_ledger），未举证的声明在 `settle` 前必须补全或删除。

## 7. SETTLE — 输出交付

```bash
python scripts/harness.py settle \
  --state "$WS/harness_state.json" \
  --final-output "# X 平台竞品分析\n\n## A 产品\n…（每条结论均见 claim_ledger 证据）\n\n## B 产品\n…\n\n## C 产品\n…\n\n## 横向对比\n…"
# → 写入 $WS/final_output.md + 完整 summary
```

## 8. 沉淀到内置技能库（可选，SETTLE 后）

```bash
python unclekk-skill-library/scripts/library.py add \
  --task-type "pipeline" \
  --description "竞品对比分析流水线" \
  --approach "INGEST→PLAN→EXEC→REVIEW→AUDIT→SETTLE" \
  --dimensions "拆解,执行,汇聚,审计,沉淀" --tags "competitor,analysis" --score 0.9
# 复用：
python unclekk-skill-library/scripts/library.py find --query "竞品"
```

## 9. 状态查看

```bash
python scripts/harness.py status --state "$WS/harness_state.json"
# → stage: settled, done: 4, pending: 0, error: 0
```

---

**完整文件清单（本例产物）**

```
competitor-analysis/
├── harness_state.json          # 全流程状态机
├── final_output.md             # SETTLE 输出
├── integrity_checklist.md      # 审计骨架
├── claim_ledger.md             # 声明证据台账
└── claim_audit_report.md       # 对抗审计结果
```
