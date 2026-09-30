"""Software input checks, not collision avoidance or safety certification."""
import math
from dataclasses import dataclass
from typing import Callable, TypeVar
from time import monotonic

from .ports import Arm, Pose

T = TypeVar("T")


class SafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    joint_ranges: tuple[tuple[float, float], ...] = ((-90.0, 90.0),) * 6
    workspace: tuple[tuple[float, float], ...] = ((0.0, 0.4), (-0.2, 0.2), (0.05, 0.4))
    max_speed_deg_s: float = 15.0
    max_timeout_s: float = 30.0

    def validate(self, pose: Pose, speed: float, timeout: float) -> None:
        if not self.joint_ranges or len(self.workspace) != 3:
            raise SafetyError("Invalid limit dimensions")
        for lo, hi in (*self.joint_ranges, *self.workspace):
            if not math.isfinite(lo) or not math.isfinite(hi) or lo > hi:
                raise SafetyError("Invalid limit interval")
        if (not math.isfinite(self.max_speed_deg_s) or self.max_speed_deg_s <= 0
                or not math.isfinite(self.max_timeout_s) or self.max_timeout_s <= 0):
            raise SafetyError("Invalid maximum speed or timeout")
        if len(pose.joints_deg) != len(self.joint_ranges) or len(pose.xyz_m) != 3:
            raise SafetyError("Pose dimensions do not match limits")
        for value, (lo, hi) in zip((*pose.joints_deg, *pose.xyz_m),
                                   (*self.joint_ranges, *self.workspace), strict=True):
            if not math.isfinite(value) or not lo <= value <= hi:
                raise SafetyError("Pose outside joint/workspace limits")
        if not math.isfinite(speed) or not 0 < speed <= self.max_speed_deg_s:
            raise SafetyError("Speed outside limits")
        if not math.isfinite(timeout) or not 0 < timeout <= self.max_timeout_s:
            raise SafetyError("Timeout outside limits")


class Motion:
    def __init__(self, arm: Arm, poses: dict[str, Pose], limits: Limits = Limits()):
        self.arm, self.poses, self.limits = arm, dict(poses), limits
        self.stopped = False

    def move_named(self, name: str) -> None:
        if self.stopped:
            raise SafetyError("Stop latched; a new supervised session is required")
        if name not in self.poses:
            raise SafetyError("Unknown approved pose")
        pose = self.poses[name]
        self.limits.validate(pose, 10.0, 10.0)
        self.arm.move(pose, speed_deg_s=10.0, timeout_s=10.0)

    def stop(self) -> None:
        self.stopped = True
        self.arm.stop()


def timed(call: Callable[[], T], timeout_s: float, clock: Callable[[], float] = monotonic) -> T:
    """Detect overruns AFTER return. Cannot interrupt a hung hardware call.

    Adapters must implement device timeouts/watchdogs; never use this alone for
    hardware safety or run blocking device IO in the agent process.
    """
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout_s must be finite and positive")
    start = clock()
    result = call()
    if clock() - start > timeout_s:
        raise TimeoutError("Device operation exceeded its deadline")
    return result
