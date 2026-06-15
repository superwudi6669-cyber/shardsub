# shardsub

`shardsub` 是一个基于 PaddleOCR 的硬字幕提取库，目标是把视频字幕提取流程整理成可复用的 Python 包，而不是一次性的脚本集合。

它当前提供这几层能力：

- 字幕区域检测
- 按固定间隔抽帧 OCR
- 帧级结果合并为字幕块
- 本地规则清洗
- SRT / JSON / CSV 输出

## 安装

建议先安装与你机器匹配的 PaddlePaddle 运行时：

- CPU 环境：安装 `paddlepaddle`
- GPU 环境：按你的 CUDA 版本安装对应的 `paddlepaddle-gpu`

然后安装本项目：

```bash
pip install .
```

或直接从源码开发安装：

```bash
pip install -e .
```

当前核心依赖：

- `paddleocr`
- `paddlex`
- `opencv-contrib-python`
- `numpy`
- `platformdirs`

## 模型策略

`shardsub` 不再把 OCR 模型文件打进包里。

首次运行时，`OCREngine` 会通过 PaddleX 官方模型路径准备检测和识别模型，并复制到用户缓存目录：

```text
<user-cache>/shardsub/models/
  det/
  rec/
```

默认模型：

- `PP-OCRv5_server_det`
- `PP-OCRv5_server_rec`

默认设备是 `cpu`。如果你要用 GPU，请显式设置：

```python
from shardsub import ExtractorConfig

config = ExtractorConfig()
config.model.device = "gpu:0"
```

## 快速开始

### 批量处理

```python
from shardsub import ExtractorConfig, extract_subtitles

config = ExtractorConfig()

results = extract_subtitles(
    [
        "path/to/video_1.mp4",
        "path/to/video_2.mp4",
    ],
    output_dir="output/demo_batch",
    config=config,
)
```

### 单视频处理

```python
from shardsub import ExtractorConfig, SubtitleExtractor

config = ExtractorConfig()

with SubtitleExtractor(config) as extractor:
    result = extractor.extract(
        "path/to/video.mp4",
        output_dir="output/demo_single",
    )
```

### 先检测字幕带，再复用到多个视频

```python
from shardsub import ExtractorConfig, SubtitleExtractor

video_paths = [
    "path/to/video_1.mp4",
    "path/to/video_2.mp4",
]

config = ExtractorConfig()

with SubtitleExtractor(config) as extractor:
    band = extractor.detect_band(video_paths)
    result_1 = extractor.extract(video_paths[0], band=band)
    result_2 = extractor.extract(video_paths[1], band=band)
```

## 可选图像预处理

预处理逻辑集中在 `image_ops.py`，默认全部关闭。只有明确设置 `config.image.mode` 时才会启用。

```python
from shardsub import ExtractorConfig

config = ExtractorConfig()
config.image.mode = "white_on_black"
```

当前支持：

- `origin`
- `gray`
- `gray_clahe`
- `white_mask`
- `white_on_black`
- `white_on_black_inv`
- `masked_color`
- `gray_soft_mask`
- `gray_bg_dim`
- `outline_tophat`

## 主要配置

对外公开的配置对象：

- `ModelConfig`
- `BandDetectConfig`
- `ExtractConfig`
- `ImagePreprocessConfig`
- `CleanConfig`
- `OutputConfig`
- `ExtractorConfig`

示例：

```python
from shardsub import ExtractorConfig

config = ExtractorConfig()
config.extract.ocr_every_n_frames = 3
config.output.save_frame_csv = True
config.output.save_crop_images = True
config.clean.keep_single_cjk_score = 0.80
```

## 输出内容

传入 `output_dir` 后，会输出：

- `subtitle_band.json`
- `subtitles.srt`
- `raw_segments.json`
- `llm_blocks.json`
- `summary.json`
- 可选 `raw_frames.csv`
- 可选调试裁剪图

当前 `subtitles.srt` 来自 `cleaned_segments`，`summary.subtitle_srt_source` 会明确标记这一点。

## 返回对象

主要返回类型：

- `SubtitleBand`
- `RawSegment`
- `CleanResult`
- `ExtractionSummary`
- `ExtractionResult`

其中 `ExtractionResult` 主要包含：

- `video_path`
- `band`
- `raw_segments`
- `cleaned_segments`
- `dominant_language`
- `removed_segments`
- `summary`
- `debug_frame_rows`

## 项目结构

```text
shardsub/
  src/
    shardsub/
      __init__.py
      config.py
      types.py
      ocr_engine.py
      video_io.py
      image_ops.py
      ocr_parser.py
      similarity.py
      band_detector.py
      segment_builder.py
      cleaner.py
      writer.py
      pipeline.py
  tests/
```

## 说明

- 这是一个以库为中心的实现，不保留 CLI。
- 批量模式会先检测一次字幕带，再复用到整批视频。
- `block_id` 在清洗后保持稳定，不会重新编号。
- 项目内部说明文档见 `README.internal.md`。

## 公开 API

```python
from shardsub import (
    ExtractorConfig,
    SubtitleExtractor,
    extract_batch,
    extract_subtitles,
)
```
