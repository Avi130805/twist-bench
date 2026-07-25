"""
recorder.py — pipe the live window straight into an mp4 via ffmpeg.

The trick that makes a benchmark run watchable: sample at two different rates.
While the cube is moving we grab frames fast, so turns look smooth. While the
model is thinking — which is most of a real run, often minutes at a time — we
grab one frame every few seconds. Played back at a constant frame rate, the
thinking gaps compress by whatever the ratio is, while the clock burned into the
HUD keeps showing the true elapsed time.

So the viewer sees a fast-moving video that never lies about how long it took.
"""

import shutil
import subprocess
from pathlib import Path


class Recorder:
    def __init__(self, path, width, height, fps=24, active_fps=24.0,
                 idle_fps=2.0, log=print):
        self.path = Path(path)
        self.width = width
        self.height = height
        self.fps = fps
        self.active_interval = 1.0 / max(active_fps, 0.1)
        # idle_fps == 0 means "drop thinking entirely" — the cut then contains
        # only the moves, which is what you want for a shareable clip.
        self.skip_idle = idle_fps <= 0
        self.idle_interval = float("inf") if self.skip_idle else 1.0 / idle_fps
        self.log = log
        self.proc = None
        self.frames = 0
        self.dropped = 0
        self._next_at = 0.0
        self.speedup = max(1.0, active_fps / max(idle_fps, 0.01))

    @staticmethod
    def available() -> bool:
        return shutil.which("ffmpeg") is not None

    def start(self):
        if not self.available():
            raise RuntimeError("ffmpeg not found on PATH — cannot record")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "-",
            "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            # yuv420p + even dimensions: what every player and X expects.
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-movflags", "+faststart",
            str(self.path),
        ]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        self.log(f"[record] writing {self.path}")

    def due(self, now: float, idle: bool) -> bool:
        """Should this frame be captured? Idle frames are sampled far less often."""
        if self.proc is None:
            return False
        if idle and self.skip_idle:
            self.dropped += 1
            return False
        if now < self._next_at:
            self.dropped += 1
            return False
        self._next_at = now + (self.idle_interval if idle else self.active_interval)
        return True

    def write(self, rgb: bytes):
        if self.proc is None or self.proc.stdin is None:
            return
        try:
            self.proc.stdin.write(rgb)
            self.frames += 1
        except (BrokenPipeError, ValueError):
            self.log("[record] ffmpeg pipe closed; recording stopped")
            self.proc = None

    def stop(self):
        if self.proc is None:
            return None
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            try:
                self.proc.kill()
            except OSError:
                pass
        self.proc = None
        self.log(f"[record] finished {self.path} ({self.frames} frames)")
        return self.path
