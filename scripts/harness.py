#!/usr/bin/env python3
"""
unclekk-harness: 6-stage autonomous pipeline.
Wires roadmap-planner → react-loop → aris-assurance into one self-contained
orchestration loop.  Zero third-party dependencies (stdlib only).

Stages:
  INGEST → PLAN → EXEC → REVIEW → AUDIT → SETTLE

The harness is an **orchestrator, not an executor**.  It tells the host
agent (Hermes / WorkBuddy) *what to do next* and *in what order*; the agent
performs the actual LLM calls and tool invocations.

Usage:
  python harness.py ingest --goal "..." --out harness_state.json
  python harness.py plan   --state harness_state.json
  python harness.py exec   --state harness_state.json
  python harness.py review --state harness_state.json
  python harness.py audit  --state harness_state.json
  python harness.py settle --state harness_state.json
  python harness.py status --state harness_state.json
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
SCHEMA_VERSION = "1.0"
SUBTASK_STATUS = ("pending", "running", "done", "skipped", "error")

# --------------------------------------------------------------------------- #
# State model
# --------------------------------------------------------------------------- #


def new_state(goal: str, workspace: str) -> Dict[str, Any]:
    """Create a fresh harness state dict."""
    return {
        "schema": SCHEMA_VERSION,
        "based_on": "unclekk-harness: roadmap-planner + react-loop + aris-assurance",
        "goal": goal,
        "workspace": os.path.abspath(workspace),
        "stage": "init",
        "started_at": _now(),
        "updated_at": None,
        # Roadmap (from INGEST/PLAN)
        "mode": "complex",
        "context": {},
        "worker_pool": {},
        "subtasks": [],
        # Execution log (from EXEC)
        "execution_log": [],
        # Aggregated outputs (from REVIEW)
        "aggregated_outputs": {},
        # Audit artifacts (from AUDIT)
        "audit": {
            "integrity_checklist": None,
            "claim_ledger": None,
            "claim_audit_report": None,
        },
        # Checkpoint gate
        "checkpoint_ok": False,
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _touch(state: Dict[str, Any]) -> None:
    state["updated_at"] = _now()


# --------------------------------------------------------------------------- #
# Atomic write
# --------------------------------------------------------------------------- #
def _atomic_write(path: str, data: Any) -> None:
    """JSON-serialise and atomically write to *path* via temp file + rename."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        tmp.replace(p)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _load(path: str, recover: bool = False) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        if recover:
            return _recover_state_from_log(path, "")
        raise FileNotFoundError(f"State file not found: {path}")
    raw = p.read_text(encoding="utf-8")
    try:
        state: Dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        if recover:
            return _recover_state_from_log(path, raw)
        raise
    if not isinstance(state, dict):
        if recover:
            return _recover_state_from_log(path, raw)
        raise ValueError("State file root is not a JSON object")
    missing = [k for k in ("subtasks", "execution_log") if k not in state]
    if missing and recover:
        recovered = _recover_state_from_log(path, raw)
        for k in ("subtasks", "execution_log"):
            if k not in recovered:
                recovered[k] = []
        return recovered
    if "subtasks" not in state:
        state.setdefault("subtasks", [])
    if "execution_log" not in state:
        state.setdefault("execution_log", [])
    return state


