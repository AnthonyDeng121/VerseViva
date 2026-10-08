# VerseViva 声声不息

**VerseViva 是一个 AI 外语歌曲演唱与分轨练习教练。**

它帮助用户看见原唱在真实演唱中具体省略、合并或改变了哪些声音，也把一遍无法同时唱完的主唱、和声、回应与重叠句拆成可练习的 Vocal 层。用户可以分别录制，再同步叠成一段完整演唱。

> 听懂每一句，唱活每一首。

产品与实现边界以 [AGENTS.md](./AGENTS.md) 为准。主歌词界面只显示 `×`、`‿`、合并桥等字符标记，中文解释与发音动作放在句子展开详情中；重叠人声默认使用左右并列的主 Vocal / 次 Vocal 双轨歌词展示。双轨只是教学视图，底层允许多 Vocal Part、多 Take 叠录，且每条 Take 可独立调节前后偏移和音量。项目不提取或展示音高、音符、音域与音准评分。

当前产品闭环是：看懂发音处理 → 分清 Vocal 层次 → 逐句跟唱和诊断 → 分轨录制重叠人声 → 同步回放 → 记住真实改善。VerseViva 不承诺把任意混合人声自动分离成独立主唱与和声，也不做完整 DAW；Hero Song 的声部边界首先采用人工校对，自动模型结果必须标明为候选。

当前已接通的语言标注链路是：上传歌曲 → LRCLIB 自动查找歌词 → Demucs 人声分离 → WhisperX 词级对齐 → CMUdict/G2P 遍历全部相邻词边界 → Gemini 对候选逐项进行受限核查 → 程序映射为 `×`、`‿`、合并桥 → 点击标记查看中文证据与练习动作。文件名使用 `歌手 - 歌名.mp3` 时可自动推断查词条件，也可在页面补充歌手和歌名。手动歌词优先级最高；LRCLIB 查询失败、匹配不足或与 WhisperX 时间轴无法对上时，会回退到 ASR 歌词，不会让整个任务失败。

这是“任意英文歌曲的候选标注流程”，不是母语级自动音素裁判；弱证据不会进入歌词主界面，Hero Song 仍需人工校对。

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

python3.11 -m venv .venv-whisperx
.venv-whisperx/bin/python -m pip install -r requirements-whisperx.txt

cp -n .env.example .env

cd web
npm install
```

两个模型工具使用隔离环境，因为各自的 NumPy 和 Torch 约束可能冲突。模型权重使用工具自身的公共缓存，不放入 Git。

## 配置

应用只读取 `VERSEVIVA_*` 环境变量。默认配置把 data、jobs、songs 和模型输出都放在仓库的 `./data` 下；模型可执行文件也使用仓库相对路径。

`.env` 是本地文件，不会提交。修改 `.env.example` 时不要加入密钥、本机绝对路径或用户音频路径。

启用 Gemini 语言核查时，在本地 `.env` 设置：

```dotenv
VERSEVIVA_LANGUAGE_ANALYSIS_PROVIDER=gemini
VERSEVIVA_GEMINI_API_KEY=你的本地密钥
VERSEVIVA_GEMINI_MODEL=gemini-3.8-flash
```

默认 provider 是 `disabled`，因此没有密钥时仍可运行 Demucs、WhisperX 和 Profile 流程，但不会自动生成语言标记。密钥不得写入 `.env.example` 或提交到 Git。

LRCLIB 默认启用且不需要 API Key。可通过 `VERSEVIVA_LYRICS_PROVIDER=disabled` 关闭，或用 `VERSEVIVA_LRCLIB_MIN_MATCH_SCORE` 调整自动采用阈值。

分析任务支持断点恢复。Demucs、WhisperX、LRCLIB 和语言模型的完整产物会保存在对应 job 目录；失败后可在前端查看真实阶段与错误详情，并点击“从失败处重试”。重试会校验已有产物的存在性和非空完整性，只重新执行缺失或未成功的阶段。Gemini 的 `429` / `5xx` / 超时等短暂错误会先自动退避重试，仍失败才转为可手动恢复状态。

## 启动

后端（WSL，仓库根目录）：

```bash
.venv/bin/uvicorn server.main:app --reload
```

### Hero 部署资源包

三首人工校验 Hero 使用独立 ZIP 部署，不在比赛服务器上重新运行整条 Pipeline。
构建包：

```bash
.venv/bin/python scripts/hero_assets.py build
```

默认产物为 `artifacts/verseviva-hero-assets.zip`，包含三首 Hero 的 Profile、网页/模型用 MP3 与
可回退的 WAV 母文件，不包含密钥、SQLite、用户录音或历史 Job。部署到服务器数据卷前恢复：

```bash
.venv/bin/python scripts/hero_assets.py restore artifacts/verseviva-hero-assets.zip \
  --data-dir /app/data
```

恢复时会校验 Hero ID、路径和 SHA-256，防止不完整资源进入演示环境。

使用 Docker Compose 时，在首次启动前把资源直接恢复到命名数据卷：

```bash
docker compose run --rm \
  -v "$PWD/artifacts:/artifacts:ro" \
  app python scripts/hero_assets.py restore \
  /artifacts/verseviva-hero-assets.zip --data-dir /app/data
