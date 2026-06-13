from .config import (
    BandDetectConfig,
    CleanConfig,
    ExtractConfig,
    ExtractorConfig,
    ImagePreprocessConfig,
    ModelConfig,
    OutputConfig,
)
from .types import (
    CleanResult,
    ExtractionResult,
    ExtractionSummary,
    FrameOCRResult,
    RawSegment,
    RemovedSegment,
    SubtitleBand,
    VideoInfo,
)


class SubtitleExtractor:
    def __new__(cls, *args, **kwargs):
        from .pipeline import SubtitleExtractor as CoreSubtitleExtractor

        return CoreSubtitleExtractor(*args, **kwargs)


def extract_batch(*args, **kwargs):
    from .pipeline import extract_batch as core_extract_batch

    return core_extract_batch(*args, **kwargs)


def extract_subtitles(*args, **kwargs):
    from .pipeline import extract_subtitles as core_extract_subtitles

    return core_extract_subtitles(*args, **kwargs)

__all__ = [
    "BandDetectConfig",
    "CleanResult",
    "CleanConfig",
    "ExtractConfig",
    "ExtractorConfig",
    "ExtractionResult",
    "ExtractionSummary",
    "FrameOCRResult",
    "ImagePreprocessConfig",
    "ModelConfig",
    "OutputConfig",
    "RawSegment",
    "RemovedSegment",
    "SubtitleBand",
    "SubtitleExtractor",
    "VideoInfo",
    "extract_batch",
    "extract_subtitles",
]
