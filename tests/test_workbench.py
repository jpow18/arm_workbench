import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from arm_workbench.adapters import (HardwareCamera, HardwareScanner, HardwareUnavailable,
                                    LeRobotSO101Arm, MockArm, MockCamera, MockScanner)
from arm_workbench.ports import Pose
from arm_workbench.runtime import AgentTools, Context, Workbench
from arm_workbench.safety import Limits, Motion, SafetyError, timed
from arm_workbench.tasks.photo_scan import validate_simulated_scan


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workbench = Workbench(self.root)
        self.tools = AgentTools(self.workbench)

    def finish(self, workbench=None):
        wb = workbench or self.workbench
        wb.start("photo_scan")
        for _ in range(20):
            if wb.terminal:
                return wb.status()
            gate = wb.status()["pending_confirmation"]
            wb.confirm(gate) if gate else wb.advance()
        self.fail("Task did not terminate")

    def test_complete_scan_artifacts(self):
        status = self.finish()
        self.assertEqual(status["state"], "completed")
        output = Path(status["output"])
        self.assertEqual({p.name for p in output.iterdir()},
                         {"manifest.json", "scene.ppm", "scan.ppm", "scan.sha256"})
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(manifest["state"], "completed")
        self.assertTrue(manifest["simulated"])
        self.assertEqual(len(self.workbench.context.motion.arm.moves), 2)

    def test_gate_blocks_advancement(self):
        before = self.workbench.start("photo_scan")
        self.assertEqual(self.workbench.advance(), before)
        self.assertEqual(self.workbench.context.motion.arm.moves, [])

    def test_cannot_confirm_wrong_gate(self):
        self.workbench.start("photo_scan")
        with self.assertRaises(ValueError):
            self.workbench.confirm("photo_loaded")
        self.assertEqual(self.workbench.status()["pending_confirmation"], "scene_ready")

    def test_confirmation_cannot_replay(self):
        self.workbench.start("photo_scan")
        self.workbench.confirm("scene_ready")
        with self.assertRaises(ValueError):
            self.workbench.confirm("scene_ready")

    def test_agent_cannot_approve_or_send_motor_commands(self):
        for name in ("confirm", "send_action", "move_named", "exec", "reset"):
            with self.assertRaises(ValueError):
                self.tools.call(name)
        with self.assertRaises(ValueError):
            self.tools.call("advance_task", {"approve": True})

    def test_tool_arguments_strict(self):
        for args in ({}, {"task": 1}, {"task": "photo_scan", "output": "/tmp/other"}):
            with self.assertRaises(ValueError):
                self.tools.call("start_task", args)
        for args in ([], "", False):
            with self.assertRaises(ValueError):
                self.tools.call("list_tasks", args)

    def test_unknown_task_writes_nothing(self):
        with self.assertRaises(ValueError):
            self.workbench.start("../../bad")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_stop_latches(self):
        self.workbench.start("photo_scan")
        self.workbench.stop()
        self.assertTrue(self.workbench.context.motion.arm.stopped)
        self.assertTrue(self.workbench.context.scanner.stopped)
        with self.assertRaises(ValueError):
            self.workbench.advance()
        with self.assertRaises(ValueError):
            self.workbench.start("photo_scan")
        self.assertEqual(self.workbench.stop()["state"], "stopped")

    def test_stop_before_start_latches(self):
        self.workbench.stop()
        with self.assertRaises(ValueError):
            self.workbench.start("photo_scan")

    def test_no_rerun_in_completed_session(self):
        self.finish()
        with self.assertRaises(ValueError):
            self.workbench.start("photo_scan")

    def test_runs_are_unique(self):
        first = self.finish()["output"]
        second = self.finish(Workbench(self.root))["output"]
        self.assertNotEqual(first, second)
        self.assertTrue(Path(first).exists())

    def test_timeout_stops_on_next_transition(self):
        now = [0.0]
        wb = Workbench(self.root, clock=lambda: now[0], max_run_s=10)
        wb.start("photo_scan")
        now[0] = 11.0
        self.assertEqual(wb.advance()["state"], "failed")
        self.assertTrue(wb.context.motion.arm.stopped)

    def test_expired_confirmation_fails(self):
        now = [0.0]
        wb = Workbench(self.root, clock=lambda: now[0], max_run_s=10)
        wb.start("photo_scan")
        now[0] = 11.0
        self.assertEqual(wb.confirm("scene_ready")["state"], "failed")

    def test_device_fault_stops_both_devices(self):
        self.workbench.start("photo_scan")
        self.workbench.confirm("scene_ready")
        def fail(*args, **kwargs):
            raise OSError("camera offline")
        self.workbench.context.camera.capture = fail
        self.assertEqual(self.workbench.advance()["state"], "failed")
        self.assertTrue(self.workbench.context.motion.arm.stopped)
        self.assertTrue(self.workbench.context.scanner.stopped)
        manifest = json.loads((self.workbench.context.output / "manifest.json").read_text())
        self.assertIn("camera offline", manifest["events"][-1]["error"])

    def test_stop_failure_does_not_skip_scanner(self):
        self.workbench.start("photo_scan")
        def fail():
            raise OSError("stop transport failed")
        self.workbench.context.motion.arm.stop = fail
        self.workbench.stop()
        self.assertTrue(self.workbench.context.scanner.stopped)
        self.assertIn("stop transport failed", self.workbench.events[-1]["stop_errors"][0])

    def test_hardware_stubs_fail_closed(self):
        for adapter in (LeRobotSO101Arm, HardwareCamera, HardwareScanner):
            with self.assertRaises(HardwareUnavailable):
                adapter()

    def test_runtime_rejects_nonsimulated_device(self):
        arm = MockArm()
        arm.simulated = False
        context = Context(Motion(arm, {}), MockCamera(), MockScanner(), self.root)
        with self.assertRaises(HardwareUnavailable):
            Workbench(self.root, context=context).start("photo_scan")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_extension_registration(self):
        class Noop:
            state = "ready"
            pending_confirmation = None
            done = False
            def step(self, context):
                self.state, self.done = "completed", True
            def confirm(self, gate):
                raise ValueError("No gate")
        self.workbench.register("noop", Noop)
        self.assertEqual(self.tools.call("list_tasks")["tasks"], ["noop", "photo_scan"])
        self.workbench.start("noop")
        self.assertEqual(self.workbench.advance()["state"], "completed")

    def test_invalid_registration(self):
        for name in ("photo_scan", "../bad", "", "Bad Name"):
            with self.assertRaises(ValueError):
                self.workbench.register(name, lambda: None)

    def test_cli_simulation(self):
        result = subprocess.run([sys.executable, "-m", "arm_workbench", "run",
                                 "--auto-confirm-simulation", "--output", str(self.root)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1])["state"], "completed")

    def test_cli_json_lines_no_approval_and_eof_stops(self):
        result = subprocess.run([sys.executable, "-m", "arm_workbench", "tools", "--output", str(self.root)],
                                input='{"tool":"start_task","arguments":{"task":"photo_scan"}}\n'
                                      '{"tool":"confirm","arguments":{"gate":"scene_ready"}}\n',
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertIn("error", lines[1])
        manifest = next(self.root.glob("*/manifest.json"))
        self.assertEqual(json.loads(manifest.read_text())["state"], "stopped")

    def test_bad_scan_fails_verification(self):
        wb = self.workbench
        wb.start("photo_scan")
        wb.confirm("scene_ready")
        wb.advance()
        wb.advance()
        wb.confirm("photo_loaded")
        wb.advance()
        (wb.context.output / "scan.ppm").write_bytes(b"broken")
        self.assertEqual(wb.advance()["state"], "failed")


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.pose = Pose((0,) * 6, (0.2, 0, 0.2))

    def test_valid_limits(self):
        Limits().validate(self.pose, 10, 10)

    def test_joint_and_workspace_limits(self):
        for pose in (Pose((100,) * 6, (0.2, 0, 0.2)), Pose((0,) * 6, (1, 0, 0.2)),
                     Pose((0,) * 5, (0.2, 0, 0.2)), Pose((0,) * 6, (0.2, 0))):
            with self.assertRaises(SafetyError):
                Limits().validate(pose, 10, 10)

    def test_speed_timeout_finite_and_bounded(self):
        for value in (0, -1, math.inf, math.nan, 100):
            with self.assertRaises(SafetyError):
                Limits().validate(self.pose, value, 10)
            with self.assertRaises(SafetyError):
                Limits().validate(self.pose, 10, value)

    def test_nonfinite_pose_rejected(self):
        for value in (math.inf, math.nan):
            with self.assertRaises(SafetyError):
                Limits().validate(Pose((value,) * 6, (0.2, 0, 0.2)), 10, 10)

    def test_invalid_limits_rejected(self):
        for limits in (Limits(joint_ranges=()), Limits(max_speed_deg_s=math.nan),
                       Limits(workspace=((1, 0),) * 3)):
            with self.assertRaises(SafetyError):
                limits.validate(self.pose, 10, 10)

    def test_named_motion_guard_and_stop(self):
        arm = MockArm()
        motion = Motion(arm, {"home": self.pose})
        with self.assertRaises(SafetyError):
            motion.move_named("unknown")
        motion.stop()
        with self.assertRaises(SafetyError):
            motion.move_named("home")
        self.assertEqual(arm.moves, [])

    def test_mock_scan_rejects_corruption(self):
        header = b"P6\n# SIMULATION scan\n2 2\n255\n"
        validate_simulated_scan(header + bytes(12))
        for data in (b"P6\n" + b"x" * 21, header + bytes(11), header + bytes(13),
                     header.replace(b"2 2", b"-2 2") + bytes(12),
                     header.replace(b"255", b"65535") + bytes(12),
                     header.replace(b"2 2", b"2 2 2") + bytes(12),
                     header.replace(b"2 2", b"a b") + bytes(12)):
            with self.assertRaises(ValueError):
                validate_simulated_scan(data)

    def test_operation_timeout_must_be_finite_positive(self):
        calls = []
        for value in (math.nan, math.inf, 0, -1):
            with self.assertRaises(ValueError):
                timed(lambda: calls.append(True), value)
        self.assertEqual(calls, [])

    def test_operation_overrun_detected(self):
        times = iter([0, 11])
        with self.assertRaises(TimeoutError):
            timed(lambda: None, 10, clock=lambda: next(times))


if __name__ == "__main__":
    unittest.main()
