"""Small capability contracts; implementations must enforce their own deadlines."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Pose:
    # Illustrative simulator units, NOT calibrated SO-101 coordinates.
    joints_deg: tuple[float, ...]
    xyz_m: tuple[float, float, float]


class Arm(Protocol):
    simulated: bool

    def move(self, pose: Pose, *, speed_deg_s: float, timeout_s: float) -> None: ...
    def stop(self) -> None:
        """Latch a stop; hardware must provide an independent physical stop path."""
        ...


class Camera(Protocol):
    simulated: bool

    def capture(self, destination: Path, *, timeout_s: float) -> None: ...


class Scanner(Protocol):
    simulated: bool

    def scan(self, destination: Path, *, timeout_s: float) -> None: ...
    def stop(self) -> None: ...
