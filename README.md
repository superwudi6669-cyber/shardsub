# shardsub

`shardsub` 是一个用于视频硬字幕提取的 Python 库。

它围绕一条实用的 OCR 流水线组织实现，主要包括：

- 字幕带检测
- 按帧采样 OCR
- 字幕分段构建
- 本地规则清洗
- 结构化结果输出

当前项目主要面向本地 Windows / Conda / PaddleOCR 环境使用，但核心实现已经整理成可复用的包结构。

## 功能特性

- 支持单个视频提取
- 支持批量视频提取
- 批量模式下共享一次字幕带检测结果
- 包内自带本地模型目录 `shardsub/model`
- 支持可选图像预处理，默认关闭
- 输出 SRT、JSON、CSV 等结构化结果
- 核心包本身不依赖 CLI

## 目录结构

```text
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
  model/
    det/
    rec/
```

## 运行依赖

建议环境：

- Python 3.11
- `paddleocr`
- `paddlex`
- `opencv-python`
- 与本机设备匹配的 PaddlePaddle 运行时

如果使用 GPU，请先安装与当前 CUDA 环境匹配的 PaddlePaddle GPU 版本。

## 模型目录

默认情况下，`shardsub` 使用包内模型目录：

- `shardsub/model/det`
- `shardsub/model/rec`

默认模型名：

- `PP-OCRv5_server_det`
- `PP-OCRv5_server_rec`

如果模型目录里缺少必须文件，`OCREngine` 会自动从 PaddleX 提供的官方模型缓存路径复制到本地目录。

## 快速开始

### 1. 批量提取

```python
from shardsub import ExtractorConfig, extract_subtitles

config = ExtractorConfig()

results = extract_subtitles(
    [
        r"E:\project\SHORT_drama\jianyji\v1\ocr\input\1.mp4",
        r"E:\project\SHORT_drama\en_to_ch\input\video\4\2.mp4",
        r"C:\Users\admin\Downloads\111.mp4",
    ],
    output_dir=r"E:\project\SHORT_drama\jianyji\v1\ocr\output\demo_batch",
    config=config,
)
```

### 2. 单视频提取

```python
from shardsub import ExtractorConfig, SubtitleExtractor

config = ExtractorConfig()

with SubtitleExtractor(config) as extractor:
    result = extractor.extract(
        r"E:\project\SHORT_drama\jianyji\v1\ocr\input\1.mp4",
        output_dir=r"E:\project\SHORT_drama\jianyji\v1\ocr\output\demo_single",
    )
```

### 3. 多视频复用同一条字幕带

```python
from shardsub import ExtractorConfig, SubtitleExtractor

video_paths = [
    r"E:\project\SHORT_drama\jianyji\v1\ocr\input\1.mp4",
    r"E:\project\SHORT_drama\en_to_ch\input\video\4\2.mp4",
]

config = ExtractorConfig()

with SubtitleExtractor(config) as extractor:
    band = extractor.detect_band(video_paths)
    result_1 = extractor.extract(video_paths[0], band=band)
    result_2 = extractor.extract(video_paths[1], band=band)
```

## 可选图像预处理

图像预处理逻辑放在 `image_ops.py` 中。

默认不启用任何预处理。只有你明确设置 `config.image.mode` 时才会启用。

```python
from shardsub import ExtractorConfig

config = ExtractorConfig()
config.image.mode = "white_on_black"
```

当前支持的模式：

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

## 配置对象

公开配置类型包括：

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

## 返回对象

主要返回类型包括：

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

## 输出文件

当传入 `output_dir` 时，流水线会写出：

- 批量根目录下的 `subtitle_band.json`
- 每个视频自己的 `subtitles.srt`
- 每个视频自己的 `raw_segments.json`
- 每个视频自己的 `llm_blocks.json`
- 每个视频自己的 `summary.json`
- 可选的 `raw_frames.csv`
- 可选的裁剪调试图片

## 处理流程

```text
视频
  -> 字幕带检测
  -> 抽样帧 OCR
  -> 帧级 OCR 解析
  -> 字幕块构建
  -> 本地清洗
  -> 输出 SRT / JSON / CSV
```

## 说明

- 这是一个以库为中心的实现，核心包本身不依赖 CLI。
- 批量模式会先检测一次字幕带，然后把结果复用到整批视频。
- 当前清洗逻辑会保留稳定的 `block_id`，并单独记录被删除的字幕块。
- 默认写出的 `subtitles.srt` 来自 `cleaned_segments`。

## 对外 API

```python
from shardsub import (
    ExtractorConfig,
    SubtitleExtractor,
    extract_batch,
    extract_subtitles,
)
```

## 内部说明文档

之前那份偏内部实现说明的文档已经保留为：

`README.internal.md`
