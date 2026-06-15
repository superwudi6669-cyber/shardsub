from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

import cv2

from .config import OutputConfig
from .types import ExtractionResult, SubtitleBand


def _format_srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def resolve_video_output_dir(output_root: str | Path | None, video_path: str | Path) -> Path | None:
    if output_root is None:
        return None
    return Path(output_root) / Path(video_path).stem


def save_debug_crop_image(output_root: str | Path | None, video_path: str | Path, frame_index: int, crop) -> None:
    video_dir = resolve_video_output_dir(output_root, video_path)
    if video_dir is None:
        return
    image_dir = video_dir / "image"
    image_dir.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(image_dir / f"frame_{frame_index:06d}.jpg"), crop)


def write_subtitle_band(output_root: str | Path | None, band: SubtitleBand) -> None:
    if output_root is None:
        return
    out_dir = Path(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "subtitle_band.json").write_text(
        json.dumps(asdict(band), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_extraction_outputs(
    result: ExtractionResult,
    output_root: str | Path | None,
    output_config: OutputConfig,
    tail_seconds: float,
) -> None:
    video_dir = resolve_video_output_dir(output_root, result.video_path)
    if video_dir is None:
        return

    video_dir.mkdir(parents=True, exist_ok=True)
    segments = result.cleaned_segments

    srt_blocks = [
        f"{segment.block_id}\n"
        f"{_format_srt_time(segment.start_time)} --> {_format_srt_time(segment.end_time + tail_seconds)}\n"
        f"{segment.text}\n"
        for segment in segments
    ]
    (video_dir / "subtitles.srt").write_text("\n".join(srt_blocks), encoding="utf-8")

    (video_dir / "raw_segments.json").write_text(
        json.dumps([segment.to_dict() for segment in result.raw_segments], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (video_dir / "llm_blocks.json").write_text(
        json.dumps([{"id": segment.block_id, "text": segment.text} for segment in segments], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (video_dir / "summary.json").write_text(
        json.dumps(result.summary.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if output_config.save_frame_csv and result.debug_frame_rows:
        with (video_dir / "raw_frames.csv").open("w", encoding="utf-8-sig", newline="") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=list(result.debug_frame_rows[0]))
            writer.writeheader()
            writer.writerows(result.debug_frame_rows)
