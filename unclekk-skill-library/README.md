# unclekk-skill-library · 内置技能库

unclekk-harness 的 Voyager 式技能库子包：把跑通的流水线方案沉淀进库，并用 `optimize` 棘轮在复用前提升质量。

- 纯 stdlib，零依赖
- 原子写（temp + rename）
- 棘轮只升不降

## 快速开始

```bash
cd unclekk-harness/unclekk-skill-library
python scripts/library.py add --task-type pipeline --description "..." --score 0.85
python scripts/library.py find --query "..."
python scripts/library.py record --id pl_0001 --score 0.95
python scripts/library.py optimize
```

详见本目录 `SKILL.md` 与 `references/schema.md`。
