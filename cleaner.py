from __future__ import annotations

import os
import re
from typing import Iterable

from .config import CleanConfig
from .types import CleanResult, RawSegment, RemovedSegment


LANG_CN = "CN"
LANG_EN = "EN"
LANG_UNKNOWN = "UNKNOWN"


def is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def is_english(char: str) -> bool:
    return "a" <= char.lower() <= "z"


class SubtitleCleaner:
    CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
    MULTI_SPACE_RE = re.compile(r"\s+")
    ONLY_DIGITS_RE = re.compile(r"^[\d\s]+$")
    ONLY_SYMBOLS_RE = re.compile(r"^[^\w\u4e00-\u9fff]+$", re.UNICODE)
    ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z']*")
    LEADING_INDEX_RE = re.compile(r"^\s*\d{1,3}[\s._\-:]+")
    LEADING_DIRTY_RE = re.compile(r"^[\s#@&*~=`|/\\\[\]{}<>（）()【】《》「」『』]+")
    TRAILING_DIRTY_RE = re.compile(r"[\s#@&*~=`|/\\\[\]{}<>（）()【】《》「」『』]+$")
    TRAILING_ISOLATED_INDEX_RE = re.compile(r"^(.*?)([\s._\-:]+)(\d{1,3})\s*$")
    URL_HINT_RE = re.compile(r"(https?://|www\.|\.com\b|\.net\b|\.cn\b)", re.IGNORECASE)
    CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")

    def __init__(self, config: CleanConfig | None = None):
        self.config = config or CleanConfig()
        self.common_english_words = {
            "a",
            "am",
            "an",
            "and",
            "are",
            "at",
            "be",
            "boss",
            "but",
            "by",
            "come",
            "dad",
            "daddy",
            "do",
            "for",
            "get",
            "go",
            "good",
            "have",
            "he",
            "hello",
            "help",
            "her",
            "here",
            "hey",
            "him",
            "home",
            "i",
            "if",
            "im",
            "in",
            "is",
            "it",
            "its",
            "jack",
            "leave",
            "let",
            "love",
            "me",
            "mom",
            "mommy",
            "mr",
            "mrs",
            "my",
            "no",
            "not",
            "now",
            "of",
            "oh",
            "ok",
            "okay",
            "on",
            "or",
            "our",
            "out",
            "please",
            "ready",
            "see",
            "she",
            "sir",
            "sorry",
            "stop",
            "thank",
            "thanks",
            "that",
            "the",
            "them",
            "there",
            "they",
            "this",
            "to",
            "up",
            "us",
            "vip",
            "wait",
            "we",
            "what",
            "who",
            "why",
            "yes",
            "you",
            "your",
        }

    def normalize_text(self, text: str) -> str:
        text = self.CONTROL_CHARS_RE.sub("", text or "")
        text = text.replace("\u3000", " ").replace("\xa0", " ")
        text = self.MULTI_SPACE_RE.sub(" ", text)
        return text.strip()

    def count_char_types(self, text: str) -> tuple[int, int, int, int]:
        cn_count = sum(1 for ch in text if is_cjk(ch))
        en_count = sum(1 for ch in text if is_english(ch))
        digit_count = sum(1 for ch in text if ch.isdigit())
        effective_count = cn_count + en_count + digit_count
        return cn_count, en_count, digit_count, effective_count

    def is_pure_number(self, text: str) -> bool:
        return bool(self.ONLY_DIGITS_RE.fullmatch(text))

    def is_pure_symbol(self, text: str) -> bool:
        return bool(self.ONLY_SYMBOLS_RE.fullmatch(text))

    def _passes_single_i_exception(self, text: str) -> bool:
        letters = re.sub(r"[^A-Za-z]", "", text)
        return len(letters) == 1 and letters.upper() == "I"

    def _is_single_letter_noise(self, text: str) -> bool:
        letters = re.sub(r"[^A-Za-z]", "", text)
        if len(letters) != 1:
            return False
        return letters.upper() != "I"

    def _is_vowel_poor_token(self, token: str) -> bool:
        letters = re.sub(r"[^A-Za-z]", "", token).upper()
        if len(letters) < 4:
            return False
        vowel_count = sum(1 for ch in letters if ch in "AEIOUY")
        return vowel_count / len(letters) < 0.25

    def _has_repeated_char_noise(self, token: str) -> bool:
        letters = re.sub(r"[^A-Za-z]", "", token).upper()
        if len(letters) < self.config.min_noise_token_length:
            return False
        most_common = max((letters.count(ch) for ch in set(letters)), default=0)
        return most_common / len(letters) >= 0.6

    def _is_safe_upper_token(self, token: str) -> bool:
        upper = token.upper()
        return len(upper) <= 3 or upper in self.config.safe_upper_tokens

    def _is_safe_mixed_token(self, token: str) -> bool:
        return token in self.config.safe_mixed_tokens or token.upper() in self.config.safe_upper_tokens

    def is_noise_english_token(self, token: str) -> bool:
        letters = re.sub(r"[^A-Za-z]", "", token)
        if len(letters) < 4:
            return False

        if len(letters) < self.config.min_noise_token_length:
            return False

        if self._is_safe_upper_token(token) or self._is_safe_mixed_token(token):
            return False

        upper = letters.upper()
        lower = letters.lower()
        if lower in self.common_english_words:
            return False

        unique_ratio = len(set(upper)) / max(len(upper), 1)
        if self._has_repeated_char_noise(token) and unique_ratio <= 0.5:
            return True

        if letters.isupper() and len(letters) >= 6 and self._is_vowel_poor_token(token):
            return True

        return False

    def is_probably_noise(self, text: str) -> bool:
        text = self.normalize_text(text)
        if not text:
            return True

        if self.is_pure_number(text) or self.is_pure_symbol(text):
            return True

        if self._is_single_letter_noise(text):
            return True

        letters_only = re.sub(r"[^A-Za-z]", "", text)
        if len(letters_only) >= 12 and len(set(letters_only.upper())) <= 4:
            return True

        if self.URL_HINT_RE.search(text):
            return True

        if re.fullmatch(r"[A-Z\s']+", text):
            tokens = [token.strip("'") for token in re.findall(r"[A-Z']+", text)]
            long_tokens = [token for token in tokens if len(token) >= 4]
            common_hits = sum(1 for token in long_tokens if token.lower() in self.common_english_words)
            vowel_poor = sum(1 for token in long_tokens if self._is_vowel_poor_token(token))

            if long_tokens and common_hits == 0 and len(long_tokens) >= 2:
                return True

            if len(long_tokens) == 1 and len(long_tokens[0]) >= 8 and vowel_poor == 1:
                return True

        return False

    def _coerce_segment(self, segment) -> RawSegment:
        if isinstance(segment, RawSegment):
            return RawSegment(
                block_id=int(segment.block_id),
                start_time=segment.start_time,
                end_time=segment.end_time,
                start_frame=segment.start_frame,
                end_frame=segment.end_frame,
                text=segment.text,
                best_score=segment.best_score,
                avg_score=segment.avg_score,
                sample_count=segment.sample_count,
            )
        if isinstance(segment, dict):
            return RawSegment(
                block_id=int(segment["block_id"]),
                start_time=segment.get("start_time"),
                end_time=segment.get("end_time"),
                start_frame=segment.get("start_frame"),
                end_frame=segment.get("end_frame"),
                text=str(segment.get("text", "")),
                best_score=segment.get("best_score"),
                avg_score=segment.get("avg_score"),
                sample_count=segment.get("sample_count"),
            )
        raise TypeError(f"Unsupported segment type: {type(segment)!r}")

    def _build_removed(
        self,
        segment: RawSegment,
        normalized_text: str,
        cleaned_text_before_drop: str,
        reason: str,
        reason_detail: str = "",
    ) -> RemovedSegment:
        return RemovedSegment(
            block_id=segment.block_id,
            original_text=segment.text,
            normalized_text=normalized_text,
            cleaned_text_before_drop=cleaned_text_before_drop,
            reason=reason,
            reason_detail=reason_detail,
        )

    def detect_dominant_language_from_segments(self, segments: Iterable[RawSegment]) -> str:
        cn_count = 0
        en_count = 0
        effective_count = 0

        for segment in segments:
            normalized = self.normalize_text(segment.text)
            seg_cn, seg_en, _seg_digit, seg_effective = self.count_char_types(normalized)
            cn_count += seg_cn
            en_count += seg_en
            effective_count += seg_effective

        if effective_count < self.config.min_language_effective_chars:
            return LANG_UNKNOWN

        total_lang_chars = cn_count + en_count
        if total_lang_chars == 0:
            return LANG_UNKNOWN

        cn_ratio = cn_count / total_lang_chars
        en_ratio = en_count / total_lang_chars

        if cn_ratio >= self.config.dominant_language_min_ratio:
            return LANG_CN
        if en_ratio >= self.config.dominant_language_min_ratio:
            return LANG_EN
        return LANG_UNKNOWN

    def _is_safe_english_segment_in_cn(self, text: str) -> bool:
        tokens = self.ENGLISH_TOKEN_RE.findall(text)
        if not tokens:
            return False

        if len(tokens) == 1:
            token = tokens[0]
            if token.upper() in self.config.safe_upper_tokens:
                return True
            if token in self.config.safe_mixed_tokens:
                return True
            if len(token) <= 3:
                return True
            if token.istitle() and len(token) <= 10:
                return True

        if len(tokens) <= 2 and all(
            token.upper() in self.config.safe_upper_tokens or token in self.config.safe_mixed_tokens
            for token in tokens
        ):
            return True

        return False

    def _strip_edge_noise(self, text: str) -> str:
        text = self.normalize_text(text)
        text = self.LEADING_INDEX_RE.sub("", text)

        match = self.TRAILING_ISOLATED_INDEX_RE.match(text)
        if match:
            candidate = self.normalize_text(match.group(1))
            separator = match.group(2)
            if candidate and self._should_strip_trailing_index(candidate, separator):
                text = candidate

        previous = None
        while previous != text:
            previous = text
            text = self.LEADING_DIRTY_RE.sub("", text)
            text = self.TRAILING_DIRTY_RE.sub("", text)
            text = self.normalize_text(text)
        return text

    def _remove_noise_english_tokens(self, text: str) -> str:
        def replace(match):
            token = match.group(0)
            return "" if self.is_noise_english_token(token) else token

        cleaned = self.ENGLISH_TOKEN_RE.sub(replace, text)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        return cleaned.strip()

    def _clean_cn_text(self, text: str) -> tuple[str, str, str]:
        cn_count, en_count, _digit_count, _effective_count = self.count_char_types(text)
        if cn_count == 0 and en_count >= self.config.min_foreign_segment_english_chars:
            if self.URL_HINT_RE.search(text) or not self._is_safe_english_segment_in_cn(text):
                return "", "foreign_language_segment", f"CN dominant, no_cjk, en_letters={en_count}"
            return text, "", ""

        if cn_count > 0 and en_count > 0:
            cleaned = self._remove_noise_english_tokens(text)
            return cleaned, "", ""

        return text, "", ""

    def _clean_en_text(self, text: str) -> tuple[str, str, str]:
        cn_count, en_count, _digit_count, _effective_count = self.count_char_types(text)
        if en_count == 0 and cn_count >= self.config.min_foreign_segment_chinese_chars:
            return "", "foreign_language_segment", f"EN dominant, no_english, cn_chars={cn_count}"

        cleaned = text
        if en_count > 0 and cn_count > 0:
            cleaned = self.CJK_RUN_RE.sub("", cleaned)
            cleaned = self.normalize_text(cleaned)

        cleaned = self._remove_noise_english_tokens(cleaned)
        return cleaned, "", ""

    def _should_strip_trailing_index(self, candidate: str, separator: str) -> bool:
        if any(ch in "._-:" for ch in separator):
            return True

        if re.search(r"[\u4e00-\u9fff]", candidate):
            return True

        if re.search(r"[A-Za-z]{2,}\s*$", candidate):
            return False

        return True

    def _passes_single_cjk_exception(self, text: str, segment: RawSegment, dominant_language: str) -> bool:
        if dominant_language != LANG_CN:
            return False
        if len(text) != 1 or not is_cjk(text):
            return False
        if segment.avg_score is None:
            return True
        return segment.avg_score >= self.config.keep_single_cjk_score

    def _apply_base_filters(self, segment: RawSegment, normalized_text: str, dominant_language: str):
        if not normalized_text:
            return "", self._build_removed(segment, normalized_text, "", "empty_text")

        if self.is_pure_number(normalized_text):
            return "", self._build_removed(segment, normalized_text, normalized_text, "pure_number")

        if self.is_pure_symbol(normalized_text):
            return "", self._build_removed(segment, normalized_text, normalized_text, "pure_symbol")

        if self._is_single_letter_noise(normalized_text):
            return "", self._build_removed(segment, normalized_text, normalized_text, "single_letter")

        _cn_count, _en_count, _digit_count, effective_count = self.count_char_types(normalized_text)
        if (
            effective_count < self.config.min_effective_chars
            and not self._passes_single_cjk_exception(normalized_text, segment, dominant_language)
            and not self._passes_single_i_exception(normalized_text)
        ):
            reason = (
                "single_cjk_low_score"
                if len(normalized_text) == 1 and any(is_cjk(ch) for ch in normalized_text)
                else "too_few_effective_chars"
            )
            return "", self._build_removed(segment, normalized_text, normalized_text, reason)

        if self.is_probably_noise(normalized_text):
            return "", self._build_removed(segment, normalized_text, normalized_text, "too_few_effective_chars")

        return normalized_text, None

    def _clean_segment_text(self, segment: RawSegment, dominant_language: str):
        normalized_text = self.normalize_text(segment.text)
        normalized_text, removed = self._apply_base_filters(segment, normalized_text, dominant_language)
        if removed:
            return None, removed

        cleaned_text = normalized_text
        reason = ""
        reason_detail = ""

        if dominant_language == LANG_CN:
            cleaned_text, reason, reason_detail = self._clean_cn_text(cleaned_text)
        elif dominant_language == LANG_EN:
            cleaned_text, reason, reason_detail = self._clean_en_text(cleaned_text)

        if reason:
            return None, self._build_removed(segment, normalized_text, cleaned_text, reason, reason_detail)

        cleaned_text = self._strip_edge_noise(cleaned_text)

        if not cleaned_text:
            return None, self._build_removed(segment, normalized_text, cleaned_text, "post_clean_empty")

        if self.is_pure_number(cleaned_text):
            return None, self._build_removed(segment, normalized_text, cleaned_text, "pure_number")

        if self.is_pure_symbol(cleaned_text):
            return None, self._build_removed(segment, normalized_text, cleaned_text, "pure_symbol")

        _cn_count, _en_count, _digit_count, effective_count = self.count_char_types(cleaned_text)
        if (
            effective_count < self.config.min_effective_chars
            and not self._passes_single_cjk_exception(cleaned_text, segment, dominant_language)
            and not self._passes_single_i_exception(cleaned_text)
        ):
            reason = (
                "single_cjk_low_score"
                if len(cleaned_text) == 1 and any(is_cjk(ch) for ch in cleaned_text)
                else "too_few_effective_chars"
            )
            return None, self._build_removed(segment, normalized_text, cleaned_text, reason)

        if self.is_probably_noise(cleaned_text):
            reason = "english_noise_token_only" if re.search(r"[A-Za-z]", cleaned_text) else "post_clean_empty"
            return None, self._build_removed(segment, normalized_text, cleaned_text, reason)

        return RawSegment(
            block_id=segment.block_id,
            start_time=segment.start_time,
            end_time=segment.end_time,
            start_frame=segment.start_frame,
            end_frame=segment.end_frame,
            text=cleaned_text,
            best_score=segment.best_score,
            avg_score=segment.avg_score,
            sample_count=segment.sample_count,
        ), None

    def clean_segments(self, segments, config: CleanConfig | None = None) -> CleanResult:
        if config is not None:
            self.config = config

        coerced_segments = [self._coerce_segment(segment) for segment in segments]
        if not self.config.clean_enable:
            return CleanResult(
                cleaned_segments=coerced_segments,
                dominant_language=LANG_UNKNOWN,
                removed_segments=[],
            )

        dominant_language = self.detect_dominant_language_from_segments(coerced_segments)
        cleaned_segments: list[RawSegment] = []
        removed_segments: list[RemovedSegment] = []

        for segment in coerced_segments:
            cleaned_segment, removed_segment = self._clean_segment_text(segment, dominant_language)
            if cleaned_segment is not None:
                cleaned_segments.append(cleaned_segment)
            elif removed_segment is not None:
                removed_segments.append(removed_segment)

        return CleanResult(
            cleaned_segments=cleaned_segments,
            dominant_language=dominant_language,
            removed_segments=removed_segments,
        )

    def parse_srt_content(self, srt_content: str) -> list[RawSegment]:
        segments: list[RawSegment] = []
        lines = srt_content.replace("\r\n", "\n").split("\n")
        index = 0
        while index < len(lines):
            current = lines[index].strip()
            if not current:
                index += 1
                continue

            if not re.fullmatch(r"\d+", current):
                index += 1
                continue

            if index + 2 >= len(lines):
                break

            block_id = int(current)
            time_range = lines[index + 1].strip()
            text = lines[index + 2].strip()
            start_time = None
            end_time = None
            if "-->" in time_range:
                start_time, end_time = [part.strip() for part in time_range.split("-->", 1)]

            segments.append(
                RawSegment(
                    block_id=block_id,
                    start_time=start_time,
                    end_time=end_time,
                    start_frame=None,
                    end_frame=None,
                    text=text,
                    best_score=None,
                    avg_score=None,
                    sample_count=None,
                )
            )
            index += 4
        return segments

    def process_srt(self, srt_path: str, output_path: str | None = None) -> CleanResult | None:
        if not os.path.exists(srt_path):
            return None

        with open(srt_path, "r", encoding="utf-8") as file_obj:
            content = file_obj.read()

        raw_segments = self.parse_srt_content(content)
        result = self.clean_segments(raw_segments)

        final_lines = []
        for segment in result.cleaned_segments:
            if not segment.start_time or not segment.end_time:
                continue
            final_lines.append(str(segment.block_id))
            final_lines.append(f"{segment.start_time} --> {segment.end_time}")
            final_lines.append(segment.text)
            final_lines.append("")

        if output_path is None:
            output_path = srt_path

        with open(output_path, "w", encoding="utf-8") as file_obj:
            file_obj.write("\n".join(final_lines))

        return result


def clean_segments(segments, config: CleanConfig | None = None) -> CleanResult:
    return SubtitleCleaner(config).clean_segments(segments)


def clean_srt_file(srt_path: str):
    cleaner = SubtitleCleaner()
    return cleaner.process_srt(srt_path)
