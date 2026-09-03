#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""unclekk-skill-library 回归测试（纯 stdlib，无依赖）。"""
import json
import os
import subprocess
import sys
import tempfile

STORE = os.path.join(tempfile.mkdtemp(), "lib.json")
LIB = os.path.join(os.path.dirname(__file__), "library.py")


def run(*a):
    return subprocess.run(
        [sys.executable, LIB, "--store", STORE, *a],
        capture_output=True, text=True,
    )


def test_add():
    r = run("add", "--task-type", "pipeline",
            "--description", "模糊复杂目标的端到端流水线",
            "--approach", "INGEST→PLAN→EXEC→REVIEW→AUDIT→SETTLE",
            "--dimensions", "拆解,执行,汇聚", "--tags", "unclekk,harness",
            "--score", "0.85")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["ok"]
    assert os.path.exists(STORE)


def test_find():
    r = run("find", "--query", "模糊", "--json")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["count"] >= 1
    rid = d["hits"][0]["id"]
    # 复用 id 供后续测试
    return rid


def test_ratchet_rises():
    rid = test_find()
    # 回写更高分 → optimize 应提升
    r = run("record", "--id", rid, "--score", "0.95")
    assert json.loads(r.stdout)["ok"]
    r = run("optimize")
    promoted = json.loads(r.stdout)["promoted"]
    assert any(p["id"] == rid for p in promoted)
    # 回写更低分 → 棘轮不降
    r = run("record", "--id", rid, "--score", "0.10")
    run("optimize")
    data = json.loads(open(STORE, encoding="utf-8").read())
    e = [x for x in data["entries"] if x["id"] == rid][0]
    assert e["score"] == 0.95, "ratchet must never drop: got {}".format(e["score"])


def test_stats():
    r = run("stats")
    assert r.returncode == 0
    assert json.loads(r.stdout)["count"] >= 1


if __name__ == "__main__":
    test_add()
    test_ratchet_rises()
    test_stats()
    print("ALL SKILL-LIBRARY TESTS PASSED")
