# VerseViva 声声不息

**VerseViva 是一个 AI 外语歌曲演唱教练。**

它不只告诉用户歌词是什么意思、单词怎么读，而是帮助用户理解原唱如何把语言放进旋律，并通过逐句反馈真正唱出来。

> 听懂每一句，唱活每一首。

## 核心体验

```text
选择一首英文歌
→ 看懂原唱的连读、重音、弱读与乐句节奏
→ 唱一句
→ 定位具体语言差异
→ 单句重练
→ 用同一指标验证改善
→ 记住长期弱点
```

示例：

```text
I wanna‿be WITH‿YOU toNIGHT
       连读      连读       重音
```

如果用户在 `with you` 之间出现明显停顿，VerseViva 会定位这两个词、解释为什么听起来像逐词朗读，并让用户立即重练这一句。

## 差异化

```text
K 歌产品：你唱得准不准？
歌词产品：这句是什么意思、怎么念？
VerseViva：原唱怎样把这句话唱进旋律，你实际唱成了什么，下一遍怎么改？
```

音准、节奏和时间对齐仍然是重要的底层证据，但不再是产品的主要卖点。

## 当前状态

项目继承了 VocalCompass 阶段已经验证的音频底座：

- Demucs `htdemucs` 人声分离
- Basic Pitch Note Event 与连续 Pitch
- WhisperX 句级、词级歌词对齐
- 上传、任务状态、错误持久化与 Song Profile API
- Pitch 清洗、静音过滤、局部八度修正与前端降采样
- Difference Engine v0
- 真实音频全链路验证

接下来按新的 VerseViva 计划优先开发：

- Song Language Profile
- 英文 G2P / 音节与语言提示
- `linking_gap`、重音和乐句时序检测
- 用户演唱对齐
- 单句重练与前后比较
- 基于事实的 AI Coach
- 用户语言演唱弱点 Memory

完整产品上下文与十天计划见 [AGENTS.md](./AGENTS.md)。

## 技术栈

- 前端：React、TypeScript、Vite、Web Audio API
- 后端：Python 3.11+、FastAPI
- 数据：SQLite（Demo 阶段）
- 音频：Demucs、Basic Pitch、WhisperX

模型运行在 Linux 后端或 WSL2 开发环境；手机只运行 H5，并通过 HTTPS 调用 API。

## 快速启动

### 后端

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn server.main:app --reload
```

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/v1/health

### 前端

```powershell
Set-Location web
npm install
npm run dev
```

前端地址：http://localhost:5173

## 当前 API

上传并分析歌曲：

```text
POST /api/v1/songs/analyze
```

查询任务状态：

```text
GET /api/v1/songs/jobs/{job_id}
```

查询 Song Profile：

```text
GET /api/v1/songs/{song_id}
```

当前上传接口可以接收歌词文本，但 Pipeline 仍以 WhisperX ASR 为主；准确歌词校正和 Song Language Profile 将按新计划实现。

## 开发检查

```powershell
pytest
ruff check server tests
```
