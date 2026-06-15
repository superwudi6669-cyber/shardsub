# shardsub 内部说明

这份文档面向仓库维护者，说明当前库的职责拆分、调用方式和默认行为。

## 1. 当前定位

`shardsub` 已经收口成纯库结构：

- 不保留 CLI
- 业务入口在 `src/shardsub/pipeline.py`
- 对外兼容导出在 `src/shardsub/__init__.py`
- 模型不再随包分发，运行时按需准备到用户缓存目录

默认流程不改核心算法，只做结构拆分和可发布化整理。

## 2. 目录结构

```text
shardsub/
  src/
    shardsub/
      __init__.py
      band_detector.py
      cleaner.py
      config.py
      image_ops.py
      ocr_engine.py
      ocr_parser.py
      pipeline.py
      segment_builder.py
      similarity.py
      types.py
      video_io.py
      writer.py
  tests/
  README.md
  README.internal.md
  pyproject.toml
```

## 3. 各文件职责

### `src/shardsub/__init__.py`

对外 re-export：

- 配置类
- 数据类型
- `SubtitleExtractor`
- `extract_batch()`
- `extract_subtitles()`

外部调用优先从这里 import。

### `src/shardsub/config.py`

集中定义全部 dataclass 配置：

- `ModelConfig`
- `BandDetectConfig`
- `ExtractConfig`
- `ImagePreprocessConfig`
- `CleanConfig`
- `OutputConfig`
- `ExtractorConfig`

关键默认值：

- `model.device = "cpu"`
- `model.model_dir = <user-cache>/shardsub/models`
- `band_detect.band_every_n_frames = 5`
- `extract.ocr_every_n_frames = 3`

### `src/shardsub/types.py`

定义跨模块数据契约：

- `VideoInfo`
- `SubtitleBand`
- `FrameOCRResult`
- `RawSegment`
- `RemovedSegment`
- `CleanResult`
- `ExtractionSummary`
- `ExtractionResult`

### `src/shardsub/ocr_engine.py`

OCR 引擎层，负责：

- 懒加载 `PaddleOCR`
- 调用 PaddleX 官方模型路径
- 将 `det/rec` 模型复制到用户缓存目录
- 提供统一 `predict(image)` 入口
- 释放 OCR 资源

注意：

- 当前只准备 `PP-OCRv5_server_det` 和 `PP-OCRv5_server_rec`
- `use_doc_orientation_classify / use_doc_unwarping / use_textline_orientation` 都关闭
- 如果 `predict()` 没有结果，会返回空 dict，避免上层直接 `IndexError`

### `src/shardsub/video_io.py`

视频 IO 层：

- `get_video_info()`
- `iter_sampled_frames()`

行为：

- 使用 `grab()` 跳帧
- 只在命中采样帧时 `retrieve()`
- 负责释放视频句柄

### `src/shardsub/image_ops.py`

图像区域与可选预处理层：

- `crop_search_region()`
- `crop_band_region()`
- `apply_image_preprocess()`

默认不做任何增强，只有显式配置 `config.image.mode` 才启用。

### `src/shardsub/ocr_parser.py`

把 PaddleOCR 原始输出解析成统一帧级对象：

- 提取 `rec_polys / rec_texts / rec_scores`
- 过滤空文本
- 聚合成 `FrameOCRResult`

### `src/shardsub/similarity.py`

文本相似度层：

- 文本归一化
- `SequenceMatcher` 相似度比较

供 `segment_builder.py` 使用。

### `src/shardsub/band_detector.py`

字幕带检测层。

当前逻辑：

1. 只使用前 `band_detect_videos` 个视频做检测
2. 每个检测视频按 `band_every_n_frames` 采样，默认每隔 5 帧检测一帧
3. 每帧只裁剪 `60% ~ 90%` 的搜索区
4. 对搜索区做 OCR
5. 过滤不像字幕的框：
   - 文本长度不足
   - 分数过低
   - 框太矮
   - 中心偏移过大
6. 将候选框投影到 y 方向 coverage
7. 用固定高度滑窗选 coverage 最高的字幕带
8. 上下追加 padding
9. 无有效框时 fallback 到默认搜索区

这里不是做逐帧框跟踪，而是统计哪一条横向带最稳定地出现字幕。

### `src/shardsub/segment_builder.py`

逐帧结果合并层。

职责：

- 低分帧忽略
- 空帧 gap 容忍
- 相似文本延长同一个字幕块
- 更高分文本替换块代表文本
- 关闭块时计算 `avg_score / sample_count`

### `src/shardsub/cleaner.py`

字幕清洗层，处理 `RawSegment` 列表。

当前规则重点：

- 删除空文本、纯数字、纯符号
- 删除单字母噪声，但保留 `I`
- 保留高分单字中文
- 先做基础去噪，再按整批主语言做跨语种删除
- 英文 token 清理保持保守，只删明显乱码 token
- 保留 `removed_segments`，并附带 `reason_detail`
- 保持原 `block_id`

兼容入口：

- `clean_segments()`
- `clean_srt_file()`

### `src/shardsub/writer.py`

输出层，只负责写文件，不参与业务判断。

当前输出：

- `subtitle_band.json`
- `subtitles.srt`
- `raw_segments.json`
- `llm_blocks.json`
- `summary.json`
- 可选 `raw_frames.csv`
- 可选裁剪调试图

### `src/shardsub/pipeline.py`

总控层，也是最常用入口。

包含：

- `SubtitleExtractor`
- `extract_batch()`
- `extract_subtitles()`

职责：

- 初始化共享 `OCREngine`
- 执行一次字幕带检测
- 单视频提取
- 统一落盘
- 统一关闭资源

## 4. 推荐调用方式

### 4.1 批量调用

```python
from shardsub import ExtractorConfig, extract_subtitles

results = extract_subtitles(
    ["path/to/a.mp4", "path/to/b.mp4"],
    output_dir="output/demo",
    config=ExtractorConfig(),
)
```

### 4.2 类式调用

```python
from shardsub import ExtractorConfig, SubtitleExtractor

with SubtitleExtractor(ExtractorConfig()) as extractor:
    band = extractor.detect_band(["path/to/a.mp4", "path/to/b.mp4"])
    result = extractor.extract("path/to/a.mp4", band=band)
```

## 5. 模型准备策略

当前不再把 `model/` 目录作为包内容发布。

运行时行为：

1. `OCREngine.instance` 首次访问时触发 `_prepare_models()`
2. 通过 `official_models.get_model_path(model_name)` 获取 PaddleX 官方模型缓存路径
3. 将官方缓存复制到 `config.model.model_dir / det` 与 `... / rec`
4. 用复制后的路径初始化 `PaddleOCR`

因此发布包时只带代码，不带数百 MB 的模型文件。

## 6. 现在的发布约束

为了能上公共包仓库，当前已经按这些方向收口：

- 使用 `src/` 布局
- 不打包模型文件
- 默认设备改为 CPU
- 依赖改为兼容区间，不再全锁死
- README 不再写本机绝对路径

仍需仓库拥有者自行确认的事项：

- 选择一个真实许可证并补 `LICENSE`

## 7. 测试范围

当前测试放在 `tests/`，优先覆盖：

- `cleaner.py`
- `segment_builder.py`

这两层最依赖规则稳定性，重构时最容易出现细小行为漂移。
