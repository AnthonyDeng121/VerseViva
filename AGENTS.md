# VerseViva 声声不息 — Project Context

> 进入仓库后先阅读本文。本文只记录当前有效的产品边界、实现事实、运行约束和剩余任务；历史开发日记、已完成的逐日计划和失效路径不再保留。

## 1. 产品定义

**VerseViva 是 AI 外语歌曲演唱与分轨练习教练。**它帮助用户看懂原唱在歌曲中省略、合并或改变了哪些声音，分别练习主唱、和声、回应、ad-lib 和重叠句，再把多个真实录音 Take 按同一伴奏时间轴叠加回放。

核心表达：听懂每一句，唱活每一首。

产品不做音准总分、音符、音域或音高评分；不把原唱解释成唯一正确答案；不声称 Demucs 已把 lead/harmony 完美拆成独立 stem；不做完整 DAW、自动调音或复杂效果器；不允许 LLM 在没有证据时自由诊断。

## 2. 核心原则

### Language in music

分析对象是具体演唱中的省音、未释放、相同辅音共享、融合、再音节化和元音连接。时间接近本身不能证明连读。歌词层只显示稳定符号：`×` 表示目标音未清楚出现或释放；`‿` 表示跨词连续动作；`└─┘` 表示多个输入音共享或融合。中文解释、动作建议和证据放在展开详情。

### 事实先于解释

```text
Audio / Algorithm → observable facts → structured issue → LLM coaching
```

LLM 只能解释已有事实，不得虚构毫秒、准确率或声学结论。模型故障保存为 `failed`；只有音频质量或证据确实不足时才返回 `insufficient_data`。提示保留 `acoustic_observed`、`text_rule_candidate`、`llm_suggestion`、`human_curated` 来源。已确认的括号声部文本使用 `lyrics_provider`；Gemini 只核查可听见性和时间，不改写确定歌词。

### Vocal Part、Take 与混音

- `primary` / `secondary` 是教学 lane，不是轨道数量上限。
- Vocal Part 描述参考编排；Take 描述用户录音，两者不可混用。
- Take 非破坏性保存，并独立持久化 timeline start、latency compensation、manual offset、gain、mute。
- 多轨回放使用同一个 `AudioContext` 时钟；伴奏是不可拖动的基准。
- 混音范围取用户选取的最早开始和最晚结束，中间无录音仍连续播放伴奏。

### 练习与 Memory

- 用户录音整句交给 Gemini 与参考比较，本阶段不运行用户录音 WhisperX 词级对齐。
- PracticeAttempt 保存结构化问题、指标、版本和与上一遍的同指标比较。
- 趋势查看最近 3–5 次可靠尝试；Memory 不统计失败或证据不足。

## 3. 技术与 Pipeline

Frontend：React、TypeScript、Vite、Web Audio API。Backend：Python 3.11+、FastAPI、SQLite。Audio / AI：Demucs、WhisperX、LRCLIB、CMUdict/G2P、Gemini Structured Output。

```text
上传 MP3/WAV/FLAC → ffprobe → Demucs → LRCLIB/提供歌词
→ WhisperX 参考人声句/词对齐 → G2P 候选 → Gemini 受限核查
→ Song Profile → 用户录音 / PracticeAttempt / 多 Take 混音
```

Pipeline 每阶段记录实际/估算耗时、API 调用次数、缓存命中和运行次数。429、5xx、超时和非法 JSON 只能有限重试；最终失败必须显示真实阶段和恢复入口。

## 4. Demo 定型状态（2026-10-09）

