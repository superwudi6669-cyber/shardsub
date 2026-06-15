from __future__ import annotations

import shutil
from pathlib import Path

from paddleocr import PaddleOCR
from paddlex.inference.utils.official_models import official_models

from .config import ModelConfig


class OCREngine:
    def __init__(self, config: ModelConfig):
        self.config = config
        self._ocr: PaddleOCR | None = None

    def _prepare_models(self) -> None:
        for name, subdir in (
            (self.config.det_model_name, "det"),
            (self.config.rec_model_name, "rec"),
        ):
            dst = self.config.model_dir / subdir
            dst.mkdir(parents=True, exist_ok=True)
            if not (dst / "inference.yml").exists():
                src = Path(official_models.get_model_path(name))
                shutil.copytree(src, dst, dirs_exist_ok=True)

    @property
    def instance(self) -> PaddleOCR:
        if self._ocr is None:
            self._prepare_models()
            self._ocr = PaddleOCR(
                text_detection_model_name=self.config.det_model_name,
                text_detection_model_dir=str(self.config.model_dir / "det"),
                text_recognition_model_name=self.config.rec_model_name,
                text_recognition_model_dir=str(self.config.model_dir / "rec"),
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_rec_score_thresh=self.config.text_rec_score_thresh,
                device=self.config.device,
            )
        return self._ocr

    def predict(self, image):
        results = self.instance.predict(image)
        if not results:
            return {}
        return results[0] or {}

    def close(self) -> None:
        if self._ocr is not None:
            self._ocr.close()
            self._ocr = None