```

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/v1/health

前端（另一个 WSL 终端）：

```bash
cd web
npm run dev
```

前端地址为 http://localhost:5173。Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 手机公网预发布测试

比赛交付不依赖校园网 IP、同一 Wi-Fi、WSL 或开发者电脑上的 Vite 地址。当前开发阶段使用两层部署：

1. 预发布：在本机构建 H5，由 FastAPI 同源提供页面和 `/api`，再通过临时 HTTPS Tunnel 供手机跨网络测试。
2. 正式比赛：使用同一个 Docker 镜像部署到公网云服务器，绑定固定域名并保留持久数据卷。

先构建前端：

```powershell
cd D:\0Desktop2\项目\VerseViva\web
npm.cmd install
npm.cmd run build
```

然后从仓库根目录启动统一 Web 服务：

```powershell
cd D:\0Desktop2\项目\VerseViva
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

此时以下内容使用同一个 origin：

```text
/                     React H5
/api/v1/health        健康检查
/api/v1/songs/...     歌曲与 Profile API
/api/v1/takes/...     用户录音 Take API
```

不要再将 Vite 的 `5173` 地址作为比赛或跨网络交付地址。Vite 只用于日常热更新开发。

临时 Tunnel 只用于手机联调，地址会变化且依赖本机在线；比赛提交必须换为固定云服务器和域名。

Windows 上可用一个命令完成前端构建、统一服务启动和临时 Tunnel：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_public_preview.ps1
```

保持该窗口打开，并使用输出中的最新 `https://...trycloudflare.com` 地址。关闭窗口、按 Ctrl+C、电脑休眠或校园网断线后，临时地址都会失效；重新运行会生成新地址。脚本固定使用 HTTP/2，以绕开校园网常见的 QUIC/UDP 7844 限制。

## Docker 与正式域名

复制生产环境模板，但不要提交密钥：

```powershell
Copy-Item .env.production.example .env.production
```

构建并启动：

```powershell
docker compose up --build -d
```

正式部署时把 `SITE_ADDRESS` 改为实际域名，例如 `demo.example.com`，并将域名解析到云服务器公网 IP。Caddy 会作为统一入口将 H5、API 和音频请求转发给 FastAPI。

临时容器 Tunnel 可使用：

```powershell
docker compose -f compose.yaml -f compose.tunnel.yaml up --build
```

完整模型镜像包含 Demucs、WhisperX 和 ffmpeg，因此第一次构建时间和镜像体积仍然较大。Hero Song 应继续使用预缓存；临时上传应限制为短片段。

`VERSEVIVA_LANGUAGE_WORKER_URL` 与 `VERSEVIVA_LANGUAGE_WORKER_TOKEN` 已为后续独立 Gemini Worker 预留。当前版本尚未将 Gemini 请求改为远程 Worker；迁移时保持现有 LanguageObservation / VocalCueTiming Schema，不改变前端合同。

## 开发检查

```bash
# 仓库根目录
.venv/bin/pytest
.venv/bin/ruff check server tests

# web/
npm test
npm run build
npm run lint
```

模型工具轻量验证：

```bash
.venv-demucs/bin/demucs --help
.venv-whisperx/bin/whisperx --help
ffmpeg -version
ffprobe -version
```

不要仅为环境验证重复运行完整音频链路。Hero Song 应优先读取 `data/` 中的缓存产物。

## 当前 API

```text
POST /api/v1/songs/analyze
GET  /api/v1/songs/jobs/{job_id}
GET  /api/v1/songs/jobs/latest
POST /api/v1/songs/jobs/{job_id}/retry
GET  /api/v1/songs/{song_id}
GET  /api/v1/songs/{song_id}/audio/source
GET  /api/v1/songs/{song_id}/audio/vocals
GET  /api/v1/songs/{song_id}/audio/accompaniment

POST /api/v1/songs/{song_id}/takes
GET  /api/v1/songs/{song_id}/takes?session_id=...
GET  /api/v1/takes/{take_id}
PATCH /api/v1/takes/{take_id}
GET  /api/v1/takes/{take_id}/audio
POST /api/v1/takes/{take_id}/analyze

GET  /api/v1/songs/{song_id}/attempts?session_id=...
GET  /api/v1/practice/memory?session_id=...
```

Take 上传接受浏览器常见的 WebM、MP4/M4A、OGG 和 WAV。Hero 网页播放与下载优先使用 MP3，
内部仍保留 WAV 母文件用于音频分析和降级，不应把所有内部音频描述成 MP3。

## 当前完成度与后续工作

当前已经完成歌曲分析、三首 Hero 预缓存、语言标记、双轨歌词、用户录音、多 Take、共享音频时钟、
拖拽对齐、音量/静音、PracticeAttempt 前后比较、Memory 聚合、SQLite 持久化、结构化阶段耗时和
API 调用计数。前端已开始按职责拆分，并为多轨时间计算、偏移方向、循环边界与录音状态机增加测试。
多轨窗口支持拖动播放起点和实时总增益；新录音默认应用 500 ms 隐式延迟补偿。浏览器录音保留原格式，
送入 Gemini 前只生成临时的 16 kHz 单声道 WAV 兼容副本。

比赛冻结前仍需完成：三首 Hero 的手机端全流程人工验收；真实设备录音延迟校准；Gemini 的真实成本、
限流和结果质量记录；继续将 `main.tsx` 中的播放器与歌词视图拆成独立组件。远程模型 Worker 本阶段不部署。

## 数据与版本控制

`data/`、`.env`、虚拟环境、`web/node_modules/`、前端构建产物、模型权重和用户音频均被忽略，不得提交。现有 `data/` 使用仓库内相对布局，历史审计字段可以保留，但运行时配置不得访问旧项目路径。

## 从 VocalCompass 迁移

VerseViva 复用了 VocalCompass 阶段验证过的 Demucs、WhisperX 和 Song Profile 底座，但已经删除音高分析与旧 Difference Engine。旧目录只可作为只读迁移来源；日常启动、测试、模型命令与数据读取均不得依赖旧目录，也不得向旧仓库远端推送。