- 上传校验、独立 song/job、进度、失败持久化、刷新恢复和失败重试。
- Demucs、WhisperX、LRCLIB、G2P、Gemini 核查和 Song Profile。
- single/dual track，括号声部按 `lyrics_provider` 确定文本处理。
- 原曲、人声、伴奏、0.75×、句循环、跳转、词级高亮和标记详情。
- 主/次 Vocal 左右语义及来源、置信度、复核状态。
- 录音资源完整预加载门禁、浏览器录音上传和恢复。
- 多 Take、共享音频时钟、延迟/手动偏移、拖拽对齐、音量和静音。
- Gemini 整句分析、同指标前后比较、最近 3–5 次趋势和 Memory。
- Take/PracticeAttempt SQLite 持久化；旧逐目录 `take.json` 已退出运行链路。
- 模型故障与证据不足分开表达。
- 三首 Hero 预缓存及带 SHA-256 校验的独立部署 ZIP。
- 前端依赖固定版本；Vitest 覆盖时间轴、偏移、循环边界和录音状态迁移。
- 浏览器录音送入 Gemini 前临时转为 16 kHz、64 kbps 单声道 MP3，原始 Take 保持不变；录音上限为 100 MB。
- Take 上传按文件头识别 WebM、M4A/MP4、OGG、WAV 的真实容器；浏览器或手工文件名与内容不一致时规范化扩展名和 MIME，不因误标扩展名阻断分析。
- 新 Take 默认使用 500 ms 隐式设备延迟补偿，界面手动偏移仍从 0 ms 开始。
- 参考播放、用户试听与录音参考互斥；多轨混音支持选择播放起点和播放中实时总增益。
- WhisperX 词级对齐继续作为 G2P、语言候选和标记定位的内部证据；用户歌词播放只做整句高亮。
- 日韩歌曲的语言标记只绘制在罗马音行，详情卡保留原文、辅助读音和演唱提示；三首 Hero 的人工语言规则校正由 `scripts/curate_hero_hints.py` 固化并纳入回归。
- 开始录音后切到技巧分析页供用户边看边唱；录音组件保持挂载，结束后回到演唱页。
- 麦克风授权完成后切到技巧分析页显示 3 秒倒计时，再同步启动录音与参考音频；Gemini Files 偶发处理失败会有限重试并清理远端临时文件。
- 三种可见语言标记 `×`、`‿`、`└─┘` 都必须进入 Practice 分析目标；目标词按标记字符位置生成，不得跨接 primary/secondary lane。
- Practice 发给 Gemini 的每个目标必须携带符号、参考动作、标准/实际读音、结构变换和人工解释；提示词正文必须明确 `×` 吞音、`‿` 改音式连读、`└─┘` 二合一的判定标准。
- Gemini 将可用录音返回为空或全部 `uncertain` 时按临时模型故障有限重试，不得保存成无反馈的成功结果。
- Take 摘要和练习反馈按 `track_slot_id` 投影歌词：primary 排除括号副轨，secondary 只取括号声部。
- 练唱分析前用 ffmpeg 客观峰值门禁拦截近静音录音；同一句、同 lane 的可靠 Attempt 才参与前后比较，选择范围变化不应重置句级历史。
- 用户可选择“仅分析”或“分析并保存”；仅分析保留 PracticeAttempt 与 Memory，但删除临时 Take 音频且不进入正式音轨列表。已保存 Take 可连同音频和对应 Attempt 删除。
- 次轨多句分析必须覆盖所选的全部 Vocal Part；每条次轨起点锚定对应主轨句首。`lyrics_provider` 的确定歌词和人工时间锚点不可被 Gemini 以 stem 分离困难为由推翻。
- 次轨 Gemini 目标必须来自 Song Profile 中已有的具体 `×`、`‿`、`└─┘` 标记，不得按问题类型机械补齐；混合参考导致全部 `uncertain` 时，Plan B 只发送用户录音和确定目标直接核查。
- 前端通过短请求启动 Practice 后台任务并轮询 Attempt，不得用单个 20–90 秒 HTTP 请求等待 Gemini；任务消失时明确提示中断并保留重分析入口。
- 歌曲 Demucs/WhisperX Pipeline 使用单 FastAPI 进程内的 FIFO 队列，任意时刻只运行一个重型歌曲分析任务；当前 Docker 固定单 Uvicorn worker。扩展为多 API 进程前必须迁移到跨进程持久任务队列，不得误以为进程内队列能限制多进程总并发。
- Practice 等待界面按“仅分析”和“分析并保存”分别显示按钮状态、已等待秒数和基于录音时长的粗略预估；预估不是模型承诺，完成前进度不得显示 100%。
- 较长练唱按少量句子/次轨编排分批送入 Gemini；次轨提示必须包含相对于用户录音起点的核查区间，避免重复歌词跨段套用结论。用户界面不得出现 Plan B 等内部实现名。
- Take 的 `track_slot_id` 统一使用 lane、起始句、结束句与句数构成的固定长度确定性标识，仅供内部识别相同练习范围；不得因13句或整首歌的句数增加而在上传阶段失败。
- `practice-language-v6` 将长录音按最多4句主轨或3段次轨分批，并按用户录音相对时间窗同步裁切用户音频与参考音频，避免长请求过载和重复副轨歌词串段。
- 当前会话可导出 192 kbps MP3 整体混音；导出必须应用 Take 的 mute/gain、延迟补偿、手动偏移和整体增益。
- 公网 Demo 使用后端签名的 HttpOnly、Secure、SameSite=Lax 匿名会话 Cookie；歌曲 Job、非 Hero Song、Take、录音、Attempt、Memory、混音和删除操作都按该会话隔离。客户端提交的 `session_id` 仅为旧接口兼容字段，不得作为授权依据；无归属的旧数据不得在生产环境公开。
- 后端回归、Ruff、前端 test/lint/build 构成冻结检查。

当前 Hero：

- `song_00000000000000000000000000000003`：Olivia Rodrigo《get him back!》英语双轨片段。
- `song_00000000000000000000000000000004`：BLACKPINK《AS IF IT'S YOUR LAST》韩语片段。
- `song_00000000000000000000000000000005`：TUNE'S《動物園は大変だ》日语片段。

## 5. 数据与部署

```text
data/
├─ songs/<song_id>/{profile.json,audio/...}
├─ takes/<take_id>/original.<browser-format>
└─ verseviva.sqlite3
```

Hero 网页播放、下载和模型代理优先 MP3；WAV 是母文件和降级输入。用户浏览器录音通常是 WebM/M4A/OGG/WAV，不应描述成 MP3。

Hero 采用独立部署包：

