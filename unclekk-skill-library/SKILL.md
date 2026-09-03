---
name: unclekk-skill-library
slug: unclekk-skill-library
version: 1.0.0
summary: Voyager 式技能库，record + optimize 棘轮沉淀流水线方案。Built-in library for the unclekk-harness orchestrator.
license: MIT
author: KK大叔 (UncleKK)
---

# unclekk-skill-library（内置技能库）

unclekk-harness 的**内置**技能库，作为 `unclekk-harness/` 的子目录同源存在。把跑通的高质量流水线方案沉淀成可复用条目，并在下次复用前用 `optimize` 棘轮提升。

> 设计铁律：库是 harness 的**资源**，harness 自身不调用它（orchestrator 不调 LLM / 不评分）；宿主 Agent 在 SETTLE 后自行调用。

## 命令 (Commands)

```bash
# 存入本次流水线方案（task_type 建议 "pipeline"）
python unclekk-skill-library/scripts/library.py add \
  --task-type "pipeline" \
  --description "模糊复杂目标的端到端流水线" \
  --approach "INGEST→PLAN→EXEC→REVIEW→AUDIT→SETTLE" \
  --dimensions "拆解,执行,汇聚,审计,沉淀" --tags "unclekk,harness" --score 0.85

# 复用：新任务查库命中方案
python unclekk-skill-library/scripts/library.py find --query "模糊复杂目标"

# 棘轮回写：跑完后回写验证分
python unclekk-skill-library/scripts/library.py record --id <id> --score <new>
python unclekk-skill-library/scripts/library.py optimize

# 其它
python unclekk-skill-library/scripts/library.py list
python unclekk-skill-library/scripts/library.py stats
```

## 棘轮规则 (Ratchet Rule)

`optimize` 仅接受 `pending_score >= 当前 score` 的回写；低于当前分的回写被忽略，保证库质量**只升不降**。

## 自测 (Self-Test)

```bash
cd unclekk-harness/unclekk-skill-library
python scripts/test_library.py
# 预期：ALL SKILL-LIBRARY TESTS PASSED
```

条目 schema 见 `references/schema.md`。
