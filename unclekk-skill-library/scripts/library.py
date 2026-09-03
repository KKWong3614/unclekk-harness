#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unclekk-skill-library/scripts/library.py
=========================================
Voyager 式技能库：record + optimize 棘轮沉淀。

设计铁律（与 harness 一致）：
- 纯 stdlib，零第三方依赖；
- 所有写入走 temp + rename 原子写，防止中途崩溃损坏库文件；
- 棘轮只升不降：optimize 仅接受 pending_score >= 当前 score 的回写；
- 库是 harness 的「资源」，harness 自身不调用本脚本（由宿主 Agent 在 SETTLE 后调用）。

调用示例（相对 harness 根目录）：
    python unclekk-skill-library/scripts/library.py add \\
        --task-type "pipeline" \\
        --description "模糊复杂目标的端到端流水线" \\
        --approach "INGEST→PLAN→EXEC→REVIEW→AUDIT→SETTLE" \\
        --dimensions "拆解,执行,汇聚,审计,沉淀" --tags "unclekk,harness" --score 0.85
    python unclekk-skill-library/scripts/library.py find --query "模糊复杂目标"
    python unclekk-skill-library/scripts/library.py record --id pl_0001 --score 0.92
    python unclekk-skill-library/scripts/library.py optimize
"""
import argparse
import json
import sys
import time
from pathlib import Path

SCHEMA = "1.0"
DEFAULT_STORE = "unclekk-skill-library/store.json"


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)  # 原子替换，避免半写


def _load(store):
    p = Path(store)
    if not p.exists():
        return {"schema": SCHEMA, "entries": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        # 库文件损坏：保留 .corrupt 备份后从空库恢复，绝不静默丢失全部数据而不留痕
        backup = p.with_suffix(".corrupt")
        if not backup.exists():
            try:
                p.replace(backup)
            except OSError:
                pass
        return {"schema": SCHEMA, "entries": []}


def _next_id(entries):
    maxn = 0
    for e in entries:
        try:
            maxn = max(maxn, int(str(e.get("id", "pl_0")).split("_")[-1]))
        except Exception:
            pass
    return "pl_{:04d}".format(maxn + 1)


def cmd_add(args):
    data = _load(args.store)
    eid = _next_id(data["entries"])
    entry = {
        "id": eid,
        "task_type": args.task_type,
        "description": args.description,
        "approach": args.approach or "",
        "dimensions": [d.strip() for d in (args.dimensions or "").split(",") if d.strip()],
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
        "score": float(args.score) if args.score is not None else 0.0,
        "pending_score": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    data["entries"].append(entry)
    _atomic_write(args.store, data)
    print(json.dumps({"ok": True, "id": eid, "store": str(args.store)}, ensure_ascii=False))
    return 0


def cmd_find(args):
    data = _load(args.store)
    q = (args.query or "").lower()
    hits = []
    for e in data["entries"]:
        blob = " ".join([
            e.get("description", ""),
            e.get("approach", ""),
            e.get("task_type", ""),
            " ".join(e.get("tags", [])),
            " ".join(e.get("dimensions", [])),
        ]).lower()
        if q in blob:
            hits.append(e)
    if args.json:
        print(json.dumps({"ok": True, "count": len(hits), "hits": hits}, ensure_ascii=False))
    else:
        if not hits:
            print("(no match)")
        for e in hits:
            print("{}\t{}\tscore={}\t{}".format(
                e["id"], e.get("task_type", ""), e.get("score", 0), e.get("description", "")))
    return 0


def cmd_record(args):
    data = _load(args.store)
    for e in data["entries"]:
        if e["id"] == args.id:
            e["pending_score"] = float(args.score)
            e["updated_at"] = _now()
            _atomic_write(args.store, data)
            print(json.dumps({
                "ok": True, "id": args.id, "pending_score": args.score,
                "note": "run `optimize` to apply ratchet (only rises)",
            }, ensure_ascii=False))
            return 0
    print(json.dumps({"ok": False, "error": "id {} not found".format(args.id)}, ensure_ascii=False))
    return 1


def cmd_optimize(args):
    data = _load(args.store)
    promoted = []
    for e in data["entries"]:
        ps = e.get("pending_score")
        if ps is None:
            continue
        if ps >= e.get("score", 0):
            old = e.get("score", 0)
            e["score"] = ps
            e["pending_score"] = None
            e["updated_at"] = _now()
            promoted.append({"id": e["id"], "old": old, "new": ps})
        # 棘轮只升不降：pending_score < 当前分则保留 pending，等待更高分回写
    _atomic_write(args.store, data)
    print(json.dumps({
        "ok": True, "promoted": promoted,
        "note": "ratchet: score only rises; lower pending_score ignored",
    }, ensure_ascii=False))
    return 0


def cmd_list(args):
    data = _load(args.store)
    if args.json:
        print(json.dumps(data, ensure_ascii=False))
    else:
        for e in data["entries"]:
            print("{}\t{}\tscore={}\t{}".format(
                e["id"], e.get("task_type", ""), e.get("score", 0), e.get("description", "")))
    return 0


def cmd_stats(args):
    data = _load(args.store)
    n = len(data["entries"])
    avg = sum(e.get("score", 0) for e in data["entries"]) / n if n else 0
    print(json.dumps({"ok": True, "count": n, "avg_score": round(avg, 3)}, ensure_ascii=False))
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="UncleKK built-in skill library (Voyager-style ratchet)")
    p.add_argument("--store", default=DEFAULT_STORE, help="library store path (JSON)")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("add")
    a.add_argument("--task-type", required=True)
    a.add_argument("--description", required=True)
    a.add_argument("--approach", default="")
    a.add_argument("--dimensions", default="")
    a.add_argument("--tags", default="")
    a.add_argument("--score", default=0.0)
    a.set_defaults(func=cmd_add)

    f = sub.add_parser("find")
    f.add_argument("--query", default="")
    f.add_argument("--json", action="store_true")
    f.set_defaults(func=cmd_find)

    r = sub.add_parser("record")
    r.add_argument("--id", required=True)
    r.add_argument("--score", required=True, type=float)
    r.set_defaults(func=cmd_record)

    o = sub.add_parser("optimize")
    o.set_defaults(func=cmd_optimize)

    l = sub.add_parser("list")
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("stats")
    s.set_defaults(func=cmd_stats)
    return p


def main():
    args = build_parser().parse_args()
    if not getattr(args, "cmd", None):
        build_parser().print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
