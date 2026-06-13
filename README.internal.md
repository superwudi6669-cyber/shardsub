# shardsub

`shardsub` 是当前字幕提取逻辑的核心库层。

设计目标是把原来集中在一个长文件里的职责拆开：

- 配置单独管理
- 数据结构单独定义
- OCR 模型加载与推理单独管理
- 视频抽帧、区域检测、OCR 解析、字幕块构建、清洗、输出分别独立
- `pipeline.py` 只负责统筹调用

当前目录除了代码模块外，也包含包内模型目录 `shardsub/model/`。

当前推荐直接从这个包调用，不要再把业务逻辑写进 `subtitle_extractor.py`。

---

## 1. 推荐入口

最常用的两个入口：

1. 函数式批量调用

```python
from shardsub import extract_subtitles, ExtractorConfig

results = extract_subtitles(
    [
        r"E:\project\SHORT_drama\jianyji\v1\ocr\input\1.mp4",
        r"E:\project\SHORT_drama\en_to_ch\input\video\4\2.mp4",
    ],
    output_dir=r"E:\project\SHORT_drama\jianyji\v1\ocr\output\demo",
    config=ExtractorConfig(),
)
```

2. 类式调用，适合复用同一个 OCR 实例

```python
from shardsub import SubtitleExtractor, ExtractorConfig

video_paths = [
    r"E:\project\SHORT_drama\jianyji\v1\ocr\input\1.mp4",
    r"E:\project\SHORT_drama\en_to_ch\input\video\4\2.mp4",
]

with SubtitleExtractor(ExtractorConfig()) as extractor:
    band = extractor.detect_band(video_paths)
    result = extractor.extract(video_paths[0], band=band)
```

说明：

- `extract_subtitles()` / `extract_batch()`：整批视频统一先检测一次字幕带，再逐个提取
- `SubtitleExtractor.detect_band()`：只做字幕区域检测
- `SubtitleExtractor.extract()`：处理单个视频

---

## 2. 每个文件的作用

### `__init__.py`

包导出入口。

作用：

- 对外导出常用配置类
- 对外导出常用数据结构
- 对外导出 `SubtitleExtractor`、`extract_batch()`、`extract_subtitles()`

你平时如果不想记内部模块路径，直接从这里 import 就行。

---

### `config.py`

配置定义文件。

包含：

- `ModelConfig`
- `BandDetectConfig`
- `ExtractConfig`
- `ImagePreprocessConfig`
- `CleanConfig`
- `OutputConfig`
- `ExtractorConfig`

作用：

- 所有默认参数都集中在这里
- 业务层不要再散落硬编码参数
- `ModelConfig.model_dir` 默认指向包内目录 `shardsub/model`

推荐用法：

```python
from shardsub import ExtractorConfig

config = ExtractorConfig()
config.extract.ocr_every_n_frames = 5
config.image.mode = "white_on_black"
config.output.save_frame_csv = True
```

---

### `types.py`

核心数据结构定义。

包含：

- `VideoInfo`
- `SubtitleBand`
- `FrameOCRResult`
- `RawSegment`
- `ExtractionSummary`
- `ExtractionResult`

作用：

- 固定各层之间传递的数据字段
- 避免不同模块各自拼 dict，导致字段漂移

说明：

- `ExtractionResult.cleaned_segments` 是清洗后的字幕块
- `ExtractionResult.raw_segments` 是清洗前字幕块
- `ExtractionResult.dominant_language` 是整批 segment 的主语言判定结果
- `ExtractionResult.removed_segments` 记录被删除的 segment、原因和细节
- `ExtractionResult.segments` 是 `cleaned_segments` 的只读别名

---

### `ocr_engine.py`

OCR 模型管理层。

作用：

- 自动准备本地模型目录
- 按需懒加载 `PaddleOCR`
- 提供统一 `predict(image)` 调用入口
- 统一释放 OCR 资源

当前默认使用的模型目录：

- `shardsub/model/det`
- `shardsub/model/rec`

外部不要直接初始化 `PaddleOCR`，应该通过 `OCREngine` 或 `SubtitleExtractor` 间接使用。

调用方式：

```python
from shardsub.config import ModelConfig
from shardsub.ocr_engine import OCREngine

engine = OCREngine(ModelConfig())
result = engine.predict(image)
engine.close()
```

通常不建议业务代码直接调它，优先走 `pipeline.py`。

---

### `video_io.py`

视频读取与抽帧层。

包含：

- `get_video_info(video_path)`
- `iter_sampled_frames(video_path, every_n)`

作用：

- 读取视频基础信息
- 使用 `grab()` 跳帧，使用 `retrieve()` 只解码目标帧
- 统一负责视频句柄释放

返回内容：

- `frame_index`
- `time_sec`
- `frame`
- `VideoInfo`

---

