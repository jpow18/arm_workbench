# SO-101 and hardware integration

## Current boundary

`LeRobotSO101Arm`, `HardwareCamera` and `HardwareScanner` raise
`HardwareUnavailable` at construction. Workbench additionally refuses adapters
whose `simulated` flag is not true. There is no `--hardware` switch. These are
intentional integration seams, not tested drivers; deleting a guard is not a
hardware implementation.

The current task stages an arm, asks the operator to load a photo, scans, asks the
operator to retrieve it, and returns home. Future autonomous pickup requires an
appropriate end effector, handling fragile media, sensing, collision clearance and
verified grasp/release procedures. An SO-101 alone does not supply these capabilities.

## LeRobot API baseline

Official documentation inspected on 2026-09-30:

- [SO-101 setup and calibration](https://huggingface.co/docs/lerobot/main/en/so101)
- [Robot API reference](https://huggingface.co/docs/lerobot/main/api/robots)
- [Bring your own hardware](https://huggingface.co/docs/lerobot/main/en/integrate_hardware)
- [Upstream source](https://github.com/huggingface/lerobot)
- [Upstream license and bundled notices](https://github.com/huggingface/lerobot/blob/main/LICENSE)

The current main documentation imports `SO101Follower` and `SO101FollowerConfig`
from `lerobot.robots.so_follower`. The robot abstraction includes connection,
observation, action and disconnect methods. Older examples use a different module
layout. Verify imports against the exact installed version rather than mixing
main documentation with a released wheel. Do not automatically calibrate/connect
as a side effect of importing this project.

## Pinning policy

The simulation has no runtime dependencies. LeRobot is not installed, pinned or
claimed compatible yet. Before hardware implementation:

1. Choose a reviewed official release or immutable full commit, supported Python,
   OS and motor interface. Record them in a hardware-specific dependency lockfile
2. Install in a separate local virtual environment, using the official guide for
   the selected revision; do not install moving `main` into an active robot system
3. Verify SO-101 imports, units, calibration behavior, observation timestamps,
   torque/disconnect semantics and `send_action` semantics at that revision
4. Pin transitive dependencies and retain the lockfile, upstream licenses and
   third-party notices; store serial paths and calibration outside the public repo
5. Add adapter contract tests with fakes, then explicitly approved supervised tests
   on the actual arm before declaring a hardware compatibility matrix

No upstream source is vendored. If source is copied later, retain all applicable
copyright headers, licenses and notices instead of relabeling it as this project's code.

## Required before energizing motors

- Known device identity and serial port, stable bench mounting and power isolation
- Operator-reviewed mechanical condition, payload and end-effector setup
- Local calibration, joint units and limits; no simulator values on hardware
- Independent physical stop with a tested safe stop behavior for this setup
- Watchdog independent of agent process, bounded device IO and lost-client handling
- Verified trajectories, forward kinematics and collision/swept-volume checks
- Speed/acceleration/payload constraints checked against real observations
- Separate operator approval channel, run-bound one-use approvals and expiry
- Manual, low-speed incremental commissioning with people outside the workspace
- Fault tests for unplugged camera, lost motor bus, stalled scanner, power loss,
  stale observations, rejected approvals and process termination

Do not assume disabling motor torque is always a safe stop: an unsupported arm or
load can fall. Define safe stopping for the actual mounting, payload and fixtures.
This project is not safety certified and is not for operation near people without
an appropriate engineered risk assessment.

## Camera and scanner

Choose actual hardware and an OS-supported API first. Camera implementation needs
frame freshness, timestamping, calibration and loss detection. Scanner implementation
needs device selection, bounded acquisition, output verification and a cancellation
contract. Prefer an explicit supported scanner API over unbounded shell commands.
Real scan quality checks must include dimensions, format, completeness and appropriate
human review; the mock PPM check is only a demonstration.

Add real hardware only through a reviewed change that replaces these stubs, separates
the hardware control process, and documents tested devices and remaining limitations.
