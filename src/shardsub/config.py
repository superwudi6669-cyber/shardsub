from __future__ import annotations

from dataclasses import dataclass, field
import platformdirs
from pathlib import Path

DEFAULT_MODEL_CACHE_DIR = Path(platformdirs.user_cache_dir("shardsub", "shardsub")) / "models"


@dataclass
class ModelConfig:
    model_dir: Path = DEFAULT_MODEL_CACHE_DIR
    device: str = "cpu"
    det_model_name: str = "PP-OCRv5_server_det"
    rec_model_name: str = "PP-OCRv5_server_rec"
    text_rec_score_thresh: float = 0.30


@dataclass
class BandDetectConfig:
    band_search_y_start: float = 0.60
    band_search_y_end: float = 0.90
    band_height_ratio: float = 160 / 1280
    band_padding_ratio: float = 0.15
    band_detect_videos: int = 2
    band_every_n_frames: int = 5
    band_min_box_height_px: int = 5
    band_min_text_len: int = 2
    band_min_score: float = 0.70
    band_center_x_tolerance: float = 0.30
    band_profile_bins: int = 300


@dataclass
class ExtractConfig:
    ocr_every_n_frames: int = 3
    merge_similarity: float = 0.85
    max_gap_samples: int = 1
    min_frame_score: float = 0.60


@dataclass
class ImagePreprocessConfig:
    mode: str | None = None
    scale: float = 2.0
    clahe_clip_limit: float = 1.5
    clahe_tile_grid_size: int = 8
    white_hsv_lower: tuple[int, int, int] = (0, 0, 170)
    white_hsv_upper: tuple[int, int, int] = (180, 90, 255)
    close_kernel_size: int = 2
    soft_mask_kernel_size: int = 7
    soft_mask_sigma_x: float = 5.0
    outline_kernel_size: int = 5


@dataclass
class CleanConfig:
    min_language_effective_chars: int = 20
    dominant_language_min_ratio: float = 0.65
    clean_enable: bool = True
    min_effective_chars: int = 2
    keep_single_cjk_score: float = 0.80
    min_foreign_segment_english_chars: int = 4
    min_foreign_segment_chinese_chars: int = 2
    min_noise_token_length: int = 5
    safe_upper_tokens: set[str] = field(
        default_factory=lambda: {
            "AI",
            "APP",
            "CEO",
            "DNA",
            "FBI",
            "GPS",
            "HELP",
            "NO",
            "OK",
            "STOP",
            "TV",
            "USA",
            "US",
            "VIP",
        }
    )
    safe_mixed_tokens: set[str] = field(
        default_factory=lambda: {
            "AI",
            "App",
            "APP",
            "Boss",
            "CEO",
            "DNA",
            "FBI",
            "GPS",
            "I",
            "Jack",
            "OK",
            "TV",
            "USA",
            "VIP",
        }
    )


@dataclass
class OutputConfig:
    output_dir: Path | None = None
    save_frame_csv: bool = False
    save_crop_images: bool = False


@dataclass
class ExtractorConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    band_detect: BandDetectConfig = field(default_factory=BandDetectConfig)
    extract: ExtractConfig = field(default_factory=ExtractConfig)
    image: ImagePreprocessConfig = field(default_factory=ImagePreprocessConfig)
    clean: CleanConfig = field(default_factory=CleanConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
