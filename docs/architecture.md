# Architecture and extending tasks

## Layers

1. **AgentTools**: named, schema-checked calls; no motor values or operator approval
2. **Workbench**: registry, session lifecycle, deadline checks, journal and stop handling
3. **Task**: explicit state machine; asks for operator gates and uses trusted capabilities
4. **Context / Motion**: device operations, named-pose guard and stop fan-out
5. **Arm / Camera / Scanner**: replaceable device contracts; mock implementations today

The interfaces are intentionally small. Task code is trusted Python, not arbitrary
AI-generated code loaded during a run. Registry changes are only permitted before
starting. All device operations and approval changes run serially; the runtime is
not thread-safe. There is no resumable physical execution: the manifest is an audit
artifact, not authority to replay commands following a crash.

## Add a task

Implement `state`, `pending_confirmation`, `done`, `step(context)` and
`confirm(gate)`. Register a factory before starting:

```python
from pathlib import Path
from arm_workbench.runtime import AgentTools, Workbench

class InspectionTask:
    state = "capture"
    pending_confirmation = None
    done = False

    def step(self, context):
        context.operation(lambda: context.camera.capture(
            context.output / "inspection.ppm", timeout_s=10))
        self.state, self.done = "completed", True

    def confirm(self, gate):
        raise ValueError("No confirmation is pending")

workbench = Workbench(Path("runs"))
workbench.register("inspection", InspectionTask)
tools = AgentTools(workbench)
tools.call("start_task", {"task": "inspection"})
tools.call("advance_task")
```

Give every task its own tests for success, device faults, stop, timeout and invalid
confirmation. New tasks that move an arm should use approved named trajectories
and explicit operator gates. A plugin is not permitted to weaken hardware controls
just because it implements this protocol. Registration has no package discovery,
network downloads or automatic code execution beyond the trusted factory.

## Approval design

`Workbench.confirm()` belongs to a trusted operator host, never the agent tool set.
The demo CLI collects approval from stdin. Production integration needs a separate,
authenticated human channel binding run ID, gate, scene and expiry; this release
has no web server/authentication and must not be deployed as a public robot API.

## Timeout and motion limitations

- Session deadlines are checked when advancing/confirming, not by a background thread
- The operation timer only detects an overrun after the adapter returns
- A hung device call cannot be interrupted by this runtime
- Named poses contain declarative XYZ metadata; it is not derived from joint angles
- Bounds check endpoints only; they do not validate paths, collisions or swept volumes
- Speed is an adapter contract, not measured physical velocity
- Mock motion is instantaneous; it is not a physics simulator

These checks are useful regression guards. Hardware needs validated kinematics,
collision-aware trajectories, actual feedback, independent watchdogs and interlocks.
No tolerance, speed or joint range here is a calibrated SO-101 setting.

## Agent transport

The JSON-lines CLI processes one request at a time and emits a `result` or `error`
object per line. Invalid tool names and extra arguments are rejected. EOF stops an
active session. A caller that blocks waiting for input does not run a watchdog.
For remote agents, build a separately authenticated transport; do not expose stdin
or Python objects as a purported security boundary. No model credentials or paid
model dependencies are needed to develop this application layer.
