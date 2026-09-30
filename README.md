# arm-workbench

A small, modular platform for AI-assisted robot-arm tasks. Start with a supervised
photo-scanning workflow; add more tasks without coupling their logic to a specific
arm, camera, scanner, or AI provider.

**Status: runnable simulation scaffold, not a hardware-ready robot controller.**
The SO-101/LeRobot, physical camera and scanner adapters are deliberately disabled.
No real photographs are scanned, no physical arm is moved, and no model service is
called. The demo produces clearly marked synthetic 2×2 PPM images.

## Run in one minute

Python 3.11 or newer. The simulator and tests use only the standard library.

```sh
git clone https://github.com/jpow18/arm_workbench.git
cd arm_workbench

# From the checkout, no installation or network access required:
PYTHONPATH=src python -m arm_workbench list
PYTHONPATH=src python -m arm_workbench run --auto-confirm-simulation
PYTHONPATH=src python -m unittest discover -s tests -v
```

On PowerShell, first set `$env:PYTHONPATH = "src"`, then run the same Python commands
without the `PYTHONPATH=src` prefix. Alternatively, install into a virtual environment:

```sh
python -m venv .venv
. .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -e .
arm-workbench run
```

Installation may fetch the setuptools build tool. The offline `PYTHONPATH` route
does not. Interactive `run` asks an operator to confirm each gate; the explicitly
named auto-confirm option only exercises the simulation.

Each run creates a unique `runs/<run-id>/` folder:

- `manifest.json`: state, confirmation events, errors, and stop failures
- `scene.ppm`: synthetic camera frame
- `scan.ppm`: synthetic scan
- `scan.sha256`: checksum of the simulated scan

Outputs are local and ignored by Git. Do not commit private photographs, device
credentials or local calibration files.

## What works today

- Arm, camera and scanner capability protocols, with deterministic mock adapters
- Trusted task registration and a reusable one-task session runtime
- Photo-scan state machine with three explicit operator gates
- Named-pose motion validation: joint bounds, declared workspace, speed and timeout
- Stop latching, failure logs, per-operation overrun detection and session deadlines
- An allowlisted agent interface and local JSON-lines transport
- Automated tests and a Python 3.11–3.13 CI matrix

There is no autonomous photo pickup, gripper control, scanner-lid control,
perception, inverse kinematics, trajectory planning, collision avoidance, ROS
integration or LLM backend in this release. Photo loading/retrieval are operator
steps. Keeping them explicit makes the first workflow useful as an integration
harness without presenting unbuilt manipulation as a feature.

## Photo-scan workflow

```text
scene_ready [operator]
  → observe camera → move to named staging pose
photo_loaded [operator]
  → request scan → verify synthetic output and checksum
photo_retrieved [operator]
  → move home → completed
```

An error enters `failed` and attempts to stop both arm and scanner. An explicit
stop enters `stopped`. Neither can be reset by an agent; start a new supervised
session after investigating. Confirmation applies only to the current gate and
cannot be replayed. A complete session cannot silently run again.

## AI integration

Any agent can call `AgentTools.call()` or exchange JSON lines with:

```sh
PYTHONPATH=src python -m arm_workbench tool-schema
PYTHONPATH=src python -m arm_workbench tools
```

Example request:

```json
{"tool":"start_task","arguments":{"task":"photo_scan"}}
```

Available tools: `list_tasks`, `start_task`, `task_status`, `advance_task`,
`stop_task`. The agent cannot approve operator gates, choose output paths, supply
motor targets, invoke a shell, or change limits through this dispatcher. It pauses
at `pending_confirmation`. The JSON-lines command has no operator approval route,
so it cannot complete the gated task alone; see the in-process trusted-host example
in [examples/supervised_agent.py](examples/supervised_agent.py).

This interface is an application boundary, **not a sandbox**. A coding agent or
Python plugin with filesystem/process access can change or bypass Python checks.
Before real hardware, put the device controller and approvals in a separate
operator-controlled process with authentication, OS/device permissions, independent
watchdogs and a physical stop. Do not give an LLM access to raw motors or serial ports.

## Extend and connect

- [Architecture and task extension](docs/architecture.md)
- [SO-101 and hardware integration checklist](docs/hardware.md)
- [Local Codex handoff and development workflow](docs/local-codex.md)
- [Safety limitations and incident reporting](SECURITY.md)
- [Third-party licensing](THIRD_PARTY_NOTICES.md)

The project is an application layer intended to use LeRobot as an optional
hardware dependency, not a fork of LeRobot. Hardware support is the next integration
milestone, after local setup and validation. Do not point simulator poses at motors.

## License

Original project code is [MIT licensed](LICENSE). Third-party dependencies retain
their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
