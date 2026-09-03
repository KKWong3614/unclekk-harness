# 常见问题 (FAQ)

> 高频疑问集中汇总。遇到拿不准的，先查这张表。

## Q1：什么时候该用 harness，什么时候不该？

| 适合用 ✅ | 不该用 ❌（降级方案） |
|---|---|
| 模糊但复杂的多步骤目标（竞品分析、可行性调研） | 单步任务 → 直接用 `react-loop` |
| 任务有明显先后依赖或可并行 | 3 步以内小 DAG → `roadmap-planner` 单独用 |
| 怕方向跑偏 / 中途漏关键步骤 | 步骤已明确的机械任务 → 手动列步骤 |
| 需要可审计、可暂停、可恢复的记录 | 目标模糊到 LLM 都拆不出 → 先对话澄清 |
| | 任务随时中断且恢复成本高 → 用内存草稿 |

详见 SKILL.md「什么时候用 / 什么时候不用」。

## Q2：audit 阶段为什么只生成骨架，不是结论？

harness 是 **orchestrator 不是 executor**，不调 LLM、不评分。它负责生成 `integrity_checklist / claim_ledger / claim_audit_report` 三个**占位骨架**，真正的证据填充由宿主 Agent + 异族 Reviewer 完成（模板见 `templates/reviewer_prompt.md`）。这正是「大幅减少 AI 幻觉」的抓手——每条声明必须映射到上游 task 的真实产出。

## Q3：内置技能库 `unclekk-skill-library` 怎么用？

SETTLE 后，宿主 Agent 自行调用（harness 不自动调它）：

```bash
python unclekk-skill-library/scripts/library.py add --task-type pipeline --description "..." --score 0.85
python unclekk-skill-library/scripts/library.py find --query "..."
python unclekk-skill-library/scripts/library.py record --id pl_0001 --score 0.95
python unclekk-skill-library/scripts/library.py optimize
```

`optimize` 棘轮**只升不降**：只接受 `pending_score >= 当前分` 的回写。条目 schema 见 `unclekk-skill-library/references/schema.md`。

## Q4：condition 沙箱安全吗？会不会被注入？

安全。condition 表达式走 **AST 白名单**（`_condition_allowlisted`）：只允许读 `outputs`/`context`/`goal`，仅开放 `len`/`bool`/`str`/`int`/`float`/`any`/`all` 等纯函数，禁 `__builtins__` 与任何副作用（文件 I/O、网络、导入）。7 类逃逸向量（`__import__`、`().__class__` 链、`open` 等）经验证全部被拦截。若用了白名单外标识符，表达式静默返回 `False`（任务被 skip），不会执行恶意代码。

## Q5：state.json 被改坏了怎么恢复？

harness 用 `temp + rename` 原子写，正常不会半写。若被人为/并发编辑破坏（JSON 合法但字段缺失），用 `python scripts/harness.py <cmd> --state X --recover` 从 `execution_log` 重建任务状态（`_load(recover=True)`）。完全不可恢复时，用 `ingest` 重生成 skeleton 从最近 checkpoint 继续。

## Q6：能多个 Agent 并发操作同一个 state.json 吗？

不能保证并发安全。harness 只保证**原子写**，无跨进程文件锁。多个 Agent 必须用各自独立的 `--state` 文件，或串行操作同一 state。

## Q7：和直接用 roadmap-planner 有什么区别？

roadmap-planner 只做「规划」（拆解 + DAG）。harness 在其上叠加 **执行调度（EXEC react-loop 模板）+ 产出聚合（REVIEW）+ 对抗审计（AUDIT）+ 交付（SETTLE）+ 可恢复状态机**。简单拆解用 planner 即可；要「规划→执行→审计→交付」闭环才上 harness。

## Q8：能在 Python 代码里直接调用，而不是命令行吗？

可以。harness.py 是纯函数式模块，可直接 import：

```python
import sys
sys.path.insert(0, "scripts")
import harness as H
state = H.ingest(goal="...", workspace="...", out="harness_state.json")
H.plan("harness_state.json")
nxt = H.exec("harness_state.json")
H.complete("harness_state.json", task_id=1, output="...")
H.review("harness_state.json")
H.audit("harness_state.json", output_dir="...")
H.settle("harness_state.json", final_output="# ...")
```

（`ingest/plan/exec/complete/review/audit/settle/status` 均为模块顶层函数，仅依赖 stdlib。）

## Q9：版本号对不上怎么办？

所有版本号（SKILL.md frontmatter / package.json / _meta.json / README / CHANGELOG）由发布流程统一对齐。若你本地看到不一致，说明是发布中间态——以 `package.json` 的 `version` 字段为准。

## Q10：报错信息里的 `H-xxxx` 错误码是什么意思？

harness 把常见失败模式归并为错误码，便于检索。完整映射见 SKILL.md「错误码速查」一节。常见：
- `H-1001` validate 失败（subtasks 字段不全）
- `H-2002` 依赖未 done 就 complete
- `H-3003` condition 用了白名单外标识符
- `H-7007` `--final-output` 为空或过短
- `H-8008` state.json 被损坏
