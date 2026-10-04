# VocalCompass

VocalCompass 是一个 AI 个性化跟唱教练。

它不只是告诉你唱了多少分，而是帮助你完成完整的练习闭环：

```text
唱歌
  ↓
发现问题
  ↓
理解问题
  ↓
单句重练
  ↓
看到改善
  ↓
记住长期弱点
```

## 产品能力

- 上传一首歌曲，分析原唱的人声、音高、旋律和歌词时间轴
- 跟唱时查看原唱与用户的音高差异
- 识别偏高、偏低、抢拍、拖拍、长音提前结束等问题
- 用容易理解的语言解释问题，并给出下一遍的练习建议
- 点击“练这一句”，完成听原唱、跟唱、分析、反馈的单句练习循环
- 记录长期反复出现的弱点，生成历史趋势和个性化练习方向
- 英文歌曲支持连读、重音、弱读和词间停顿提示

## 项目状态

当前已完成 Day 2 后端核心链路的真实验收，正在进入 Day 3「Reference Visualization」：

- 已接入 Demucs `htdemucs`，可生成原唱人声与伴奏分离结果
- 已接入 Basic Pitch，可生成 Note Event CSV、MIDI 和模型原始 NPZ
- 已接入 WhisperX，可生成句级、词级歌词与时间戳
- 已完成歌曲上传、任务状态查询、失败信息持久化和 Song Profile 查询 API
- 已通过真实音频跑通 `上传 → 分离人声 → 提取 Pitch → 对齐歌词 → 生成 Song Profile`
- Song Profile、PitchPoint、Note、Sentence、WordTiming 和诊断数据模型已建立
- 前端目前仍是 Vite 页面骨架，上传、任务进度和 Song Profile 页面尚待接入

Day 3 后端重点是将模型原始输出转换为可靠、轻量、可供前端绘制的参考数据：

1. 从 Basic Pitch 模型输出生成真实的连续 `PitchPoint[]`
2. 过滤静音、低置信度、极短音符和明显的八度误判，并适度平滑
3. 根据清洗后的有效数据计算音名、音域和句级 Pitch 摘要
4. 记录清洗前后统计，保留 Debug 可追溯性
5. 控制 Song Profile JSON 的数据量，避免把原始 NPZ 直接传给浏览器
6. 建立 Difference Engine v0 的纯函数接口和合成测试数据

## 技术栈

- 前端：React、TypeScript、Vite
- 后端：Python、FastAPI
- 数据存储：Demo 阶段使用 SQLite
- 音频分析：Demucs、Basic Pitch、WhisperX

当前模型 Pipeline 已在 WSL2 Ubuntu、Python 3.11、FFmpeg 和 CPU 推理环境下验证。手机端只运行 React H5，并通过 HTTPS 调用后端；手机不需要安装这些模型或 WSL。

## 快速启动

### 启动后端

需要 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn server.main:app --reload
```

后端启动后：

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/v1/health

### 启动前端

需要 Node.js 20 或更高版本。

```powershell
Set-Location web
npm install
npm run dev
```

前端地址：http://localhost:5173

前端会自动把 `/api` 请求转发到本地 FastAPI 后端。

## 上传歌曲接口

```text
POST /api/v1/songs/analyze
```

使用 `multipart/form-data` 上传：

- `audio`：MP3、WAV 或 FLAC 文件
- `title`：可选的歌曲名称
- `lyrics`：可选的歌词文本

接口会保存音频并返回一个排队中的分析任务。当自动分析配置开启时，后台会依次执行 Demucs、Basic Pitch、WhisperX，并最终生成 Song Profile。

当前版本虽然接收 `lyrics` 字段，但歌词 Pipeline 仍使用 WhisperX ASR 结果，Song Profile 的 `lyricsSource` 保持为 `asr`；用户歌词/LRC 校正流程尚未实现。

## 查询分析结果

查询任务状态：

```text
GET /api/v1/songs/jobs/{job_id}
```

任务完成后查询 Song Profile：

```text
GET /api/v1/songs/{song_id}
```

任务状态包含 `queued`、`processing`、`completed` 和 `failed`。处理中会进一步报告人声分离、Pitch 提取、歌词对齐和 Profile 构建等真实阶段。

## 开发检查

在项目根目录运行：

```powershell
pytest
ruff check server tests
```


