from __future__ import annotations

from pathlib import Path

from .band_detector import detect_subtitle_band
from .cleaner import clean_segments
from .config import ExtractorConfig
from .image_ops import crop_band_region
from .ocr_engine import OCREngine
from .ocr_parser import parse_frame_ocr_result
from .segment_builder import SegmentBuilder
from .types import ExtractionResult, ExtractionSummary, SubtitleBand
from .video_io import iter_sampled_frames
from .writer import save_debug_crop_image, write_extraction_outputs, write_subtitle_band


def _resolve_output_root(output_dir: str | Path | None, config: ExtractorConfig) -> Path | None:
    if output_dir is not None:
        return Path(output_dir)
    if config.output.output_dir is not None:
        return Path(config.output.output_dir)
    return None


class SubtitleExtractor:
    def __init__(self, config: ExtractorConfig | None = None):
        self.config = config or ExtractorConfig()
        self.engine = OCREngine(self.config.model)

    def close(self) -> None:
        self.engine.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def detect_band(self, video_paths: list[str | Path]) -> SubtitleBand:
        return detect_subtitle_band(video_paths, self.config.band_detect, self.engine)

    def extract(
        self,
        video_path: str | Path,
        band: SubtitleBand | None = None,
        output_dir: str | Path | None = None,
    ) -> ExtractionResult:
        import time

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        resolved_band = band or self.detect_band([video_path])
        output_root = _resolve_output_root(output_dir, self.config)
        debug_frame_rows: list[dict] | None = [] if self.config.output.save_frame_csv else None
        builder = SegmentBuilder(self.config.extract)
        info = None
        started = time.perf_counter()

        for frame_index, time_sec, frame, info in iter_sampled_frames(video_path, self.config.extract.ocr_every_n_frames):
            crop, _, _ = crop_band_region(frame, resolved_band, info, preprocess=self.config.image)
            result = self.engine.predict(crop)
            frame_result = parse_frame_ocr_result(result, frame_index, time_sec, info)
            builder.process(frame_result)

            if debug_frame_rows is not None:
                debug_frame_rows.append(
                    {
                        "frame_index": frame_index,
                        "time_sec": round(time_sec, 3),
                        "avg_score": round(frame_result.avg_score, 4),
                        "text": frame_result.text,
                    }
                )
            if self.config.output.save_crop_images and output_root is not None:
                save_debug_crop_image(output_root, video_path, frame_index, crop)

        runtime_seconds = round(time.perf_counter() - started, 3)
        raw_segments = builder.finish()
        clean_result = clean_segments(raw_segments, self.config.clean)
        cleaned_segments = clean_result.cleaned_segments
        fps = info.fps if info is not None else 25.0
        tail_seconds = self.config.extract.ocr_every_n_frames / fps

        summary = ExtractionSummary(
            video_path=str(video_path),
            width=info.width if info is not None else None,
            height=info.height if info is not None else None,
            fps=round(fps, 3),
            band_y_start_ratio=resolved_band.y_start_ratio,
            band_y_end_ratio=resolved_band.y_end_ratio,
            ocr_every_n_frames=self.config.extract.ocr_every_n_frames,
            runtime_seconds=runtime_seconds,
            raw_segment_count=len(raw_segments),
            cleaned_segment_count=len(cleaned_segments),
            dominant_language=clean_result.dominant_language,
            subtitle_srt_source="cleaned_segments",
        )
        extraction_result = ExtractionResult(
            video_path=str(video_path),
            band=resolved_band,
            raw_segments=raw_segments,
            cleaned_segments=cleaned_segments,
            dominant_language=clean_result.dominant_language,
            removed_segments=clean_result.removed_segments,
            summary=summary,
            debug_frame_rows=debug_frame_rows,
        )
        write_extraction_outputs(extraction_result, output_root, self.config.output, tail_seconds)
        return extraction_result


def extract_batch(
    video_paths: list[str | Path],
    output_dir: str | Path | None = None,
    config: ExtractorConfig | None = None,
) -> list[ExtractionResult]:
    if not video_paths:
        return []

    with SubtitleExtractor(config) as extractor:
        band = extractor.detect_band(video_paths)
        output_root = _resolve_output_root(output_dir, extractor.config)
        write_subtitle_band(output_root, band)
        return [extractor.extract(video_path, band, output_root) for video_path in video_paths]


def extract_subtitles(
    video_paths: list[str | Path],
    output_dir: str | Path | None = None,
    config: ExtractorConfig | None = None,
) -> list[ExtractionResult]:
    return extract_batch(video_paths, output_dir=output_dir, config=config)
