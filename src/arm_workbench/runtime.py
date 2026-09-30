"""Trusted task runtime; exposes a deliberately small agent-facing dispatcher."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Callable, Protocol
from uuid import uuid4

from .adapters import MockArm, MockCamera, MockScanner, HardwareUnavailable
from .ports import Camera, Scanner, Pose
from .safety import Motion, timed


@dataclass
class Context:
    motion: Motion
    camera: Camera
    scanner: Scanner
    output: Path

    def operation(self, action: Callable[[], None], timeout_s: float = 10.0) -> None:
        timed(action, timeout_s)

    def stop(self) -> list[str]:
        errors = []
        # A failed arm stop must not prevent a scanner stop attempt.
        for name, stop in (("arm", self.motion.stop), ("scanner", self.scanner.stop)):
            try:
                stop()
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
        return errors


class Task(Protocol):
    state: str
    pending_confirmation: str | None
    done: bool

    def step(self, context: Context) -> None: ...
    def confirm(self, gate: str) -> None: ...


class Workbench:
    """One task per session. Restart explicitly after completion, failure or stop."""
    def __init__(self, output_root: Path, *, context: Context | None = None,
                 clock: Callable[[], float] = monotonic, max_run_s: float = 300.0):
        from .tasks.photo_scan import PhotoScanTask
        if not 0 < max_run_s <= 3600:
            raise ValueError("max_run_s must be in (0, 3600]")
        self.output_root = Path(output_root)
        self.clock, self.max_run_s = clock, max_run_s
        self.registry: dict[str, Callable[[], Task]] = {"photo_scan": PhotoScanTask}
        self.context = context
        self.task: Task | None = None
        self.run_id: str | None = None
        self.task_name: str | None = None
        self.events: list[dict] = []
        self.terminal: str | None = None
        self.started = 0.0
        self._confirmed: set[str] = set()

    def register(self, name: str, factory: Callable[[], Task]) -> None:
        if self.task is not None:
            raise ValueError("Register tasks before starting")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name) or name in self.registry:
            raise ValueError("Invalid or duplicate task name")
        self.registry[name] = factory

    def start(self, name: str) -> dict:
        if self.task is not None or self.terminal is not None:
            raise ValueError("Session already used; create a new supervised session")
        if name not in self.registry:
            raise ValueError("Unknown task")
        if self.context is not None and not all(
            getattr(device, "simulated", False) is True
            for device in (self.context.motion.arm, self.context.camera, self.context.scanner)
        ):
            raise HardwareUnavailable("This release only allows simulated devices")
        task = self.registry[name]()
        run_id = uuid4().hex
        output = self.output_root / run_id
        output.mkdir(parents=True, exist_ok=False)
        if self.context is None:
            poses = {
                "home": Pose((0, 0, 0, 0, 0, 0), (0.15, 0.0, 0.3)),
                "scan_staging": Pose((10, 10, 0, 0, 0, 0), (0.2, 0.0, 0.2)),
            }
            self.context = Context(Motion(MockArm(), poses), MockCamera(), MockScanner(), output)
        else:
            self.context.output = output
        self.task, self.run_id, self.task_name = task, run_id, name
        self.started = self.clock()
        try:
            self._record("started")
        except Exception:
            self.terminal = "failed"
            self.context.stop()
            raise
        return self.status()

    def status(self) -> dict:
        return {
            "run_id": self.run_id, "task": self.task_name, "simulated": True,
            "state": self.terminal or (self.task.state if self.task else "idle"),
            "pending_confirmation": (self.task.pending_confirmation
                                     if self.task and not self.terminal else None),
            "output": str(self.context.output) if self.run_id and self.context else None,
        }

    def _record(self, event: str, **detail) -> None:
        self.events.append({"event": event, "elapsed_s": self.clock() - self.started,
                            **self.status(), **detail})
        assert self.context
        path = self.context.output / "manifest.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"schema_version": 1, **self.status(),
                                         "events": self.events}, indent=2) + "\n")
        temporary.replace(path)

    def _check_deadline(self) -> None:
        if self.clock() - self.started > self.max_run_s:
            raise TimeoutError("Run expired, including operator confirmation wait")

    def confirm(self, gate: str) -> dict:
        """Trusted operator entry point. Never register this as an agent tool."""
        if not self.task or self.terminal:
            raise ValueError("No active task")
        if gate != self.task.pending_confirmation or gate in self._confirmed:
            raise ValueError("Confirmation does not match the current, unused gate")
        try:
            self._check_deadline()
            self.task.confirm(gate)
            self._confirmed.add(gate)
            self._record("operator_confirmed", gate=gate)
        except Exception as exc:
            self._fail(exc)
        return self.status()

    def advance(self) -> dict:
        if not self.task or self.terminal:
            raise ValueError("No active task")
        try:
            self._check_deadline()
            if self.task.pending_confirmation:
                return self.status()
            assert self.context
            self.task.step(self.context)
            self._check_deadline()
            if self.task.done:
                self.terminal = "completed"
            self._record("advanced")
        except Exception as exc:
            self._fail(exc)
        return self.status()

    def _fail(self, exc: Exception) -> None:
        self.terminal = "failed"
        errors = self.context.stop() if self.context else []
        self._record("failed", error=f"{type(exc).__name__}: {exc}", stop_errors=errors)

    def stop(self) -> dict:
        if not self.task:
            self.terminal = "stopped"
            return self.status()
        if self.terminal:
            return self.status()
        self.terminal = "stopped"
        assert self.context
        errors = self.context.stop()
        self._record("stopped", stop_errors=errors)
        return self.status()


TOOLS = {
    "list_tasks": {"description": "List installed, trusted tasks", "arguments": {}},
    "start_task": {"description": "Start one named task in simulation", "arguments": {"task": "string"}},
    "task_status": {"description": "Read current state and operator gate", "arguments": {}},
    "advance_task": {"description": "Perform one allowed transition; never approves a gate", "arguments": {}},
    "stop_task": {"description": "Latch a stop for the session", "arguments": {}},
}


class AgentTools:
    """Transport-neutral allowlist. No eval, shell, motor values or file paths."""
    def __init__(self, workbench: Workbench):
        self._workbench = workbench

    def call(self, name: str, arguments: dict | None = None) -> dict:
        args = {} if arguments is None else arguments
        if name not in TOOLS or not isinstance(args, dict):
            raise ValueError("Unknown tool or invalid arguments")
        if set(args) != set(TOOLS[name]["arguments"]):
            raise ValueError("Unexpected or missing arguments")
        if name == "start_task":
            if not isinstance(args["task"], str):
                raise ValueError("task must be a string")
            return self._workbench.start(args["task"])
        if name == "list_tasks":
            return {"tasks": sorted(self._workbench.registry)}
        return {"task_status": self._workbench.status,
                "advance_task": self._workbench.advance,
                "stop_task": self._workbench.stop}[name]()
