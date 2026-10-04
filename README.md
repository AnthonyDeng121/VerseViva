# VerseViva 声声不息

**VerseViva 是一个 AI 外语歌曲演唱教练。**

它不只告诉用户歌词是什么意思、单词怎么读，而是帮助用户看见原唱在真实演唱中具体省略、合并或改变了哪些声音，并通过逐句反馈真正唱出来。

> 听懂每一句，唱活每一首。

产品与实现边界以 [AGENTS.md](./AGENTS.md) 为准。主歌词界面只显示 `×`、`‿`、合并桥等字符标记，中文解释与发音动作放在句子展开详情中。音高、节奏和时间对齐是定位与验证音变的底层证据，不是产品的主要卖点。

## 环境要求

当前已验证开发环境是 Windows 11 + WSL2 Ubuntu：

- WSL Python 3.11（后端和模型工具）
- Node.js 22 / npm 10（前端）
- ffmpeg / ffprobe 4.4+

仓库可以位于 Windows 盘，但所有 Python 虚拟环境都应从 WSL 创建。不要复制旧项目的虚拟环境；虚拟环境中的解释器路径不可迁移。

## 首次安装

在 PowerShell 中进入项目，再打开 WSL：

```powershell
Set-Location 'D:\0Desktop2\项目\VerseViva'
wsl -d Ubuntu
```

以下命令在 WSL 中执行：

```bash
cd '/mnt/d/0Desktop2/项目/VerseViva'

python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e '.[dev]'

python3.11 -m venv .venv-demucs
.venv-demucs/bin/python -m pip install -r requirements-demucs.txt

python3.11 -m venv .venv-pitch
.venv-pitch/bin/python -m pip install -r requirements-basic-pitch.txt

python3.11 -m venv .venv-whisperx
.venv-whisperx/bin/python -m pip install -r requirements-whisperx.txt

cp -n .env.example .env

cd web
npm install
```

三个模型工具使用隔离环境，因为各自的 NumPy、TensorFlow 和 Torch 约束可能冲突。模型权重使用工具自身的公共缓存，不放入 Git。

## 配置

应用只读取 `VERSEVIVA_*` 环境变量。默认配置把 data、jobs、songs 和模型输出都放在仓库的 `./data` 下；模型可执行文件也使用仓库相对路径。

`.env` 是本地文件，不会提交。修改 `.env.example` 时不要加入密钥、本机绝对路径或用户音频路径。

## 启动

后端（WSL，仓库根目录）：

```bash
.venv/bin/uvicorn server.main:app --reload
```

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/v1/health

前端（另一个 WSL 终端）：

```bash
cd web
npm run dev
```

前端地址为 http://localhost:5173。Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 开发检查

```bash
# 仓库根目录
.venv/bin/pytest
.venv/bin/ruff check server tests

# web/
npm run build
npm run lint
```

模型工具轻量验证：

```bash
.venv-demucs/bin/demucs --help
.venv-pitch/bin/basic-pitch --help
.venv-whisperx/bin/whisperx --help
ffmpeg -version
ffprobe -version
```

不要仅为环境验证重复运行完整音频链路。Hero Song 应优先读取 `data/` 中的缓存产物。

## 当前 API

```text
POST /api/v1/songs/analyze
GET  /api/v1/songs/jobs/{job_id}
GET  /api/v1/songs/{song_id}
```

## 数据与版本控制

`data/`、`.env`、虚拟环境、`web/node_modules/`、前端构建产物、模型权重和用户音频均被忽略，不得提交。现有 `data/` 使用仓库内相对布局，历史审计字段可以保留，但运行时配置不得访问旧项目路径。

## 从 VocalCompass 迁移

VerseViva 复用了 VocalCompass 阶段验证过的 Demucs、Basic Pitch、WhisperX、Song Profile 和 Difference Engine 底座，但已经是独立项目。旧目录只可作为只读迁移来源；日常启动、测试、模型命令与数据读取均不得依赖旧目录，也不得向旧仓库远端推送。
