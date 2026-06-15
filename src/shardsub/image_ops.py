from __future__ import annotations

import cv2
import numpy as np

from .config import BandDetectConfig, ImagePreprocessConfig
from .types import SubtitleBand, VideoInfo


def _ensure_bgr(image):
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image


def _normalize_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    normalized = str(mode).strip().lower()
    if normalized in {"", "none", "off", "disable", "disabled"}:
        return None
    if normalized in {"origin", "original", "raw"}:
        return "origin"
    return normalized


def _resize_if_needed(image, config: ImagePreprocessConfig):
    if config.scale == 1:
        return image
    return cv2.resize(
        image,
        None,
        fx=config.scale,
        fy=config.scale,
        interpolation=cv2.INTER_CUBIC,
    )


def _white_subtitle_mask(image, config: ImagePreprocessConfig):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower = np.array(config.white_hsv_lower, dtype=np.uint8)
    upper = np.array(config.white_hsv_upper, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (config.close_kernel_size, config.close_kernel_size),
    )
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def apply_image_preprocess(image, config: ImagePreprocessConfig | None = None):
    if config is None:
        return image

    mode = _normalize_mode(config.mode)
    if mode is None:
        return image

    image_up = _resize_if_needed(image, config)
    if mode == "origin":
        return image_up

    gray = cv2.cvtColor(image_up, cv2.COLOR_BGR2GRAY)
    if mode == "gray":
        return _ensure_bgr(gray)

    if mode == "gray_clahe":
        clahe = cv2.createCLAHE(
            clipLimit=config.clahe_clip_limit,
            tileGridSize=(config.clahe_tile_grid_size, config.clahe_tile_grid_size),
        )
        return _ensure_bgr(clahe.apply(gray))

    white_mask = _white_subtitle_mask(image_up, config)
    if mode == "white_mask":
        return _ensure_bgr(white_mask)

    if mode == "white_on_black":
        white_on_black = cv2.bitwise_and(gray, gray, mask=white_mask)
        white_on_black = cv2.normalize(white_on_black, None, 0, 255, cv2.NORM_MINMAX)
        return _ensure_bgr(white_on_black)

    if mode == "white_on_black_inv":
        white_on_black = cv2.bitwise_and(gray, gray, mask=white_mask)
        white_on_black = cv2.normalize(white_on_black, None, 0, 255, cv2.NORM_MINMAX)
        return _ensure_bgr(cv2.bitwise_not(white_on_black))

    if mode == "masked_color":
        return cv2.bitwise_and(image_up, image_up, mask=white_mask)

    if mode == "gray_soft_mask":
        dilate_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (config.soft_mask_kernel_size, config.soft_mask_kernel_size),
        )
        mask_dilated = cv2.dilate(white_mask, dilate_kernel)
        return _ensure_bgr(cv2.bitwise_and(gray, gray, mask=mask_dilated))

    if mode == "gray_bg_dim":
        dilate_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (config.soft_mask_kernel_size, config.soft_mask_kernel_size),
        )
        mask_dilated = cv2.dilate(white_mask, dilate_kernel)
        feather = cv2.GaussianBlur(mask_dilated, (0, 0), sigmaX=config.soft_mask_sigma_x).astype(np.float32) / 255.0
        dimmed = gray.astype(np.float32) * (0.2 + 0.8 * feather)
        return _ensure_bgr(np.clip(dimmed, 0, 255).astype(np.uint8))

    if mode == "outline_tophat":
        erode_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (config.outline_kernel_size, config.outline_kernel_size),
        )
        local_min = cv2.erode(gray, erode_kernel)
        outline_response = cv2.subtract(gray, local_min)
        return _ensure_bgr(cv2.normalize(outline_response, None, 0, 255, cv2.NORM_MINMAX))

    supported = [
        "origin",
        "gray",
        "gray_clahe",
        "white_mask",
        "white_on_black",
        "white_on_black_inv",
        "masked_color",
        "gray_soft_mask",
        "gray_bg_dim",
        "outline_tophat",
    ]
    raise ValueError(f"Unsupported preprocess mode: {config.mode!r}. Supported: {', '.join(supported)}")


def crop_search_region(
    frame,
    config: BandDetectConfig,
    video_info: VideoInfo,
    preprocess: ImagePreprocessConfig | None = None,
):
    y0 = int(video_info.height * config.band_search_y_start)
    y1 = int(video_info.height * config.band_search_y_end)
    crop = frame[y0:y1, :]
    return apply_image_preprocess(crop, preprocess), y0, y1


def crop_band_region(
    frame,
    band: SubtitleBand,
    video_info: VideoInfo,
    preprocess: ImagePreprocessConfig | None = None,
):
    y0 = int(video_info.height * band.y_start_ratio)
    y1 = int(video_info.height * band.y_end_ratio)
    crop = frame[y0:y1, :]
    return apply_image_preprocess(crop, preprocess), y0, y1