### `image_ops.py`

图像裁剪层。

包含：

- `crop_search_region()`
- `crop_band_region()`
- `apply_image_preprocess()`

作用：

- 检测阶段裁剪搜索区域
- 正式 OCR 阶段裁剪字幕带区域
- 按配置做可选预处理

默认不启用任何预处理；只有明确传入 `config.image.mode` 才会启用。

当前支持的预处理模式：

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

---

### `ocr_parser.py`

OCR 结果解析层。

包含：

- `extract_detection_entries()`
- `parse_frame_ocr_result()`

作用：

- 从 PaddleOCR 原始结果中提取：
  - 文本框
  - 文本
  - 分数
- 把单帧结果整理成 `FrameOCRResult`

当前行为：

- 多段文本按空格拼接
- 计算平均分
- 保留 `texts / scores / polys`

---

### `similarity.py`

文本相似度判断层。

包含：

- `normalize_text()`
- `are_similar()`

作用：

- 去掉空白并转小写
- 用 `SequenceMatcher` 判断两段文本是否属于同一句字幕

这个模块只负责文本比较，不依赖 OCR、视频和输出逻辑。

---

### `band_detector.py`

字幕区域检测层。

包含：

- `detect_subtitle_band(video_paths, config, engine)`

作用：

- 从前 N 个视频中抽样帧
- 在 `60%~90%` 搜索区内找字幕候选框
- 过滤低质量文本框
- 按 y 方向累积 coverage
- 用滑窗找最佳字幕带
- 输出 `SubtitleBand`

这是批处理开始前最先跑的一步。

---

### `segment_builder.py`

字幕块状态机构建层。

包含：

- `SegmentBuilder`

作用：

- 把逐帧 OCR 结果合并成字幕块
- 处理 gap 容忍
- 处理低分帧忽略
- 处理相似文本延长
- 处理 block 关闭与 finalize

输入：

- 一帧一帧的 `FrameOCRResult`

输出：

- `list[RawSegment]`

---

### `cleaner.py`

字幕清洗层。

包含：

- `clean_segments(segments, config)`
- `clean_srt_file(srt_path)`

作用：

- 删除空文本
- 删除纯数字
- 删除纯符号、单字母噪声、低有效字符字幕
- 保留高分单个 CJK 字字幕
- 做整批主语言判定：`CN / EN / UNKNOWN`
- 按主语言执行跨语种 segment 删除
- 对英文 token 做保守噪声清理
- 保留 `removed_segments`，用于调参与排查误删
- 保持原始 `block_id`

返回值不是单纯的 `list[RawSegment]`，而是 `CleanResult`：

- `cleaned_segments`
- `dominant_language`
- `removed_segments`

这个模块不做 OCR；核心入口处理 `RawSegment` 列表，`clean_srt_file()` 只是兼容旧文件级调用。

---

### `writer.py`

输出层。

包含：

- `write_subtitle_band()`
- `write_extraction_outputs()`
- `save_debug_crop_image()`
- `resolve_video_output_dir()`

作用：

- 写 `subtitle_band.json`
- 写 `subtitles.srt`
- 写 `raw_segments.json`
- 写 `llm_blocks.json`
- 写 `summary.json`
- 写 debug `raw_frames.csv`
- 写 debug crop 图片

注意：

- 当前 `subtitles.srt` 仍然来自 `cleaned_segments`
- `summary.subtitle_srt_source` 会标明这个来源

---

### `pipeline.py`

统筹层，也是核心业务入口。

包含：

- `SubtitleExtractor`
- `extract_batch()`
- `extract_subtitles()`

作用：

- 管理共享 `OCREngine`
- 检测字幕带
- 处理单视频抽帧 / 裁剪 / OCR / 合并 / 清洗 / 输出
- 统一释放资源

这是你最应该直接调用的文件。

---

## 3. 模块调用关系

当前推荐依赖方向如下：

```text
pipeline
  -> band_detector
  -> ocr_engine
  -> video_io
  -> image_ops
  -> ocr_parser
  -> segment_builder
  -> cleaner
  -> writer

band_detector
  -> video_io
  -> image_ops
  -> ocr_engine
  -> ocr_parser

segment_builder
  -> similarity
```

约束：

- `writer.py` 不参与业务判断
- `cleaner.py` 不依赖 `cv2` / `PaddleOCR`
- `segment_builder.py` 不直接调用 OCR
- `band_detector.py` 不负责写文件

---

## 4. 常见使用方式

### 方式 A：整批视频直接提取

```python
from shardsub import extract_subtitles, ExtractorConfig

config = ExtractorConfig()
config.output.save_frame_csv = True
config.output.save_crop_images = True

results = extract_subtitles(
    [
        r"E:\project\SHORT_drama\jianyji\v1\ocr\input\1.mp4",
        r"E:\project\SHORT_drama\en_to_ch\input\video\4\2.mp4",
    ],
    output_dir=r"E:\project\SHORT_drama\jianyji\v1\ocr\output\demo",
    config=config,
)
```

