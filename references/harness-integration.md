# unclekk-harness 集成说明

## 定位

unclekk-harness 不是替代 unclekk-roadmap-planner / unclekk-react-loop / unclekk-aris-assurance，
而是把三个技能的**协调层**抽出来做成一个可执行调度器，让它们在一个 workflow 里协同工作。

## 集成关系图

```
                    unclekk-harness (orchestrator)
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                  ▼
   INGEST/PLAN        EXEC                 AUDIT
         │                 │                  │
         ▼                 ▼                  ▼
   roadmap-planner   react-loop          aris-assurance
   (DAG schema +     (Thought/Action/   (3-stage claim
    topology +        Observation +       audit + adversarial
    validation)       stop rules)          review)
```

## 具体集成方式

| 源技能 | harness 阶段 | 集成模式 | 是否修改源技能 |
|--------|-------------|----------|----------------|
| roadmap-planner | INGEST | 复用 schema 定义，harness 生成 skeleton | 否 |
| roadmap-planner | PLAN | 复用 DAG 拓扑排序、condition 沙箱、validate | 否 |
| react-loop | EXEC | 输出 prompt_template 注入 react-loop 三段式 | 否 |
| aris-assurance | AUDIT | 生成 audit skeleton，后续由 Agent 跑完整三阶段 | 否 |

harness 不修改任何源技能的代码。集成层全部在 harness 内部实现。

## 宿主 Agent 适配

Hermes 和 WorkBuddy 使用完全相同的 harness 接口。唯一差异在 Agent 端：
- **Hermes**：用 `mcp__codebuddy_bridge__generate_code` 调用 CodeBuddy 写代码
- **WorkBuddy**：直接用 terminal 调用 WorkBuddy CLI

harness 本身不知道宿主是谁，只关心 `complete` / `error` 命令。
