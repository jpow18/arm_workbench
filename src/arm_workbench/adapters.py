"""Deterministic mock devices and deliberately disabled hardware integration."""
from pathlib import Path

from .ports import Pose
from .safety import SafetyError


def placeholder(destination: Path, label: str) -> None:
    # Portable pixmap: real, viewable image bytes; explicitly synthetic content.
    destination.write_bytes(f"P6\n# SIMULATION {label}\n2 2\n255\n".encode()
                            + bytes([30, 80, 150, 230, 200, 80, 230, 200, 80, 30, 80, 150]))


class MockArm:
    simulated = True

    def __init__(self):
        self.moves: list[Pose] = []
        self.stopped = False

    def move(self, pose: Pose, *, speed_deg_s: float, timeout_s: float) -> None:
        if self.stopped:
            raise SafetyError("Mock arm stopped")
        self.moves.append(pose)

    def stop(self) -> None:
        self.stopped = True


class MockCamera:
    simulated = True

    def capture(self, destination: Path, *, timeout_s: float) -> None:
        placeholder(destination, "camera frame")


class MockScanner:
    simulated = True

    def __init__(self):
        self.stopped = False

    def scan(self, destination: Path, *, timeout_s: float) -> None:
        if self.stopped:
            raise SafetyError("Mock scanner stopped")
        placeholder(destination, "scanner output; not an actual photograph")

    def stop(self) -> None:
        self.stopped = True


class HardwareUnavailable(RuntimeError):
    pass


class LeRobotSO101Arm:
    """Integration seam, not a working hardware driver.

    Official API researched 2026-09-30: SO101Follower / SO101FollowerConfig
    from lerobot.robots.so_follower. See docs/hardware.md before implementing.
    No LeRobot import or device connection occurs here.
    """
    simulated = False

    def __init__(self, *, port: str | None = None):
        raise HardwareUnavailable(
            "SO-101 hardware is disabled: implement and validate the LeRobot adapter, "
            "calibration, supervised trajectories, device watchdog and physical stop first"
        )


class HardwareCamera:
    simulated = False

    def __init__(self):
        raise HardwareUnavailable("Real camera capture is not implemented")


class HardwareScanner:
    simulated = False

    def __init__(self):
        raise HardwareUnavailable("Real scanner control is not implemented")
