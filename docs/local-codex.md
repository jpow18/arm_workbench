# Local Codex handoff

Use this checklist when continuing on the computer physically connected to the arm.
Do not expose serial devices to a remote model or give an agent unrestricted motor tools.

## First local session

1. Clone `https://github.com/jpow18/arm_workbench.git` and read `README.md`, `SECURITY.md` and `docs/hardware.md`
2. Read local `AGENTS.md` files and relevant `.agents/skills` before editing
3. Run the offline tests and simulator; inspect the generated manifest
4. Inventory OS, Python, SO-101 controller/firmware, mounting, camera, scanner and
   end effector without connecting or energizing actuators
5. Decide the first hardware milestone with the operator: read-only camera capture,
   scanner acquisition, then separately approved arm calibration/motion
6. Keep private calibration, device IDs and personal photographs outside version control

## Suggested Codex task

> Continue arm-workbench on this local checkout. Keep the simulator working and
> preserve the agent/operator separation. Inspect the repository guidance and run
> all tests first. Inventory the available hardware and propose a pinned LeRobot
> adapter design. Implement fake-backed adapter tests before physical integration.
> Do not energize, calibrate or move the arm, operate the real scanner, weaken the
> hardware guards or accept new device permissions without explicit operator
> approval for that hardware step. Report what is simulated, tested locally and
> still unverified separately. Never put secrets or private photos in commits.

## Completion evidence for a hardware milestone

Record tested exact versions, commands, unit/contract test results, operator-approved
physical procedure and observations, stop/watchdog tests and unresolved limitations.
A Python test pass does not prove hardware safety. Keep hardware changes in a reviewable
branch; do not silently publish photos, calibration or machine details.
