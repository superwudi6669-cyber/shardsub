from __future__ import annotations

from pathlib import Path

import cv2

from .types import VideoInfo


def get_video_info(video_path: str | Path) -> VideoInfo:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    try:
        return VideoInfo(
            fps=cap.get(cv2.CAP_PROP_FPS) or 25.0,
            total_frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
    finally:
        cap.release()


def iter_sampled_frames(video_path: str | Path, every_n: int):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    info = VideoInfo(
        fps=cap.get(cv2.CAP_PROP_FPS) or 25.0,
        total_frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    )
    try:
        index = 0
        while cap.grab():
            if index % every_n == 0:
                ok, frame = cap.retrieve()
                if ok:
                    yield index, index / info.fps, frame, info
            index += 1
    finally:
        cap.release()
