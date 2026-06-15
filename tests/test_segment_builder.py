from __future__ import annotations

import unittest

from shardsub.config import ExtractConfig
from shardsub.segment_builder import SegmentBuilder
from shardsub.types import FrameOCRResult, VideoInfo


VIDEO_INFO = VideoInfo(fps=25.0, total_frames=100, width=1920, height=1080)


def frame(frame_index: int, time_sec: float, text: str, score: float) -> FrameOCRResult:
    texts = [text] if text else []
    scores = [score] if text else []
    return FrameOCRResult(
        frame_index=frame_index,
        time_sec=time_sec,
        text=text,
        avg_score=score if text else 0.0,
        texts=texts,
        scores=scores,
        polys=[],
        video_info=VIDEO_INFO,
    )


class SegmentBuilderTests(unittest.TestCase):
    def test_similar_text_extends_existing_block_and_keeps_best_text(self) -> None:
        builder = SegmentBuilder(ExtractConfig(merge_similarity=0.8, max_gap_samples=1, min_frame_score=0.6))
        builder.process(frame(0, 0.0, "hello", 0.70))
        builder.process(frame(3, 0.12, "hello!", 0.95))
        segments = builder.finish()

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].block_id, 1)
        self.assertEqual(segments[0].text, "hello!")
        self.assertEqual(segments[0].sample_count, 2)
        self.assertEqual(segments[0].start_frame, 0)
        self.assertEqual(segments[0].end_frame, 3)

    def test_gap_within_limit_keeps_block_open(self) -> None:
        builder = SegmentBuilder(ExtractConfig(merge_similarity=0.8, max_gap_samples=1, min_frame_score=0.6))
        builder.process(frame(0, 0.0, "same text", 0.80))
        builder.process(frame(3, 0.12, "", 0.0))
        builder.process(frame(6, 0.24, "same text", 0.82))
        segments = builder.finish()

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].sample_count, 2)
        self.assertEqual(segments[0].end_frame, 6)

    def test_gap_beyond_limit_closes_previous_block(self) -> None:
        builder = SegmentBuilder(ExtractConfig(merge_similarity=0.8, max_gap_samples=1, min_frame_score=0.6))
        builder.process(frame(0, 0.0, "alpha", 0.80))
        builder.process(frame(3, 0.12, "", 0.0))
        builder.process(frame(6, 0.24, "", 0.0))
        builder.process(frame(9, 0.36, "beta", 0.85))
        segments = builder.finish()

        self.assertEqual([segment.block_id for segment in segments], [1, 2])
        self.assertEqual([segment.text for segment in segments], ["alpha", "beta"])

    def test_low_score_frame_does_not_start_block(self) -> None:
        builder = SegmentBuilder(ExtractConfig(merge_similarity=0.8, max_gap_samples=1, min_frame_score=0.6))
        builder.process(frame(0, 0.0, "weak", 0.40))
        segments = builder.finish()
        self.assertEqual(segments, [])


if __name__ == "__main__":
    unittest.main()
