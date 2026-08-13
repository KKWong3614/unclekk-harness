#!/usr/bin/env python3
"""Tests for unclekk-harness / scripts/harness.py"""

import json
import os
import tempfile
import unittest
from pathlib import Path

# Import from sibling
SCRIPTS = Path(__file__).parent
HARNESS = SCRIPTS / "harness.py"

# Dynamic import
import importlib.util
spec = importlib.util.spec_from_file_location("harness", HARNESS)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class TestIngest(unittest.TestCase):
    def test_creates_state(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out = f.name
        state = harness.stage_ingest(
            goal="write report",
            workspace=tempfile.mkdtemp(),
            out=out,
        )
        self.assertEqual(state["stage"], "ingest")
        self.assertEqual(state["goal"], "write report")
        self.assertIn("subtasks", state)
        self.assertTrue(len(state["subtasks"]) >= 1)
        os.unlink(out)


class TestPlan(unittest.TestCase):
    def _make_state(self, subtasks):
        return {
            "schema": harness.SCHEMA_VERSION,
            "based_on": "",
            "goal": "test",
            "workspace": tempfile.mkdtemp(),
            "stage": "ingest",
            "started_at": "",
            "updated_at": None,
            "mode": "complex",
            "context": {},
            "worker_pool": {},
            "subtasks": subtasks,
            "execution_log": [],
            "aggregated_outputs": {},
            "audit": {},
            "checkpoint_ok": False,
        }

    def test_validate_pass(self):
        state = self._make_state([
            {"subtask_id": 1, "subtask_description": "do A", "success_criteria": "A done",
             "depends_on": [], "status": "pending", "output": ""},
        ])
        self.assertEqual(harness.validate_state(state), [])

    def test_validate_missing_description(self):
        state = self._make_state([
            {"subtask_id": 1, "subtask_description": "", "success_criteria": "A done",
             "depends_on": [], "status": "pending", "output": ""},
        ])
        self.assertTrue(len(harness.validate_state(state)) > 0)

    def test_validate_duplicate_ids(self):
        state = self._make_state([
            {"subtask_id": 1, "subtask_description": "A", "success_criteria": "ok",
             "depends_on": [], "status": "pending", "output": ""},
            {"subtask_id": 1, "subtask_description": "B", "success_criteria": "ok",
             "depends_on": [], "status": "pending", "output": ""},
        ])
        errors = harness.validate_state(state)
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_validate_cycle(self):
        state = self._make_state([
            {"subtask_id": 1, "subtask_description": "A", "success_criteria": "ok",
             "depends_on": [2], "status": "pending", "output": ""},
            {"subtask_id": 2, "subtask_description": "B", "success_criteria": "ok",
             "depends_on": [1], "status": "pending", "output": ""},
        ])
        errors = harness.validate_state(state)
        self.assertTrue(any("cycle" in e for e in errors))

    def test_validate_unknown_dep(self):
        state = self._make_state([
            {"subtask_id": 1, "subtask_description": "A", "success_criteria": "ok",
             "depends_on": [99], "status": "pending", "output": ""},
        ])
        errors = harness.validate_state(state)
        self.assertTrue(any("unknown" in e for e in errors))

    def test_validate_placeholder_rejected(self):
        """Plan must reject ingest skeleton's placeholder descriptions."""
        state = self._make_state([
            {"subtask_id": 1, "subtask_description": "[LLM: replace with first concrete step]",
             "success_criteria": "step completed and output recorded",
             "depends_on": [], "status": "pending", "output": ""},
        ])
        errors = harness.validate_state(state)
        self.assertTrue(any("placeholder" in e for e in errors))

    def test_validate_placeholder_replaced_passes(self):
        """Real description (no [LLM: prefix) passes validate."""
        state = self._make_state([
            {"subtask_id": 1, "subtask_description": "Gather competitor pricing data",
             "success_criteria": "table of prices collected",
             "depends_on": [], "status": "pending", "output": ""},
        ])
        self.assertEqual(harness.validate_state(state), [])

    def test_topo_order(self):
        state = self._make_state([
            {"subtask_id": 1, "subtask_description": "A", "success_criteria": "ok",
             "depends_on": [], "status": "pending", "output": ""},
            {"subtask_id": 2, "subtask_description": "B", "success_criteria": "ok",
             "depends_on": [1], "status": "pending", "output": ""},
            {"subtask_id": 3, "subtask_description": "C", "success_criteria": "ok",
             "depends_on": [1], "status": "pending", "output": ""},
        ])
        order = harness.topo_order(state)
        self.assertEqual(order.index(1), 0)  # 1 must come first
        self.assertIn(2, order)
        self.assertIn(3, order)


class TestCondition(unittest.TestCase):
    def test_none_condition(self):
        self.assertIsNone(harness.eval_condition(None, {}, {}))

    def test_empty_condition(self):
        self.assertIsNone(harness.eval_condition("", {}, {}))

    def test_true_condition(self):
        outputs = {"5": "some data here"}
        self.assertTrue(
            harness.eval_condition('len(outputs.get("5", "")) > 5', outputs, {})
        )

    def test_false_condition(self):
        outputs = {"5": "x"}
        self.assertFalse(
            harness.eval_condition('len(outputs.get("5", "")) > 5', outputs, {})
        )

    def test_invalid_condition(self):
        self.assertFalse(harness.eval_condition("import os", {}, {}))


class TestNextSteps(unittest.TestCase):
    def _state(self, subtasks):
        return {
            "schema": "1.0", "goal": "", "context": {}, "subtasks": subtasks,
        }

    def test_ready_no_deps(self):
        state = self._state([
            {"subtask_id": 1, "status": "pending", "depends_on": [],
             "condition": None, "subtask_description": "A",
             "success_criteria": "ok", "output": ""},
        ])
        ready = harness.next_steps(state)
        self.assertTrue(len(ready) > 0)
        self.assertEqual(ready[0]["subtask_id"], 1)

    def test_deps_not_done(self):
        state = self._state([
            {"subtask_id": 1, "status": "pending", "depends_on": [],
             "condition": None, "subtask_description": "A",
             "success_criteria": "ok", "output": ""},
            {"subtask_id": 2, "status": "pending", "depends_on": [1],
             "condition": None, "subtask_description": "B",
             "success_criteria": "ok", "output": ""},
        ])
        ready = harness.next_steps(state)
        self.assertTrue(len(ready) > 0)
        self.assertEqual(ready[0]["subtask_id"], 1)

    def test_deps_done(self):
        state = self._state([
            {"subtask_id": 1, "status": "done", "depends_on": [],
             "condition": None, "subtask_description": "A",
             "success_criteria": "ok", "output": "result"},
            {"subtask_id": 2, "status": "pending", "depends_on": [1],
             "condition": None, "subtask_description": "B",
             "success_criteria": "ok", "output": ""},
        ])
        ready = harness.next_steps(state)
        self.assertTrue(len(ready) > 0)
        self.assertEqual(ready[0]["subtask_id"], 2)

    def test_condition_false_skips(self):
        state = self._state([
            {"subtask_id": 1, "status": "pending", "depends_on": [],
             "condition": 'len(outputs.get("5", "")) > 5',
             "subtask_description": "A", "success_criteria": "ok", "output": ""},
        ])
        # outputs empty → condition false → skipped
        ready = harness.next_steps(state)
        self.assertEqual(ready, [])
        self.assertEqual(state["subtasks"][0]["status"], "skipped")


class TestAtomicWrite(unittest.TestCase):
    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.json")
            harness._atomic_write(path, {"a": 1, "b": "hello"})
            data = json.loads(Path(path).read_text())
            self.assertEqual(data, {"a": 1, "b": "hello"})


def _st(sid, desc="task", criteria="ok", deps=None, status="pending",
        output="", cond=None, group=None, tools=None):
    return {
        "subtask_id": sid,
        "subtask_description": desc,
        "exact_input": "",
        "expected_output": "out",
        "success_criteria": criteria,
        "desired_auxiliary_tools": tools or [],
        "depends_on": deps or [],
        "parallel_group": group,
        "condition": cond,
        "assigned_worker": None,
        "status": status,
        "output": output,
    }


def _full_state(subtasks):
    return {
        "schema": harness.SCHEMA_VERSION,
        "based_on": "",
        "goal": "dag test",
        "workspace": tempfile.mkdtemp(),
        "stage": "plan",
        "started_at": "",
        "updated_at": None,
        "mode": "complex",
        "context": {},
        "worker_pool": {},
        "subtasks": subtasks,
        "execution_log": [],
        "aggregated_outputs": {},
        "audit": {"integrity_checklist": None,
                  "claim_ledger": None,
                  "claim_audit_report": None},
        "checkpoint_ok": False,
    }


class TestMultiDAG(unittest.TestCase):
    """Real multi-subtask DAG: coverage gaps the original 17 tests left open."""

    def test_dag_a_to_b_c_topology(self):
        state = _full_state([
            _st(1, "A"),
            _st(2, "B", deps=[1]),
            _st(3, "C", deps=[1]),
        ])
        order = harness.topo_order(state)
        self.assertEqual(order.index(1), 0)
        self.assertTrue(order.index(2) > order.index(1))
        self.assertTrue(order.index(3) > order.index(1))

    def test_parallel_group_returned_together(self):
        state = _full_state([
            _st(1, "X", group="collect"),
            _st(2, "Y", group="collect"),
        ])
        ready = harness.next_steps(state)
        # next_steps groups members sharing parallel_group into one dict
        groups = [r for r in ready if "subtasks" in r]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["parallel_group"], "collect")
        self.assertEqual(len(groups[0]["subtasks"]), 2)

    def test_downstream_runs_after_skipped_dep(self):
        """A skipped condition-tasks should still satisfy downstream deps."""
        state = _full_state([
            _st(1, "A", cond='len(outputs.get("1","")) > 5'),
            _st(2, "B", deps=[1]),
        ])
        # condition false -> task 1 skipped; task 2 deps (done/skipped) satisfied
        ready = harness.next_steps(state)
        self.assertEqual(state["subtasks"][0]["status"], "skipped")
        ids = {r["id"] if "id" in r else r["subtask_id"] for r in ready}
        self.assertIn(2, ids)

    def test_validate_unknown_dep_after_skip(self):
        state = _full_state([_st(1, "A", deps=[99])])
        errors = harness.validate_state(state)
        self.assertTrue(any("unknown" in e for e in errors))


