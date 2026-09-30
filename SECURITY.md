# Safety and security

This is experimental, simulation-only software. It has no safety certification,
validated motion planner, hardware watchdog, physical emergency stop, authentication
server or working SO-101 driver. Do not use it as a safety system.

The software stop is a latch and best-effort adapter contract, not a physical e-stop.
Timeout checks cannot interrupt blocked device calls. Declared XYZ bounds are not
forward kinematics or collision checks. The numeric limits and poses are illustrative.
Real hardware support must meet the separate checklist in `docs/hardware.md`.

Agent tools are an allowlist, not a sandbox. Run trusted task code only. Keep the
control process, operator approval channel, devices and credentials outside agent
filesystem/shell access. Never expose this demo as an unauthenticated network service.
No cloud upload or telemetry is implemented. Output files may contain private media
once real adapters exist; review permissions and retention before enabling them.

For a security or safety bug, do not publish credentials, private media or an exploit
against live hardware in an issue. Contact the repository maintainer through an
available private channel. General reproducible simulator bugs can use public issues
with synthetic data. If hardware is ever connected during downstream development,
stop physical experimentation until the issue is understood.
