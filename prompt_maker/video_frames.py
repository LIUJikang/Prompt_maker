"""Save full-resolution PNG candidates for the next video's first frame."""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

from PIL import Image


class FrameExtractionError(RuntimeError):
    pass


def extract_video_frames(
    video_path: str | Path, count: int = 4, tail_seconds: float = 1.0
) -> list[Path]:
    """Sample the final N seconds (0 = whole video), including the last frame."""
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 12:
        raise FrameExtractionError("截帧数量必须是 1–12 的整数。")
    if not math.isfinite(tail_seconds) or tail_seconds < 0:
        raise FrameExtractionError("末尾秒数必须是非负有限数值（0 表示整个视频）。")
    path = Path(video_path).resolve()
    if not path.is_file():
        raise FrameExtractionError("视频文件不存在，请先生成视频。")
    try:
        import cv2
    except ImportError as exc:
        raise FrameExtractionError("缺少截帧依赖，请安装 requirements.txt 后重试。") from exc

    capture = cv2.VideoCapture(str(path))
    saved: list[Path] = []
    output_dir = None
    completed = False
    try:
        if not capture.isOpened():
            raise FrameExtractionError("无法打开视频，请检查文件格式或文件是否完整。")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            raise FrameExtractionError("无法读取视频帧率。")
        # Count actual frames; container metadata may overestimate the last frame.
        total = 0
        while capture.grab():
            total += 1
        if total == 0:
            raise FrameExtractionError("视频中没有可读取的画面。")
        start = max(0, total - max(1, math.ceil(tail_seconds * fps))) if tail_seconds else 0
        count = min(count, total - start)
        indices = ([total - 1] if count == 1 else [
            start + round(i * (total - 1 - start) / (count - 1)) for i in range(count)
        ])
        capture.release()
        capture = cv2.VideoCapture(str(path))
        root = path.parent / f"{path.stem}_frames"
        root.mkdir(parents=True, exist_ok=True)
        output_dir = Path(tempfile.mkdtemp(prefix="capture_", dir=root))
        targets = set(indices)
        for index in range(total):
            if not capture.grab():
                raise FrameExtractionError("读取视频中断，请检查视频文件是否完整。")
            if index not in targets:
                continue
            ok, frame = capture.retrieve()
            if not ok or frame is None:
                raise FrameExtractionError(f"无法解码第 {index + 1} 帧。")
            destination = output_dir / f"frame_{index + 1:06d}_{index / fps:.3f}s.png"
            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(destination)
            saved.append(destination)
        completed = True
        return saved
    except (OSError, cv2.error) as exc:
        raise FrameExtractionError(f"截帧或保存图片失败：{exc}") from exc
    finally:
        capture.release()
        if output_dir is not None and not completed:
            for image_path in output_dir.glob("*.png"):
                image_path.unlink(missing_ok=True)
            output_dir.rmdir()