class TestStateRecovery(unittest.TestCase):
    def test_recover_from_execution_log(self):
        state = {
            "goal": "restore me",
            "workspace": "/tmp/ws",
            "stage": "exec",
            "execution_log": [
                {"subtask_id": 1, "status": "done", "output_preview": "result"},
                {"subtask_id": 2, "status": "error", "error": "boom"},
            ],
        }
        raw = json.dumps(state)
        rec = harness._recover_state_from_log("/tmp/bad.json", raw)
        self.assertEqual(rec["goal"], "restore me")
        self.assertEqual(rec["workspace"], "/tmp/ws")
        self.assertEqual(len(rec["subtasks"]), 2)
        done = [s for s in rec["subtasks"] if s["status"] == "done"]
        err = [s for s in rec["subtasks"] if s["status"] == "error"]
        self.assertEqual(len(done), 1)
        self.assertEqual(len(err), 1)

    def test_recover_empty_raises(self):
        with self.assertRaises(ValueError):
            harness._recover_state_from_log("/tmp/none.json", "{}")

    def test_recover_missing_subtasks_field(self):
        """State with valid JSON but no subtasks + surviving execution_log recovers."""
        state = {
            "goal": "partial",
            "workspace": "/tmp/ws",
            "stage": "exec",
            "execution_log": [
                {"subtask_id": 3, "status": "done", "output_preview": "ok"},
            ],
        }
        rec = harness._recover_state_from_log("/tmp/bad.json", json.dumps(state))
        self.assertEqual(len(rec["subtasks"]), 1)
        self.assertEqual(rec["subtasks"][0]["status"], "done")

    def test_cli_missing_state_returns_error(self):
        """CLI error-path: reading a nonexistent state.json returns ok:false."""
        r = harness.main(["exec", "--state", "/no/such/file.json"])
        self.assertEqual(r, 1)

    def test_exec_recover_cli_fails_on_unrecoverable(self):
        """exec --recover returns exit 1 when corruption has no recoverable log."""
        import os
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            # JSON that parses but lacks subtasks AND has no execution_log to recover from
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"goal":"lost","workspace":"/tmp/r"}\n')
            r = harness.main(["exec", "--state", path, "--recover"])
            self.assertEqual(r, 1)

    def test_exec_recover_cli_with_embedded_log(self):
        """--recover with JSON that partially contains a recoverable execution_log."""
        state = _full_state([_st(1, "A", status="done", output="ok")])
        state["stage"] = "exec"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            # Embed recoverable log inside a malformed dict so _recover can extract it
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"goal":"recovered","execution_log":[{"subtask_id":1,"status":"done"}]}')
            r = harness.main(["exec", "--state", path, "--recover"])
            self.assertEqual(r, 0)

    def test_exec_without_recover_raises_on_corrupt(self):
        """Without --recover, a corrupt state.json returns ok:false (exit 1)."""
        state = _full_state([_st(1, "A", status="done", output="ok")])
        state["stage"] = "exec"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{ broken")
            r = harness.main(["exec", "--state", path])
            self.assertEqual(r, 1)

    def test_audit_normalizes_output_dir_to_absolute(self):
        """stage_audit resolves output_dir so artifact paths are runtime-consistent."""
        state = _full_state([_st(1, "A", status="done", output="x")])
        state["stage"] = "review"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            harness._atomic_write(path, state)
            harness.stage_audit(path, output_dir=td)
            ledger = harness._load(path)["audit"]["claim_ledger"]
            self.assertTrue(
                ledger.startswith("/") or ledger.startswith("C:\\"),
                f"audit path not absolute: {ledger}",
            )


class TestConditionSafety(unittest.TestCase):
    def test_block_lambda(self):
        self.assertFalse(harness.eval_condition("lambda: 1", {}, {}))

    def test_block_generator_exp(self):
        self.assertFalse(harness.eval_condition("(x for x in [] if 1)", {}, {}))

    def test_block_attribute_chain(self):
        self.assertFalse(harness.eval_condition("outputs.__class__", {}, {}))

    def test_allow_len_get(self):
        self.assertTrue(
            harness.eval_condition('len(outputs.get("1","")) > 0',
                                   {"1": "hi"}, {})
        )


class TestStageGates(unittest.TestCase):
    """Verify that review/settle cannot be called out of stage order."""

    def test_review_rejected_before_exec(self):
        """review should be rejected while still in 'ingest' stage."""
        state = _full_state([])
        state["stage"] = "ingest"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            harness._atomic_write(path, state)
            r = harness.stage_review(path)
            self.assertEqual(r["stage"], "ingest")  # stage unchanged

    def test_settle_rejected_before_review(self):
        """settle should be rejected while in 'exec' stage."""
        state = _full_state([_st(1, "A", status="done", output="result")])
        state["stage"] = "exec"
        state["aggregated_outputs"] = {"1": "result"}
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            harness._atomic_write(path, state)
            r = harness.stage_settle(path, final_output="## Done")
            self.assertEqual(r["stage"], "exec")

    def test_settle_rejected_empty_final_output(self):
        """settle should reject an empty --final-output."""
        state = _full_state([])
        state["stage"] = "review"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            harness._atomic_write(path, state)
            r = harness.stage_settle(path, final_output="")
            self.assertEqual(r["stage"], "review")

    def test_settle_rejected_whitespace_final_output(self):
        """settle should reject whitespace-only final output."""
        state = _full_state([])
        state["stage"] = "audit"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            harness._atomic_write(path, state)
            r = harness.stage_settle(path, final_output="   ")
            self.assertEqual(r["stage"], "audit")


if __name__ == "__main__":
    unittest.main()
