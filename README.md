# VocalCompass

VocalCompass 是一个 AI 个性化跟唱教练 Demo。它不只给用户一个分数，而是比较原唱和用户的演唱差异，指出具体问题，给出可执行的建议，并支持单句重练和长期弱点记忆。

## 项目结构

```text
server/   FastAPI 后端、音频分析管线、差异诊断和用户记忆
web/      React + TypeScript + Vite 移动端网页
tests/    后端测试
```

## 为什么使用 SQLite

当前目标是十天左右完成一个稳定、可演示的产品闭环，而不是立即部署成多人在线生产系统。SQLite 适合这个阶段，原因是：

- 不需要额外启动 PostgreSQL 或 MySQL 服务，安装和演示成本低。
- 一个数据库文件就能保存歌曲分析结果、练习记录、问题记录和用户弱点。
- Python 标准库和 FastAPI 生态支持成熟，开发速度快。
- 本地 Demo、单用户或少量并发时性能足够。
- 后续可以通过 Repository 层迁移到 PostgreSQL，不需要改变前端 API 和核心业务模型。

SQLite 不是最终生产数据库方案。如果未来需要多用户、高并发、云端部署、复杂检索或多实例运行，应迁移到 PostgreSQL。当前阶段优先保证音频分析和“发现问题 → 单句重练 → 看见改善”的产品闭环。

## 后端启动

需要 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn server.main:app --reload
```

启动后访问：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/v1/health`

运行测试和静态检查：

```powershell
pytest
ruff check server tests
```

## 当前后端接口

### 健康检查

```text
GET /api/v1/health
```

### 上传歌曲并创建分析任务

```text
POST /api/v1/songs/analyze
Content-Type: multipart/form-data
```

表单字段：

- `audio`：MP3、WAV 或 FLAC 文件
- `title`：可选，歌曲名称
- `lyrics`：可选，歌词文本

当前接口会校验并持久化音频，返回 `queued` 状态的分析任务。下一步由音频 Worker 接入人声分离、Pitch 提取、歌词对齐和 Song Profile 生成。

## 前端启动

需要 Node.js 20 或更高版本。

```powershell
Set-Location web
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，并将 `/api` 请求代理到后端 `http://127.0.0.1:8000`。

## 音频模型接入原则

基础依赖没有强制安装 Demucs、WhisperX 或具体 Pitch 模型。这些模型可能需要较大的下载量、系统音频库或 GPU 环境。模型应该通过 `server/pipelines/contracts.py` 中的接口接入：

```text
歌曲音频
→ 人声分离
→ 原唱 Pitch / Note
→ 歌词和词级时间对齐
→ 英文连读、重音等演唱提示
→ Song Profile
```

这样可以替换模型而不改变 API 和前端业务流程。


