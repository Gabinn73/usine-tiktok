"""Encodage H.264 : les frames RGB brutes sont envoyées en pipe à ffmpeg."""
import subprocess
from pathlib import Path

import pygame

from . import config as C


class Encoder:
    def __init__(self, out_path, width=C.WIDTH, height=C.HEIGHT, fps=C.FPS, crf=20):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out_path),
        ]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        self.frames = 0

    def write(self, surf: pygame.Surface):
        self.proc.stdin.write(pygame.image.tobytes(surf, "RGB"))
        self.frames += 1

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError(f"ffmpeg a échoué (code {self.proc.returncode})")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.close()
        else:
            self.proc.kill()


def mux(video_path, wav_path, out_path):
    """Assemble la vidéo (copiée telle quelle) et la bande-son (AAC 192 kb/s)."""
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(video_path), "-i", str(wav_path),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", str(out_path),
    ], check=True)
