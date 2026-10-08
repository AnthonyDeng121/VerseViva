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

## 4. 当前完成状态（2026-10-08）

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
- 新 Take 默认使用 500 ms 隐式设备延迟补偿，界面手动偏移仍从 0 ms 开始。
- 参考播放、用户试听与录音参考互斥；多轨混音支持选择播放起点和播放中实时总增益。
- WhisperX 词级对齐继续作为 G2P、语言候选和标记定位的内部证据；用户歌词播放只做整句高亮。
- 开始录音后切到技巧分析页供用户边看边唱；录音组件保持挂载，结束后回到演唱页。
- 后端 93 项回归、Ruff、前端 test/lint/build 构成冻结检查。

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

## 6. 剩余任务

比赛冻结前：

1. 在真实 iOS/Android 完成三首 Hero 全流程验收，检查权限、耳机、锁屏和弱网。
2. 完成真实设备录音延迟校准并记录不同浏览器的补偿范围。
3. 人工复核 Hero 语言提示、主/次轨进入时间和演示脚本。
4. 记录 Gemini 真实成本、429/503、超时和输出质量，确定额度与降级文案。
5. 完成 2–3 分钟可重复比赛演示和彩排。

后续工程优化：

1. 继续拆分 `main.tsx` 的播放器、标准歌词、双轨歌词和上传/任务面板。
2. 继续拆分 `RecordingStudio.tsx` 的预加载、MediaRecorder、Take API 和混音控制为 hook/service。
3. 增加浏览器组件测试及一条录音 → 上传 → 混音端到端测试。
4. 补充 G2P 未登录词、缩写和多发音词消歧。
5. 服务器上线后补监控、备份恢复演练和数据保留策略；远程 Worker 等真实负载需要时再评估。

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
python -m ruff check server tests scripts/hero_assets.py
cd web
npm test
npm run lint
npm run build
```
