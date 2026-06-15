from __future__ import annotations

from pathlib import Path

import numpy as np

from .config import BandDetectConfig
from .image_ops import crop_search_region
from .ocr_engine import OCREngine
from .ocr_parser import extract_detection_entries
from .types import SubtitleBand
from .video_io import iter_sampled_frames


def detect_subtitle_band(
    video_paths: list[str | Path],
    config: BandDetectConfig,
    engine: OCREngine,
) -> SubtitleBand:
    paths = [Path(path) for path in video_paths[: config.band_detect_videos]]
    search_span = config.band_search_y_end - config.band_search_y_start
    bins = config.band_profile_bins
    window_bins = max(1, round(bins * min(1.0, config.band_height_ratio / search_span)))
    coverage = np.zeros(bins, dtype=np.float32)
    total_boxes = 0
    total_samples = 0

    for video_path in paths:
        for _, _, frame, video_info in iter_sampled_frames(video_path, config.band_every_n_frames):
            total_samples += 1
            crop, _, _ = crop_search_region(frame, config, video_info)
            result = engine.predict(crop)

            for poly, text, score in extract_detection_entries(result):
                if len(text) < config.band_min_text_len or score < config.band_min_score:
                    continue
                arr = np.asarray(poly)
                if arr.size == 0:
                    continue
                y_min = float(arr[:, 1].min())
                y_max = float(arr[:, 1].max())
                if y_max - y_min < config.band_min_box_height_px:
                    continue
                if config.band_center_x_tolerance is not None:
                    center_x = float(arr[:, 0].mean())
                    if abs(center_x - video_info.width / 2) > config.band_center_x_tolerance * video_info.width:
                        continue

                total_boxes += 1
                crop_h = max(crop.shape[0], 1)
                bin_start = int(np.clip(np.floor(y_min / crop_h * bins), 0, bins - 1))
                bin_end = int(np.clip(np.ceil(y_max / crop_h * bins), bin_start + 1, bins))
                coverage[bin_start:bin_end] += 1

    if total_boxes == 0:
        return SubtitleBand(
            y_start_ratio=config.band_search_y_start,
            y_end_ratio=config.band_search_y_end,
            fallback_used=True,
            meta={"total_samples": total_samples, "total_boxes": 0, "videos": [str(path) for path in paths]},
        )

    scores = np.convolve(coverage, np.ones(window_bins, dtype=np.float32), mode="valid")
    best = int(np.argmax(scores))
    band_start = config.band_search_y_start + search_span * (best / bins)
    band_end = config.band_search_y_start + search_span * ((best + window_bins) / bins)
    padding = (band_end - band_start) * config.band_padding_ratio
    band_start = max(0.0, band_start - padding)
    band_end = min(1.0, band_end + padding)

    return SubtitleBand(
        y_start_ratio=round(band_start, 6),
        y_end_ratio=round(band_end, 6),
        fallback_used=False,
        meta={
            "total_samples": total_samples,
            "total_boxes": total_boxes,
            "window_score": float(scores[best]),
            "videos": [str(path) for path in paths],
        },
    )