def _recover_state_from_log(path: str, raw: str = "") -> Dict[str, Any]:
    """Build the smallest usable state from a damaged state.json.

    The harness is an orchestrator, so the safest recovery is to keep
    provenance (goal / workspace / started_at) and re-derive task
    progress from the execution_log when the log itself survives.
    """
    recovery: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "based_on": "",
        "goal": "(recovered)",
        "workspace": "",
        "stage": "recovered",
        "started_at": "",
        "updated_at": "",
        "mode": "complex",
        "context": {},
        "worker_pool": {},
        "subtasks": [],
        "execution_log": [],
        "aggregated_outputs": {},
        "audit": {"integrity_checklist": None, "claim_ledger": None, "claim_audit_report": None},
        "checkpoint_ok": False,
    }
    try:
        candidate = json.loads(raw)
        if isinstance(candidate, dict):
            for key in ("goal", "workspace", "started_at", "stage", "execution_log"):
                if key in candidate and candidate[key] is not None:
                    recovery[key] = candidate[key]
            if isinstance(recovery["execution_log"], list):
                ids = {int(e.get("subtask_id")) for e in recovery["execution_log"]
                       if isinstance(e, dict) and e.get("subtask_id") is not None}
                statuses = {
                    int(e.get("subtask_id")): e.get("status", "done")
                    for e in recovery["execution_log"]
                    if isinstance(e, dict) and e.get("subtask_id") is not None
                }
                for sid in sorted(ids):
                    preview = next(
                        (
                            e.get("output_preview") or e.get("output") or e.get("error") or ""
                            for e in recovery["execution_log"]
                            if isinstance(e, dict) and e.get("subtask_id") == sid
                        ),
                        "",
                    )
                    recovery["subtasks"].append({
                        "subtask_id": sid,
                        "subtask_description": "Recovered from execution_log",
                        "exact_input": "",
                        "expected_output": "",
                        "success_criteria": "Recovered from execution_log",
                        "desired_auxiliary_tools": [],
                        "depends_on": [],
                        "parallel_group": None,
                        "condition": None,
                        "assigned_worker": None,
                        "status": statuses.get(sid, "done"),
                        "output": str(preview),
                    })
    except json.JSONDecodeError:
        pass
    if not recovery["subtasks"] and not recovery["execution_log"]:
        raise ValueError(
            f"State file {path} is corrupted and cannot be recovered. "
            "Recovery advice: restore from backup, or run 'ingest' again with the original goal "
            "and a fresh state file. Partial recovery is only possible when execution_log survives."
        )
    return recovery


# --------------------------------------------------------------------------- #
# STAGE 1: INGEST
# --------------------------------------------------------------------------- #
def stage_ingest(goal: str, workspace: str, out: str, **_kw) -> Dict[str, Any]:
    """
    Take a natural-language goal and emit a boilerplate roadmap.json.
    The host agent should use an LLM to fill subtasks; the skeleton below
    gives the schema the agent needs to start with.
    """
    # Validate workspace is writable + normalize to absolute path so audit
    # artifacts and final_output.md land exactly where the agent expects.
    workspace = os.path.abspath(workspace)
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    if not ws.is_dir() or not os.access(ws, os.W_OK):
        raise PermissionError(
            f"Workspace not writable or not a directory: {workspace}. "
            "Pass an existing, writable absolute path via --workspace."
        )
    state = new_state(goal, workspace)
    state["stage"] = "ingest"
    _touch(state)

    # Minimal starter subtasks — the agent replaces these with real ones
    state["subtasks"] = [
        {
            "subtask_id": 1,
            "subtask_description": "[LLM: replace with first concrete step]",
            "exact_input": "",
            "expected_output": "",
            "success_criteria": "step completed and output recorded",
            "desired_auxiliary_tools": [],
            "depends_on": [],
            "parallel_group": None,
            "condition": None,
            "assigned_worker": None,
            "status": "pending",
            "output": "",
        }
    ]
    _atomic_write(out, state)
    return state


# --------------------------------------------------------------------------- #
# STAGE 2: PLAN
# --------------------------------------------------------------------------- #

# -- Validation helpers --


def validate_state(state: Dict[str, Any]) -> List[str]:
    """Return a list of validation errors (empty = OK).

    Rejects placeholder descriptions emitted by ingest's skeleton (anything
    starting with ``[LLM:``) so that the pipeline cannot silently ``plan``
    past the INGEST stage before the host agent has filled in real subtasks.
    """
    _PLACEHOLDER_PREFIX = "[LLM:"
    errors: List[str] = []
    subtasks = state.get("subtasks", [])

    # Required fields
    for st in subtasks:
        sid = st.get("subtask_id")
        if not st.get("subtask_description", "").strip():
            errors.append(f"subtask #{sid}: missing subtask_description")
        desc = st.get("subtask_description", "").strip()
        if desc.startswith(_PLACEHOLDER_PREFIX):
            errors.append(
                f"subtask #{sid}: placeholder description not replaced "
                f"(still '{desc}'). Host agent must fill in real subtasks "
                f"before running 'plan'."
            )
        if not st.get("success_criteria", "").strip():
            errors.append(f"subtask #{sid}: missing success_criteria")
        if st.get("status") not in SUBTASK_STATUS:
            errors.append(f"subtask #{sid}: invalid status '{st.get('status')}'")

    # Duplicate IDs
    seen = {st["subtask_id"] for st in subtasks}
    if len(seen) != len(subtasks):
        errors.append("duplicate subtask_id detected")

    # DAG cycle detection (DFS)
    adj = {st["subtask_id"]: st.get("depends_on", []) for st in subtasks}
    visiting, visited = set(), set()
    stack: List[int] = []

    def _dfs(node: int) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in adj.get(node, []):
            if dep not in adj:
                errors.append(
                    f"subtask #{node}: depends on unknown subtask #{dep}"
                )
                continue
            if _dfs(dep):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    for node in list(adj.keys()):
        if node not in visited:
            if _dfs(node):
                errors.append(f"cycle detected involving subtask #{node}")
                break

    return errors


