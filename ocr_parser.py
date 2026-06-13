from __future__ import annotations

from .types import FrameOCRResult, VideoInfo


def extract_detection_entries(result) -> list[tuple[object, str, float]]:
    polys = result.get("rec_polys", []) or []
    texts = result.get("rec_texts", []) or []
    scores = result.get("rec_scores", []) or []
    entries = []
    for poly, text, score in zip(polys, texts, scores):
        text = str(text).strip() if text is not None else ""
        entries.append((poly, text, float(score)))
    return entries


def parse_frame_ocr_result(result, frame_index: int, time_sec: float, video_info: VideoInfo) -> FrameOCRResult:
    texts: list[str] = []
    scores: list[float] = []
    polys: list[object] = []
    for poly, text, score in extract_detection_entries(result):
        if text:
            texts.append(text)
            scores.append(score)
            polys.append(poly)
    merged = " ".join(texts)
    avg_score = sum(scores) / len(scores) if scores else 0.0
    return FrameOCRResult(
        frame_index=frame_index,
        time_sec=time_sec,
        text=merged,
        avg_score=avg_score,
        texts=texts,
        scores=scores,
        polys=polys,
        video_info=video_info,
    )
