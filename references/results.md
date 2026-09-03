# 评分棘轮账本 (Score Ratchet Ledger)

harness 自身的 9 维评分棘轮记录，格式与 darwin-skill 的 results 账本对齐（列：时间戳 / commit / skill / 旧分 / 新分 / 状态 / 维度 / 备注 / 评测模式）。

| timestamp | commit | skill | old_score | new_score | status | dimension | note | eval_mode |
|-----------|--------|-------|-----------|-----------|--------|-----------|------|-----------|
| 2026-07-26 | v1.0.1 | unclekk-harness | 74 | 92 | improve | dim1-9 | darwin+skillevolver 元技能集成（3 层闭环：EXEC 后 darwin 评分→AUDIT 对抗审计→SETTLE 后 skill-library 沉淀+optimize） | full |