适用场景：

- 想直接跑一批视频
- 希望自动统一检测字幕带
- 需要自动写输出文件

---

### 方式 B：先检测字幕带，再手动逐个视频处理

```python
from shardsub import SubtitleExtractor, ExtractorConfig

video_paths = [
    r"E:\project\SHORT_drama\jianyji\v1\ocr\input\1.mp4",
    r"E:\project\SHORT_drama\en_to_ch\input\video\4\2.mp4",
]

with SubtitleExtractor(ExtractorConfig()) as extractor:
    band = extractor.detect_band(video_paths)
    result1 = extractor.extract(video_paths[0], band=band)
    result2 = extractor.extract(video_paths[1], band=band)
```

适用场景：

- 想手动控制 band 复用
- 想拿到 `ExtractionResult` 做后续自定义处理
- 不一定每次都要写盘

---

### 方式 C：只做字幕带可视化或分析

```python
from shardsub import SubtitleExtractor, ExtractorConfig

with SubtitleExtractor(ExtractorConfig()) as extractor:
    band = extractor.detect_band([video_path])
    print(band.y_start_ratio, band.y_end_ratio)
```

适用场景：

- 给预览脚本叠框
- 单独分析波段检测效果

---

## 5. 返回结果应该怎么看

如果你调用的是：

```python
result = extractor.extract(video_path, band=band)
```

那核心数据看这几个字段：

- `result.raw_segments`
  - 原始字幕块，清洗前
- `result.cleaned_segments`
  - 清洗后字幕块
- `result.summary`
  - 统计信息
- `result.debug_frame_rows`
  - 只有开启 `save_frame_csv` 时才有内容

如果走的是顶层兼容封装 `subtitle_extractor.extract_subtitles()`，返回的是 `dict` 形式，字段基本对应：

- `raw_segments`
- `segments`（等于 cleaned segments）
- `summary`

---

## 6. 当前注意事项

1. `subtitle_extractor.py` 现在只是兼容薄封装，不应该继续往里加业务逻辑。
2. 后续如果要继续增强：
   - 图像增强优先加在 `image_ops.py`
   - 更复杂的文本清洗优先加在 `cleaner.py`
   - 不同 OCR profile 优先加在 `ocr_engine.py`
3. 当前输出语义仍保持第一阶段兼容：
   - `subtitles.srt` 来自 `cleaned_segments`
   - `raw_segments.json` 保留清洗前结果
4. 如果以后要补 `cleaned_segments.json` 或 `cleaned_subtitles.srt`，优先改 `writer.py`

---

## 7. 最短调用模板

如果你只是想记一个最短模板，就用这个：

```python
from shardsub import extract_subtitles

results = extract_subtitles(
    [r"E:\project\SHORT_drama\jianyji\v1\ocr\input\1.mp4"],
    output_dir=r"E:\project\SHORT_drama\jianyji\v1\ocr\output\demo",
)
```

如果你需要复用 OCR 实例，就用：

```python
from shardsub import SubtitleExtractor, ExtractorConfig

with SubtitleExtractor(ExtractorConfig()) as extractor:
    band = extractor.detect_band([video_path])
    result = extractor.extract(video_path, band=band)
```

---

## 8. 当前字幕区域检测逻辑

当前 `band_detector.py` 的检测逻辑是：

1. 只使用前 `N` 个视频做字幕带检测
   - 默认 `band_detect_videos = 2`
2. 对参与检测的每个视频，固定 **每隔 5 帧** 抽一帧
   - 配置项是 `config.band_detect.band_every_n_frames`
   - 当前默认值是 `5`
3. 每帧只裁剪画面高度 `60% ~ 90%` 的搜索区
4. 对搜索区执行 OCR
5. 读取 OCR 的 `rec_polys / rec_texts / rec_scores`
6. 过滤掉不像字幕的框：
   - 文本长度小于 `2`
   - 分数小于 `0.70`
   - 框高度小于 `5px`
   - 框中心偏离画面中心过多
7. 把保留下来的框投影到 y 方向 coverage
8. 用固定高度滑窗找 coverage 最高的字幕带
9. 对结果上下加 `15%` padding
10. 如果没有任何有效框，就 fallback 到 `60% ~ 90%`

需要注意：

- 当前检测层**不是**做逐帧框跟踪
- 它不判断“某个框在相邻帧怎么移动”
- 它判断的是“哪一条 y 方向横带，在所有检测帧里最稳定地出现字幕框”

如果以后要增强“框位置移动”的判断，优先改 `band_detector.py`，不要把这部分逻辑塞进 `pipeline.py`。

