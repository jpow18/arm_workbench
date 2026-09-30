"""First task module: supervised photo-scanning orchestration in simulation."""
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..runtime import Context


class PhotoScanTask:
    def __init__(self):
        self.state = "await_scene"
        self.pending_confirmation: str | None = "scene_ready"
        self.done = False

    def confirm(self, gate: str) -> None:
        gates = {"scene_ready": "observe", "photo_loaded": "scan",
                 "photo_retrieved": "return_home"}
        if gate != self.pending_confirmation:
            raise ValueError("Wrong operator gate")
        self.state = gates[gate]
        self.pending_confirmation = None

    def step(self, context: "Context") -> None:
        if self.pending_confirmation or self.done:
            raise ValueError("Task cannot advance")
        if self.state == "observe":
            context.operation(lambda: context.camera.capture(context.output / "scene.ppm", timeout_s=10))
            self.state = "stage"
        elif self.state == "stage":
            context.operation(lambda: context.motion.move_named("scan_staging"))
            self.state, self.pending_confirmation = "await_load", "photo_loaded"
        elif self.state == "scan":
            context.operation(lambda: context.scanner.scan(context.output / "scan.ppm", timeout_s=10))
            self.state = "verify"
        elif self.state == "verify":
            artifact = context.output / "scan.ppm"
            data = artifact.read_bytes()
            validate_simulated_scan(data)
            (context.output / "scan.sha256").write_text(sha256(data).hexdigest() + "  scan.ppm\n")
            self.state, self.pending_confirmation = "await_retrieval", "photo_retrieved"
        elif self.state == "return_home":
            context.operation(lambda: context.motion.move_named("home"))
            self.state, self.done = "completed", True
        else:
            raise ValueError(f"Unknown task state: {self.state}")


def validate_simulated_scan(data: bytes) -> None:
    """Validate the deliberately narrow mock PPM format, not real scan quality."""
    parts = data.split(b"\n", 4)
    if len(parts) != 5:
        raise ValueError("Incomplete simulated PPM header")
    magic, comment, dimensions, maximum, pixels = parts
    if magic != b"P6" or not comment.startswith(b"# SIMULATION "):
        raise ValueError("Expected a marked simulated P6 image")
    try:
        width, height = (int(value) for value in dimensions.split())
        max_value = int(maximum)
    except ValueError as exc:
        raise ValueError("Invalid simulated PPM dimensions or maximum") from exc
    if (width, height, max_value) != (2, 2, 255) or len(pixels) != width * height * 3:
        raise ValueError("Invalid simulated PPM dimensions or pixel length")
