# 库条目 Schema (Entry Schema)

`store.json` 结构：

```json
{
  "schema": "1.0",
  "entries": [
    {
      "id": "pl_0001",                 // 自动生成，pl_ + 4 位序号
      "task_type": "pipeline",        // 方案类型，建议 "pipeline"
      "description": "模糊复杂目标的端到端流水线",
      "approach": "INGEST→PLAN→EXEC→REVIEW→AUDIT→SETTLE",
      "dimensions": ["拆解", "执行", "汇聚", "审计", "沉淀"],
      "tags": ["unclekk", "harness"],
      "score": 0.85,                  // 当前质量分（棘轮值）
      "pending_score": null,          // 待回写分；optimize 时与 score 比较
      "created_at": "2026-08-28T12:00:00",
      "updated_at": "2026-08-28T12:00:00"
    }
  ]
}
```

## 字段说明

| 字段 | 含义 |
|------|------|
| `id` | 唯一标识，自动递增 |
| `task_type` | 方案类型；流水线统一用 `"pipeline"` |
| `description` | 方案一句话描述，供 `find` 命中 |
| `approach` | 关键步骤/方法论摘录 |
| `dimensions` | 涉及的维度标签（如拆解/执行/汇聚/审计/沉淀） |
| `tags` | 检索标签 |
| `score` | 当前质量分（0–1 或任意浮点），棘轮只升不降 |
| `pending_score` | 宿主 Agent 回写的待定分；`optimize` 时应用 |
| `created_at` / `updated_at` | ISO 本地时间戳 |

## 棘轮语义

`record --id X --score S` 仅写入 `pending_score = S`；`optimize` 遍历条目：

- 若 `pending_score >= score`：提升 `score = pending_score`，清空 pending；
- 若 `pending_score < score`：保留 pending，等待更高分回写（不回退）。
