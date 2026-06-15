from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class VideoInfo:
    fps: float
    total_frames: int
    width: int
    height: int


@dataclass
class SubtitleBand:
    y_start_ratio: float
    y_end_ratio: float
    fallback_used: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class FrameOCRResult:
    frame_index: int
    time_sec: float
    text: str
    avg_score: float
    texts: list[str]
    scores: list[float]
    polys: list[Any]
    video_info: VideoInfo


@dataclass
class RawSegment:
    block_id: int
    start_time: float | str | None
    end_time: float | str | None
    start_frame: int | None
    end_frame: int | None
    text: str
    best_score: float | None = None
    avg_score: float | None = None
    sample_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RemovedSegment:
    block_id: int
    original_text: str
    normalized_text: str
    cleaned_text_before_drop: str
    reason: str
    reason_detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CleanResult:
    cleaned_segments: list[RawSegment]
    dominant_language: str
    removed_segments: list[RemovedSegment]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cleaned_segments": [segment.to_dict() for segment in self.cleaned_segments],
            "dominant_language": self.dominant_language,
            "removed_segments": [segment.to_dict() for segment in self.removed_segments],
        }


@dataclass
class ExtractionSummary:
    video_path: str
    width: int | None
    height: int | None
    fps: float
    band_y_start_ratio: float
    band_y_end_ratio: float
    ocr_every_n_frames: int
    runtime_seconds: float
    raw_segment_count: int
    cleaned_segment_count: int
    dominant_language: str | None = None
    subtitle_srt_source: str = "cleaned_segments"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionResult:
    video_path: str
    band: SubtitleBand
    raw_segments: list[RawSegment]
    cleaned_segments: list[RawSegment]
    summary: ExtractionSummary
    dominant_language: str | None = None
    removed_segments: list[RemovedSegment] | None = None
    debug_frame_rows: list[dict[str, Any]] | None = None

    @property
    def segments(self) -> list[RawSegment]:
        return self.cleaned_segments

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_path": self.video_path,
            "band": asdict(self.band),
            "segments": [segment.to_dict() for segment in self.cleaned_segments],
            "raw_segments": [segment.to_dict() for segment in self.raw_segments],
            "dominant_language": self.dominant_language,
            "removed_segments": [segment.to_dict() for segment in (self.removed_segments or [])],
            "summary": self.summary.to_dict(),
            "debug_frame_rows": self.debug_frame_rows,
        }