```bash
python scripts/hero_assets.py build
python scripts/hero_assets.py restore artifacts/verseviva-hero-assets.zip --data-dir /app/data
```

部署包不包含 SQLite、用户录音、历史 Job 或密钥。远程模型 Worker 本阶段不部署；配置只保留兼容性，当前模型由主 FastAPI 进程调用。

### 当前比赛线上实例（2026-10-10）

- 正式入口为 `https://verseviva.top`，永久跳转到 `https://www.verseviva.top`；DNS A 记录指向 `43.161.219.71`。
- 腾讯云轻量应用服务器位于中国香港，Ubuntu 24.04 LTS、x86_64、2 vCPU、约 8 GB 内存、80 GB 系统盘，并额外配置约 6 GB swap。
- Docker Compose 固定运行一个 FastAPI/Uvicorn `app` 容器和一个 Caddy 容器。Caddy 负责 80 → 443 跳转、反向代理和 Let's Encrypt 自动证书；云防火墙放行 22/TCP、80/TCP、443/TCP，443/UDP 仅用于可选 HTTP/3。
- `verseviva-data`、`caddy-data`、`caddy-config` 均为持久卷；三首 Hero 已从带 SHA-256 清单的独立 ZIP 恢复到 `verseviva-data`。`.env.production` 权限为 600，不得把其中的 Key 写入仓库或文档。
- 完整基础镜像约 6.51 GB，包含 CPU-only Demucs、WhisperX 与 ffmpeg。线上健康检查、两个域名 HTTPS、Hero Profile/音频和匿名会话隔离已完成黑盒验收。
- 会话隔离上线前已通过 SQLite backup API 生成部署前备份；服务器当前还保留覆盖层发布前的镜像标签作为短期回滚点。它们不是长期备份策略，后续仍需自动备份、恢复演练和保留期清理。
- 为避免香港实例以约 50 KB/s 再次下载数 GB Python 模型依赖，会话隔离首次上线采用“已验证完整基础镜像 + 仅复制变更应用文件”的覆盖层镜像发布。2026-10-10 已完成自包含完整镜像重建并切换生产：Dockerfile 将稳定的 Demucs/WhisperX 环境放在应用源码之前，重复构建实测约 2 秒且模型层命中缓存；生产镜像不再依赖临时 `pre-*` 覆盖层链，旧标签仅作为短期回滚点保留。
- 当前公网 Demo 适合受控比赛评审，不等同于长期开放的多租户服务：尚未实现上传/Gemini 调用限频、用户配额、监控告警、自动备份和隐私数据定期清理，不应在社交媒体无限制扩散。

## 6. Demo 冻结结论与复赛优化

当前 Demo 代码链路已定型：歌曲上传与恢复、单并发歌曲分析队列、三首 Hero、语言技巧展示、主/次轨录音、Gemini
练唱分析、Attempt/Memory、多 Take 对齐混音与 MP3 导出均已有实现和回归覆盖。Hero 部署包已通过
空数据目录恢复验收；冻结检查为后端 117 项、前端 12 项全绿，Ruff、ESLint 和生产构建通过。

部署前置条件不是待开发功能：必须填写生产环境 Gemini Key（GLM Key 可选）、用
`docker compose --env-file .env.production` 启动、恢复 Hero ZIP、挂载
持久数据卷并配置固定域名/HTTPS。代码审计未发现仍可稳定复现的核心链路阻塞；真实设备、外部模型
额度和云环境属于交付验收边界，不能由单元测试替代。

当前比赛 Docker 运行于纯 CPU Linux，构建时必须先使用 PyTorch 官方 CPU index 安装两套隔离环境的
Torch 依赖，避免默认 PyPI 解析并下载无用的 CUDA/NVIDIA 运行库。

复赛阶段优化：

1. 在真实 iOS/Android 验收三首 Hero，覆盖权限、耳机、锁屏、弱网，并校准各浏览器录音延迟。
2. 记录 Gemini 成本、429/503、超时和输出质量；按真实并发决定是否部署持久任务队列和远程 Worker。
3. 增加浏览器组件测试及一条录音 → 上传 → 分析 → 混音端到端测试。
4. 拆分 `main.tsx` 与 `RecordingStudio.tsx`，并补充 G2P 未登录词、缩写和多发音词消歧。
5. 上线后增加监控、SQLite/用户录音备份恢复演练、数据保留与隐私清理策略。

## 7. 仓库约束

- 先阅读本文和 README；实现变化后同步更新。
- 不提交 `data/`、`artifacts/`、用户音频、密钥、权重、虚拟环境、`node_modules` 或构建产物。
- 不依赖历史 `data/day*`；测试夹具放 `server/fixtures` 或测试临时目录。
- 普通回归不重复运行完整 Hero Pipeline。
- 不覆盖无关修改，不使用 `git reset --hard` 或 `git checkout --` 清理工作树。
- 新增 API、Schema、环境变量或布局时同步 README 和测试。

冻结检查：

```bash
python -m pytest -q --basetemp=<可写临时目录>
python -m ruff check server tests scripts
cd web
npm test
npm run lint
npm run build
```