def topo_order(state: Dict[str, Any]) -> List[int]:
    """Return subtask IDs in DAG topological order (skipped also counted)."""
    subtasks = state["subtasks"]
    ids = [st["subtask_id"] for st in subtasks]
    adj = {st["subtask_id"]: st.get("depends_on", []) for st in subtasks}
    indegree = {i: 0 for i in ids}
    for i in ids:
        for dep in adj.get(i, []):
            if dep in indegree:
                indegree[dep] += 0  # just ensure key exists
        indegree[i] = len(adj.get(i, []))

    queue = [i for i in ids if indegree[i] == 0]
    order: List[int] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for child in ids:
            if n in adj.get(child, []):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
    return order


_CONDITION_ALLOWLIST = frozenset(
    {"outputs", "context", "goal", "len", "bool", "str", "int", "float", "any", "all"}
)


def _condition_allowlisted(condition: str) -> bool:
    """Token-level allowlist check for condition expressions.

    Non-allowlisted identifiers are rejected early so that even if the
    sandbox globals leak, an attacker cannot reach names they should not.
    """
    try:
        tree = ast.parse(condition.strip(), mode="eval")
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in _CONDITION_ALLOWLIST:
            return False
        if isinstance(node, ast.Attribute):
            # Only allow .get() on an allowlisted dict-like name (e.g.
            # outputs.get("key")).  Reject all other attribute traversal
            # (e.g. outputs.__class__, outputs.__dict__) — these defeat
            # the sandbox even when the root name is allowlisted.
            if isinstance(node.value, ast.Name):
                if node.value.id not in _CONDITION_ALLOWLIST:
                    return False
                if node.attr != "get":
                    return False
            else:
                return False
        if isinstance(node, (ast.Call, ast.Subscript, ast.Assign, ast.AugAssign)):
            pass  # allowed on allowlisted names (e.g. len(x), x[1])
        if isinstance(node, (ast.Lambda, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
            return False
    return True


def eval_condition(condition: Optional[str], outputs: Dict[str, str], context: Dict[str, Any]) -> Optional[bool]:
    """
    Evaluate a condition string in a safe sandbox.
    Returns True/False, or None if condition is None/empty.
    Allowed globals: outputs (dict), context (dict), goal (str), len, bool,
    str, int, float, any, all.
    """
    if not condition:
        return None
    if not _condition_allowlisted(condition):
        return False
    safe_globals: Dict[str, Any] = {
        "outputs": outputs,
        "context": context,
        "goal": "",
        "len": len,
        "bool": bool,
        "str": str,
        "int": int,
        "float": float,
        "any": any,
        "all": all,
    }
    try:
        return bool(eval(condition, safe_globals, {}))
    except Exception:
        return False


def _get_outputs(state: Dict[str, Any]) -> Dict[str, str]:
    return {
        str(st["subtask_id"]): st.get("output", "")
        for st in state.get("subtasks", [])
    }


def next_steps(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return the next group of subtasks to execute.
    Groups that belong to the same parallel_group are returned together.
    """
    outputs = _get_outputs(state)
    context = state.get("context", {})
    subtasks = {st["subtask_id"]: st for st in state["subtasks"]}

    ready: List[Dict[str, Any]] = []
    for st in state.get("subtasks", []):
        sid = st["subtask_id"]
        if st["status"] not in ("pending",):
            continue
        # Dependencies satisfied?
        deps = st.get("depends_on", [])
        deps_ok = all(
            subtasks.get(d, {}).get("status") in ("done", "skipped") for d in deps
        )
        if not deps_ok:
            continue
        # Condition satisfied?
        cond = eval_condition(st.get("condition"), outputs, context)
        if cond is False:
            st["status"] = "skipped"
            _touch(state)
            continue
        ready.append(st)

    if not ready:
        return []

    # Group by parallel_group
    groups: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for st in ready:
        g = st.get("parallel_group")
        groups.setdefault(g, []).append(st)

    result: List[Dict[str, Any]] = []
    for g, members in groups.items():
        if len(members) > 1:
            # Return as a parallel group
            result.append({"parallel_group": g, "subtasks": members})
        else:
            result.extend(members)
    return result


def stage_plan(state_path: str, **_kw) -> Dict[str, Any]:
    state = _load(state_path)
    state["stage"] = "plan"
    errors = validate_state(state)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return state
    order = topo_order(state)
    _touch(state)
    _atomic_write(state_path, state)
    print(json.dumps({
        "ok": True,
        "topological_order": order,
        "subtask_count": len(state.get("subtasks", [])),
        "message": "Plan validated. READY for EXEC. 🛑 CHECKPOINT: confirm and continue.",
    }, indent=2, ensure_ascii=False))
    return state


# --------------------------------------------------------------------------- #
# STAGE 3: EXEC
# --------------------------------------------------------------------------- #

REACT_TEMPLATE = """\
You are executing subtask #{subtask_id}: {description}.

Use the ReAct pattern — Thought / Action / Observation — for every step.
Each Thought must reference the previous Observation.

- Exact input context: {exact_input}
- Expected output: {expected_output}
- Success criteria: {success_criteria}
- Suggested tools: {tools}

Start with a Thought about what to do first.
"""


def _format_task_prompt(st: Dict[str, Any]) -> str:
    return REACT_TEMPLATE.format(
        subtask_id=st["subtask_id"],
        description=st.get("subtask_description", ""),
        exact_input=st.get("exact_input", ""),
        expected_output=st.get("expected_output", ""),
        success_criteria=st.get("success_criteria", ""),
        tools=", ".join(st.get("desired_auxiliary_tools", [])) or "use available tools",
    )


def stage_exec(state_path: str, task_id: Optional[int] = None,
               recover: bool = False, **_kw) -> Dict[str, Any]:
    """
    Report the next task(s) to the host agent.
    If task_id is provided, the agent has completed that task and should
    mark it done (call stage_complete instead).
    """
    try:
        state = _load(state_path, recover=recover)
    except (json.JSONDecodeError, ValueError) as exc:
        if recover:
            state = _recover_state_from_log(state_path, "")
        else:
            raise
    # Force the stage into the active pipeline branch so that recovery
    # from a truncated/corrupt state can resume execution immediately;
    # callers without --recover are unaffected.
    if recover:
        state["stage"] = "exec"
    if state["stage"] not in ("plan", "exec", "review"):
        print(json.dumps({
            "ok": False,
            "error": f"Must be in plan/exec/review stage, got '{state['stage']}'. Run 'plan' first.",
        }, indent=2))
        return state

    state["stage"] = "exec"
    state["checkpoint_ok"] = False
    ready = next_steps(state)

    if not ready:
        # Check if all done or stuck
        all_statuses = [st["status"] for st in state.get("subtasks", [])]
        if all(s in ("done", "skipped") for s in all_statuses):
            _touch(state)
            _atomic_write(state_path, state)
            print(json.dumps({
                "ok": True, "message": "ALL TASKS DONE — proceed to REVIEW",
                "status": "complete",
            }, indent=2))
            return state

        errors = [st for st in state.get("subtasks", []) if st["status"] == "error"]
        if errors:
            _touch(state)
            _atomic_write(state_path, state)
            print(json.dumps({
                "ok": False,
                "error": "ERROR tasks remain",
                "error_tasks": [e["subtask_id"] for e in errors],
            }, indent=2))
            return state

        _touch(state)
        _atomic_write(state_path, state)
        print(json.dumps({
            "ok": True,
            "message": "No ready tasks but not all complete. Run 'status' to inspect.",
            "pending": [st["subtask_id"] for st in state["subtasks"] if st["status"] == "pending"],
        }, indent=2))
        return state

    # Format output
    items: List[Dict[str, Any]] = []
    for item in ready:
        group_name = item.get("parallel_group")
        if group_name:
            tasks_out = []
            for st in item["subtasks"]:
                tasks_out.append({
                    "id": st["subtask_id"],
                    "description": st["subtask_description"],
                    "prompt_template": _format_task_prompt(st),
                    "tools": st.get("desired_auxiliary_tools", []),
                    "success_criteria": st.get("success_criteria", ""),
                })
            items.append({
                "type": "parallel_group",
                "group_name": item["parallel_group"],
                "tasks": tasks_out,
            })
        else:
            st = item
            items.append({
                "type": "single",
                "id": st["subtask_id"],
                "description": st["subtask_description"],
                "prompt_template": _format_task_prompt(st),
                "tools": st.get("desired_auxiliary_tools", []),
                "success_criteria": st.get("success_criteria", ""),
            })

    _touch(state)
    _atomic_write(state_path, state)
    print(json.dumps({
        "ok": True,
        "stage": "exec",
        "checkpoint": "🛑 CHECKPOINT: host agent must execute these tasks, then call 'complete' for each.",
        "next_tasks": items,
    }, indent=2, ensure_ascii=False))
    return state


# --------------------------------------------------------------------------- #
# STAGE COMPLETE (called by host agent after executing a task)
# --------------------------------------------------------------------------- #
def stage_complete(state_path: str, task_id: int, output: str = "",
                   **_kw) -> Dict[str, Any]:
    state = _load(state_path)
    found = None
    for st in state.get("subtasks", []):
        if st["subtask_id"] == task_id:
            found = st
            break
    if found is None:
        print(json.dumps({"ok": False, "error": f"No subtask #{task_id}"}))
        return state

    # Validate dependencies are satisfied
    deps = found.get("depends_on", [])
    subtasks = {st["subtask_id"]: st for st in state["subtasks"]}
    for d in deps:
        parent = subtasks.get(d)
        if parent and parent.get("status") not in ("done", "skipped"):
            print(json.dumps({
                "ok": False,
                "error": f"Dependency #{d} not done/skipped",
            }))
            return state

    found["status"] = "done"
    found["output"] = output
    entry = {
        "timestamp": _now(),
        "subtask_id": task_id,
        "status": "done",
        "output_preview": output[:200] if output else "",
    }
    state.setdefault("execution_log", []).append(entry)
    _touch(state)
    _atomic_write(state_path, state)
    print(json.dumps({
        "ok": True,
        "subtask_id": task_id,
        "status": "done",
        "message": f"Subtask #{task_id} marked done.",
    }, indent=2))
    return state


def stage_error(state_path: str, task_id: int, error_msg: str = "",
                **_kw) -> Dict[str, Any]:
    state = _load(state_path)
    for st in state.get("subtasks", []):
        if st["subtask_id"] == task_id:
            st["status"] = "error"
            st["output"] = error_msg
            break
    entry = {
        "timestamp": _now(),
        "subtask_id": task_id,
        "status": "error",
        "error": error_msg,
    }
    state.setdefault("execution_log", []).append(entry)
    _touch(state)
    _atomic_write(state_path, state)
    print(json.dumps({
        "ok": True,
        "subtask_id": task_id,
        "status": "error",
        "message": f"Subtask #{task_id} marked error.",
    }, indent=2))
    return state


# --------------------------------------------------------------------------- #
# STAGE 4: REVIEW
# --------------------------------------------------------------------------- #

def stage_review(state_path: str, **_kw) -> Dict[str, Any]:
    state = _load(state_path)
    if state["stage"] not in ("exec", "review"):
        print(json.dumps({
            "ok": False,
            "error": f"Must be in exec/review stage, got '{state['stage']}'. "
                     "Execute all tasks (or reach ALL TASKS DONE) before 'review'.",
        }, indent=2))
        return state
    state["stage"] = "review"
    outputs = _get_outputs(state)

    # Filter to only done tasks' outputs
    aggregated = {
        k: v for k, v in outputs.items() if v and k in {
            str(st["subtask_id"]) for st in state["subtasks"] if st["status"] == "done"
        }
    }
    state["aggregated_outputs"] = aggregated
    _touch(state)
    _atomic_write(state_path, state)

    counts = {s: sum(1 for st in state["subtasks"] if st["status"] == s)
              for s in SUBTASK_STATUS}
    print(json.dumps({
        "ok": True,
        "stage": "review",
        "message": "Outputs aggregated. Proceed to AUDIT.",
        "counts": counts,
        "output_keys": list(aggregated.keys()),
    }, indent=2, ensure_ascii=False))
    return state


# --------------------------------------------------------------------------- #
# STAGE 5: AUDIT
# --------------------------------------------------------------------------- #

CLAIM_LEDGER_TEMPLATE = """\
| # | 声明(原文句子) | 证据来源(文件/行/截图) | 支撑强度 | 缺口 |
|---|---|---|---|---|
| C1 | {example_claim} | {example_evidence} | 弱 | 缺直接证据 |
"""

AUDIT_REPORT_TEMPLATE = """\
# Audit Report — {goal}

## Integrity Checklist
{integrity}

## Claim Ledger (summary)
{ledger}

## Required revisions (P0)
{p0_items}

## Recommended revisions (P1/P2)
{p1p2_items}
"""


def stage_audit(state_path: str, output_dir: str = "", **_kw) -> Dict[str, Any]:
    state = _load(state_path)
    state["stage"] = "audit"
    if not output_dir:
        output_dir = state.get("workspace", ".")

    # Normalize the audit output directory to an absolute path so that the
    # three artifact paths are consistent across runtimes (MSYS2/Windows
    # vs native) and land exactly where the agent expects them.
    workspace = Path(output_dir).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    # Integrity checklist (P0: check for missing/empty evidence)
    integrity_lines = []
    for st in state.get("subtasks", []):
        sid = st["subtask_id"]
        status = st.get("status")
        output = st.get("output", "")
        if status == "error":
            integrity_lines.append(f"- [❌] Subtask #{sid}: execution error")
        elif status in ("pending",):
            integrity_lines.append(f"- [⚠️] Subtask #{sid}: not yet executed")
        elif not output.strip():
            integrity_lines.append(f"- [⚠️] Subtask #{sid}: no output recorded")
        else:
            integrity_lines.append(f"- [✅] Subtask #{sid}: output recorded")

    # Claim ledger skeleton
    ledger_lines = [
        "| # | 声明 | 证据来源 | 支撑强度 | 缺口 |",
        "|---|---|---|---|---|",
        "| (LLM: fill in from aggregated outputs) | | | | |",
    ]

    audit_report = AUDIT_REPORT_TEMPLATE.format(
        goal=state.get("goal", ""),
        integrity="\n".join(integrity_lines),
        ledger="\n".join(ledger_lines),
        p0_items="(to be determined by executor + reviewer)",
        p1p2_items="(to be determined by executor + reviewer)",
    )

    # Write artifacts
    integrity_path = str(workspace / "integrity_checklist.md")
    ledger_path = str(workspace / "claim_ledger.md")
    report_path = str(workspace / "claim_audit_report.md")

    Path(integrity_path).write_text("\n".join(integrity_lines) + "\n", encoding="utf-8")
    Path(ledger_path).write_text("\n".join(ledger_lines) + "\n", encoding="utf-8")
    Path(report_path).write_text(audit_report, encoding="utf-8")

    state["audit"] = {
        "integrity_checklist": integrity_path,
        "claim_ledger": ledger_path,
        "claim_audit_report": report_path,
    }
    _touch(state)
    _atomic_write(state_path, state)

    print(json.dumps({
        "ok": True,
        "stage": "audit",
        "message": "Audit skeletons generated. LLM + reviewer should fill ledger and run 3-stage audit.",
        "artifacts": {
            "integrity_checklist": integrity_path,
            "claim_ledger": ledger_path,
            "claim_audit_report": report_path,
        },
    }, indent=2, ensure_ascii=False))
    return state


# --------------------------------------------------------------------------- #
# STAGE 6: SETTLE
# --------------------------------------------------------------------------- #
def stage_settle(state_path: str, final_output: str = "",
                 **_kw) -> Dict[str, Any]:
    state = _load(state_path)
    if state["stage"] not in ("review", "audit"):
        print(json.dumps({
            "ok": False,
            "error": f"Must be in review/audit stage, got '{state['stage']}'. "
                     "Run 'review' then 'audit' before 'settle'.",
        }, indent=2))
        return state
    if not final_output.strip():
        print(json.dumps({
            "ok": False,
            "error": "--final-output is empty. Pass the markdown content of the final deliverable.",
        }, indent=2))
        return state
    state["stage"] = "settled"

    if final_output:
        # Write final deliverable
        ws = Path(state.get("workspace", "."))
        ws.mkdir(parents=True, exist_ok=True)
        final_path = str(ws / "final_output.md")
        Path(final_path).write_text(final_output, encoding="utf-8")
    else:
        final_path = None

    # Compile summary
    counts = {s: sum(1 for st in state["subtasks"] if st["status"] == s)
              for s in SUBTASK_STATUS}

    _touch(state)
    _atomic_write(state_path, state)
    print(json.dumps({
        "ok": True,
        "stage": "settled",
        "message": "Pipeline complete. All artifacts written.",
        "summary": {
            "goal": state["goal"],
            "started_at": state["started_at"],
            "settled_at": state["updated_at"],
            "subtask_counts": counts,
            "final_output": final_path,
            "audit_artifacts": state.get("audit", {}),
        },
    }, indent=2, ensure_ascii=False))
    return state


# --------------------------------------------------------------------------- #
# STATUS
# --------------------------------------------------------------------------- #
def stage_status(state_path: str, **_kw) -> Dict[str, Any]:
    state = _load(state_path)
    counts = {s: sum(1 for st in state["subtasks"] if st["status"] == s)
              for s in SUBTASK_STATUS}
    pending = [st["subtask_id"] for st in state["subtasks"] if st["status"] == "pending"]
    done = [st["subtask_id"] for st in state["subtasks"] if st["status"] == "done"]
    print(json.dumps({
        "ok": True,
        "stage": state.get("stage"),
        "goal": state.get("goal"),
        "subtask_counts": counts,
        "pending": pending,
        "done": done,
        "execution_log_entries": len(state.get("execution_log", [])),
    }, indent=2, ensure_ascii=False))
    return state


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="unclekk-harness 6-stage pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    # ingest
    pi = sub.add_parser("ingest", help="Stage 1: create roadmap skeleton")
    pi.add_argument("--goal", required=True)
    pi.add_argument("--workspace", default=".")
    pi.add_argument("--out", default="harness_state.json")

    # plan
    pp = sub.add_parser("plan", help="Stage 2: validate DAG + output plan")
    pp.add_argument("--state", default="harness_state.json")

    # exec
    pe = sub.add_parser("exec", help="Stage 3: get next tasks")
    pe.add_argument("--state", default="harness_state.json")
    pe.add_argument("--recover", action="store_true",
                    help="On corrupt/truncated state, recover from execution_log "
                         "and resume the exec stage instead of failing hard.")

    # complete
    pc = sub.add_parser("complete", help="Mark a task done (host agent calls this)")
    pc.add_argument("--state", default="harness_state.json")
    pc.add_argument("--id", type=int, required=True)
    pc.add_argument("--output", default="")

    # error
    pa = sub.add_parser("error", help="Mark a task error")
    pa.add_argument("--state", default="harness_state.json")
    pa.add_argument("--id", type=int, required=True)
    pa.add_argument("--msg", default="")

    # review
    pr = sub.add_parser("review", help="Stage 4: aggregate outputs")
    pr.add_argument("--state", default="harness_state.json")

    # audit
    pdr = sub.add_parser("audit", help="Stage 5: generate audit skeletons")
    pdr.add_argument("--state", default="harness_state.json")
    pdr.add_argument("--output-dir", default="")

    # settle
    ps = sub.add_parser("settle", help="Stage 6: write final + summary")
    ps.add_argument("--state", default="harness_state.json")
    ps.add_argument("--final-output", default="")

    # status
    pst = sub.add_parser("status", help="Show current state")
    pst.add_argument("--state", default="harness_state.json")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cmd = args.cmd

    try:
        if cmd == "ingest":
            stage_ingest(args.goal, args.workspace, args.out)
        elif cmd == "plan":
            stage_plan(args.state)
        elif cmd == "exec":
            stage_exec(args.state, recover=args.recover)
        elif cmd == "complete":
            stage_complete(args.state, args.id, args.output)
        elif cmd == "error":
            stage_error(args.state, args.id, args.msg)
        elif cmd == "review":
            stage_review(args.state)
        elif cmd == "audit":
            stage_audit(args.state, args.output_dir)
        elif cmd == "settle":
            stage_settle(args.state, args.final_output)
        elif cmd == "status":
            stage_status(args.state)
    except FileNotFoundError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"JSON parse error: {e}"}))
        return 1
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Unexpected error: {e}"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
