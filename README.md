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

当前是 Demo 初始框架阶段：

- 后端基础 API 已完成
- 音频上传接口已完成
- Song Profile 和诊断数据模型已建立
- 前端 Vite 页面骨架已建立
- Demucs、Pitch 模型和 WhisperX 尚未接入

## 技术栈

- 前端：React、TypeScript、Vite
- 后端：Python、FastAPI
- 数据存储：Demo 阶段使用 SQLite
- 音频分析：计划接入 Demucs、Pitch 模型和 WhisperX

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

当前接口会保存音频并返回一个排队中的分析任务。后续音频分析模块会继续生成 Song Profile。

## 开发检查

在项目根目录运行：

```powershell
pytest
ruff check server tests
```


