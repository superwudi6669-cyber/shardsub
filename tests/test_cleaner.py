from __future__ import annotations

import unittest

from shardsub.cleaner import LANG_CN, LANG_EN, clean_segments
from shardsub.config import CleanConfig
from shardsub.types import RawSegment


def make_segment(block_id: int, text: str, avg_score: float | None = 0.9) -> RawSegment:
    return RawSegment(
        block_id=block_id,
        start_time=0.0,
        end_time=1.0,
        start_frame=0,
        end_frame=1,
        text=text,
        best_score=avg_score,
        avg_score=avg_score,
        sample_count=1,
    )


class CleanerTests(unittest.TestCase):
    def test_single_i_is_kept(self) -> None:
        result = clean_segments([make_segment(1, "I")], CleanConfig(min_language_effective_chars=1))
        self.assertEqual([segment.text for segment in result.cleaned_segments], ["I"])
        self.assertEqual(result.dominant_language, LANG_EN)

    def test_single_non_i_letter_is_removed(self) -> None:
        result = clean_segments([make_segment(1, "A")], CleanConfig(min_language_effective_chars=1))
        self.assertEqual(result.cleaned_segments, [])
        self.assertEqual(result.removed_segments[0].reason, "single_letter")

    def test_cn_dominant_foreign_segment_is_removed_with_detail(self) -> None:
        config = CleanConfig(min_language_effective_chars=1)
        result = clean_segments(
            [
                make_segment(1, "我们现在马上离开这里不要再继续停留了"),
                make_segment(2, "他们已经在外面等了很久我们该走了"),
                make_segment(3, "SUBSCRIBE NOW"),
            ],
            config,
        )
        kept_ids = [segment.block_id for segment in result.cleaned_segments]
        removed = result.removed_segments[0]
        self.assertEqual(result.dominant_language, LANG_CN)
        self.assertEqual(kept_ids, [1, 2])
        self.assertEqual(removed.block_id, 3)
        self.assertEqual(removed.reason, "foreign_language_segment")
        self.assertIn("no_cjk", removed.reason_detail)

    def test_common_english_words_are_not_deleted_as_noise(self) -> None:
        result = clean_segments([make_segment(1, "I am here")], CleanConfig(min_language_effective_chars=1))
        self.assertEqual([segment.text for segment in result.cleaned_segments], ["I am here"])


if __name__ == "__main__":
    unittest.main()
