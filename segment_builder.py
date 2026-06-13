from __future__ import annotations

from .config import ExtractConfig
from .similarity import are_similar
from .types import FrameOCRResult, RawSegment


class SegmentBuilder:
    def __init__(self, config: ExtractConfig):
        self.config = config
        self._segments: list[RawSegment] = []
        self._current: dict | None = None
        self._gap = 0
        self._next_id = 1

    def _close_block(self) -> None:
        if self._current is not None:
            scores = self._current.pop("scores")
            self._segments.append(
                RawSegment(
                    block_id=self._current["block_id"],
                    start_time=round(self._current["start_time"], 3),
                    end_time=round(self._current["end_time"], 3),
                    start_frame=self._current["start_frame"],
                    end_frame=self._current["end_frame"],
                    text=self._current["text"],
                    best_score=round(self._current["best_score"], 4),
                    avg_score=round(sum(scores) / len(scores), 4),
                    sample_count=len(scores),
                )
            )
            self._current = None
        self._gap = 0

    def process(self, frame_result: FrameOCRResult) -> None:
        text = frame_result.text
        score = frame_result.avg_score

        if not text:
            if self._current is not None:
                self._gap += 1
                if self._gap > self.config.max_gap_samples:
                    self._close_block()
            return

        if score < self.config.min_frame_score:
            return

        if self._current is not None and are_similar(text, self._current["text"], self.config.merge_similarity):
            self._gap = 0
            self._current["end_time"] = frame_result.time_sec
            self._current["end_frame"] = frame_result.frame_index
            self._current["scores"].append(score)
            if score > self._current["best_score"]:
                self._current["best_score"] = score
                self._current["text"] = text
            return

        self._close_block()
        self._current = {
            "block_id": self._next_id,
            "start_time": frame_result.time_sec,
            "end_time": frame_result.time_sec,
            "start_frame": frame_result.frame_index,
            "end_frame": frame_result.frame_index,
            "text": text,
            "best_score": score,
            "scores": [score],
        }
        self._next_id += 1

    def finish(self) -> list[RawSegment]:
        self._close_block()
        return list(self._segments)
