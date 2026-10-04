# VocalCompass — Project Context / AGENTS.md

> 本文件是 **VocalCompass Demo 的产品与实现上下文源文件**。  
> 目标是让进入仓库的 Codex / AI Agent 不需要重新阅读聊天记录，也能理解：
>
> - 我们为什么做这个产品
> - 用户真正要解决什么问题
> - Demo 必须证明什么
> - 哪些功能是核心，哪些只是加分项
> - 技术方案为什么这样选
> - 实现时哪些原则不能被破坏
>
> 如果实现细节与本文冲突，优先保证 **产品闭环、P0 功能、Demo 稳定性**，不要为了“技术看起来高级”牺牲体验。

---

# 1. 产品一句话

**VocalCompass 是一个 AI 个性化跟唱教练。**

给它一首歌，它先理解原唱怎么唱；再听用户怎么唱；然后告诉用户：

- 哪里唱得和参考演唱有明显差异
- 哪些属于客观问题（音准 / 节奏 / 长音等）
- 下一遍应该怎么改
- 哪一句最值得单独重练
- 用户长期反复出现的弱点是什么
- 用户最近有没有进步

它不是另一个“K 歌打分器”。

我们的核心目标是把体验从：

```text
唱完
→ 得分
→ 结束
```

升级为：

```text
唱
→ 发现问题
→ AI 解释
→ 单句重练
→ 再次分析
→ 看见改善
→ 记住长期弱点
→ 下次继续针对性练习
```

产品关键词：

> **理解歌曲 / 理解用户 / 教学闭环 / 个性化记忆**

---

# 2. 核心产品理念

## 2.1 从“评分”升级到“教学”

传统 K 歌系统擅长告诉用户：

- 85 分
- 音准 82
- 节奏 88

但没有真正回答：

- 为什么只有 85？
- 哪一句最值得改？
- 是偏高还是偏低？
- 是唱错了，还是只是和原唱风格不同？
- 下一遍具体怎么唱？
- 我是不是一直犯同一个问题？
- 我练了几次以后有没有变好？

VocalCompass 要回答这些问题。

---

## 2.2 专用算法负责“量”，LLM 负责“教”

不要把所有音频问题都交给大模型。

### 专用算法 / 音频模型负责客观事实

例如：

- Pitch / F0
- Note / MIDI
- 音域
- 时间戳
- 用户与原唱的 cents 偏差
- 节奏提前 / 滞后
- 长音持续时长
- 词级时间对齐
- 人声分离

### LLM / Audio LLM 负责理解和表达

例如：

- 英文连读
- 重读 / 弱读
- 吞音 / 省音
- 原唱某一句的大致演唱处理
- 将结构化分析结果翻译成初学者听得懂的话
- 根据用户历史问题生成个性化建议
- 总结“用户最近最值得练什么”

原则：

```text
Algorithm / Audio Model
        ↓
      Facts
        ↓
       LLM
        ↓
     Coaching
```

不要让 LLM 凭感觉输出精确数值事实。

---

# 3. Demo 最终要证明的四件事

## 3.1 AI 可以理解一首新歌

不是只支持一首预制歌曲。

用户可以上传一首新歌，系统自动生成：

```text
Song
→ Vocal Stem
→ Pitch / Notes
→ Lyrics Alignment
→ Singing Hints
→ Song Profile
```

Demo 至少要展示：

- 预缓存 Hero Song
- 英文歌
- 一首临时重新分析的歌曲

这样可以证明系统不是“针对一首歌写死”。

---

## 3.2 系统可以看见用户与原唱之间的差异

至少需要识别：

- pitch high
- pitch low
- timing early
- timing late
- long note early release

展示形式应该直观：

```text
原唱  ━━━━━━━━━━━━━━━
用户  ━━━━━━━╮━━━━━━━━
             ↑
           偏高
```

---

## 3.3 系统真的能“教”

不是唱完以后只生成一张分析报告。

每一个重要问题都应该能够：

```text
发现问题
→ 点击「练这一句」
→ 听原唱
→ 用户再唱
→ 再次分析
→ 告诉用户有没有改善
```

示例：

```text
第 1 次：+42 cents
第 2 次：+25 cents
第 3 次：+9 cents

✓ 已明显改善
```

**单句重练闭环是 P0。**

---

## 3.4 系统会越来越了解用户

保存用户反复出现的问题：

```text
高音容易偏高
长音容易提前结束
节奏容易抢拍
英文连读容易断开
某些词反复处理不好
```

然后用于：

- 历史趋势
- AI 个性化建议
- “今天建议练什么”
- 判断当前问题是不是长期问题
- 展示改善趋势

---

# 4. 用户主流程

整个 Demo 要尽量控制在 2~3 分钟内能够演示完整闭环。

---

## Step 1：选择 / 上传歌曲

首页提供：

- 示例歌曲
- 上传 MP3

上传后进入分析页：

```text
正在理解这首歌……

✓ 提取原唱人声
✓ 分析音高和旋律
✓ 对齐歌词
✓ 分析演唱特征
✓ 生成练唱提示
```

分析结果缓存为 Song Profile。

---

## Step 2：查看歌曲声乐画像

可以展示：

- 音域
- Pitch / Note Timeline
- 歌词时间轴
- 英文演唱提示（若为英文歌）
- 声区 / 真假声 / 音色（如果分析可靠）

注意：

这里不要堆大量专业数据。

目标是让用户“看懂这首歌怎么唱”。

---

## Step 3：开始跟唱

页面核心：

- 当前歌词
- 原唱 Pitch Curve
- 用户实时 Pitch Curve
- 当前 note
- 当前 cents deviation
- 偏高 / 偏低提示

---

## Step 4：唱后诊断

不要先给一个总分。

优先展示：

# 这次最值得改的 3 个地方

示例：

### 01 副歌第一句

整句平均偏高约 31 cents，最后一个长音最明显。

`[练这一句]`

### 02 第三句

最后一个长音提前约 300ms 收掉。

`[练这一句]`

### 03 英文连读

`with you` 原唱基本连在一起，你这一遍中间停顿明显。

`[练这一句]`

---

## Step 5：单句重练

进入 Loop：

```text
听原唱这一句
↓
用户唱
↓
分析
↓
反馈
↓
再唱
```

一定要能显示用户变好。

---

## Step 6：Memory / History

长期生成用户 Vocal Profile。

例如：

```json
{
  "highPitchSharp": {
    "count": 7,
    "avgCents": 28
  },
  "longNoteEarlyRelease": {
    "count": 4
  },
  "englishLinking": {
    "failureCount": 6
  }
}
```

首页未来可以出现：

```text
今天建议练：

1. 高音稳定
   最近 5 次练习出现 4 次偏高

2. 英文连读
   最近三首英文歌都有断开
```

---

# 5. Song Understanding

## 5.1 输入

```text
Song Audio
+
Lyrics（如果有）
```

如果没有歌词，可以通过 ASR 获得歌词草稿。

---

## 5.2 Pipeline

```text
                 Song
                  │
         ┌────────┴────────┐
         ↓                 ↓
       Audio             Lyrics
         │                 │
    Source Separation      │
         ↓                 │
     Vocal Stem ────────────┘
         │
 ┌───────┼────────────┐
 ↓       ↓            ↓
Pitch  Alignment  Audio/LLM Analysis
 ↓       ↓            ↓
旋律    字词时间轴    连读/重音/演唱提示
 └───────┼────────────┘
         ↓
     Song Profile
```

---

# 6. Song Profile 建议结构

可以根据实际实现调整，但语义不要变。

```json
{
  "songId": "xxx",
  "title": "xxx",
  "duration": 210.2,
  "range": {
    "lowest": "C3",
    "highest": "E5"
  },
  "sentences": [
    {
      "id": "sentence_01",
      "start": 32.14,
      "end": 35.86,
      "lyrics": "I wanna be with you tonight",
      "pitchContour": [],
      "notes": [],
      "words": [
        {
          "word": "with",
          "start": 33.31,
          "end": 33.52
        }
      ],
      "singingHints": {
        "linking": ["wanna‿be", "with‿you"],
        "stress": ["tonight"],
        "reduction": [],
        "elision": [],
        "tips": []
      },
      "vocalFeatures": {
        "register": null,
        "falsetto": null,
        "timbre": null
      }
    }
  ]
}
```

---

# 7. Difference Engine

这是产品逻辑核心之一。

输入：

```text
Reference Pitch
+
User Pitch
+
Reference Timing
+
User Timing
```

输出：

```json
{
  "type": "pitch_sharp",
  "sentenceId": "sentence_04",
  "start": 42.3,
  "end": 44.1,
  "avgCents": 31,
  "maxCents": 52,
  "severity": "medium"
}
```

第一版至少支持：

```text
pitch_high
pitch_low
timing_early
timing_late
long_note_early_release
```

注意：

Difference Engine 输出事实。

最终自然语言解释交给 Coach。

---

# 8. 英文歌教学

这部分是项目特色功能之一。

目标不是做完整英语教育平台，而是解决：

> “为什么我音准差不多，却听起来不像原唱？”

至少分析：

- linking 连读
- stress 重读
- reduction 弱读
- elision / omission 吞音、脱落
- phrase timing
- 用户在词之间是否出现明显停顿

展示示例：

```text
I wanna‿be WITH‿YOU toNIGHT
       ↑       ↑        ↑
     连读     连读      重音
```

AI 文案示例：

> `with you` 原唱这里几乎一口气带过去。你这一遍两个词之间停顿比较明显，所以听起来有一点“逐词念”。

推荐输入：

```text
Vocal Clip
+
Lyrics
+
Word Timestamp
+
Acoustic Features
```

输出固定 JSON，不要输出不可控散文。

```json
{
  "linking": [],
  "stress": [],
  "reduction": [],
  "elision": [],
  "tips": []
}
```

---

# 9. 音域 / 音色 / 声区 / 真假声

这组属于挑战功能。

优先级：

```text
音域 > 声区 > 音色 / 真假声
```

## 9.1 音域

基于有效 Pitch 统计：

```text
Lowest Note ~ Highest Note
```

例如：

```text
C3 ~ E5
```

这是相对稳定的能力。

---

## 9.2 声区

尝试：

- chest
- mix
- head

Demo 中只作为：

> 辅助判断 / 参考分析

不要包装成专业医学级准确判断。

---

## 9.3 真假声

这是高难挑战项。

可尝试：

- harmonic structure
- spectral features
- F0
- energy
- HNR / spectral tilt
- 现成模型

如果效果不稳定，允许降低存在感。

**不能因为真假声模型没做完导致整个 Demo 失败。**

---

## 9.4 音色

第一版只做用户能理解的描述维度，例如：

- 明亮 / 暗
- 厚 / 薄
- 稳定 / 气声感明显

不要承诺专业 Timbre Classification。

---

# 10. 一个重要原则：不同 ≠ 错

原唱不是绝对标准答案。

必须区分：

## 客观问题

可以明确指出：

- pitch high / low
- timing early / late
- 长音提前结束
- 明显歌词错误

## 风格差异

只能描述差异：

- 原唱用假声，用户用混声
- 原唱尾音渐弱，用户保持强音
- 原唱更轻，用户更厚
- 不同情绪处理

文案应该类似：

> “你的处理方式和参考演唱不同。”

而不是：

> “你唱错了。”

---

# 11. 技术架构

```text
                         Mobile H5
                 React + TypeScript + Vite
                           │
          ┌────────────────┼─────────────────┐
          ↓                ↓                 ↓
     Song Upload      Live Microphone    Practice UI
          │                │
          ↓                ↓
       FastAPI        Web Audio API
          │            AudioWorklet
          │                │
  ┌───────┼────────┐       ↓
  ↓       ↓        ↓    Live Pitch
Demucs  Pitch   WhisperX      │
  │       │        │          │
  └───────┼────────┘          │
          ↓                   │
      Song Profile            │
          │                   │
          └─────────┬─────────┘
                    ↓
             Difference Engine
                    │
           ┌────────┴────────┐
           ↓                 ↓
        Memory              LLM
           │                 │
           └────────┬────────┘
                    ↓
             AI Vocal Coach
```

---

# 12. 建议技术栈

## Frontend

```text
React
TypeScript
Vite
Canvas 2D
Web Audio API
AudioWorklet
```

第一阶段是：

> Mobile-first H5

最终需要通过 URL 直接打开。

---

## Backend

```text
Python
FastAPI
SQLite
```

---

## Audio / AI

优先尝试成熟方案，不自己训练模型。

```text
Demucs
→ Source Separation / Vocal Stem

Basic Pitch / FCPE / CREPE
→ Pitch / Notes

WhisperX
→ Lyrics / Word Alignment
```

具体选哪个 Pitch Model，以：

- 集成成本
- 稳定性
- 延迟
- Demo 实测效果

为准。

不要为了模型名字更高级强行选难接的方案。

---

# 13. Web Demo 与未来小程序

第一阶段不要为了未来小程序提前增加过多复杂度。

但以下部分不要散落浏览器 API：

```text
audio capture
audio playback
file upload
storage
canvas rendering
```

尽量封装成平台服务。

例如：

```ts
interface AudioRecorder {
  start(): Promise<void>
  stop(): Promise<AudioResult>
}
```

H5 当前实现：

```text
getUserMedia
+
AudioWorklet
```

未来迁微信小程序时，可以替换 Adapter，而不是重写全部业务逻辑。

---

# 14. 推荐目录结构

仅作为建议，可按实际代码调整。

```text
src/
├── pages/
│   ├── home/
│   ├── song-analysis/
│   ├── practice/
│   ├── result/
│   ├── sentence-practice/
│   └── history/
│
├── components/
│   ├── PitchTimeline/
│   ├── LyricsTimeline/
│   ├── ProblemCard/
│   └── PracticeTrend/
│
├── core/
│   ├── song-profile/
│   ├── difference/
│   ├── practice/
│   └── memory/
│
├── services/
│   ├── api/
│   ├── audio/
│   ├── storage/
│   └── coach/
│
├── types/
└── utils/
```

Backend：

```text
server/
├── api/
├── pipelines/
│   ├── separation/
│   ├── pitch/
│   ├── alignment/
│   ├── english-coach/
│   └── vocal-features/
├── services/
│   ├── difference/
│   ├── memory/
│   └── llm/
├── models/
└── storage/
```

---

# 15. 功能优先级

## P0 — 没有这些 Demo 不成立

- 任意歌曲上传
- 自动人声分离
- 原唱 Pitch 提取
- 歌词时间对齐
- Song Profile
- 麦克风采集
- 用户实时 Pitch
- 原唱 / 用户双 Pitch Curve
- Difference Engine
- 问题片段检测
- 单句重练
- AI Coach

---

## P1 — 重点特色

- User Memory
- 英文教学
- 音域
- 声区
- History / Trend
- 今日练习建议

---

## P2 — 挑战功能

- 音色
- 真假声
- 更细的声乐技巧判断
- 分享卡
- 更丰富视觉动效

P2 没做完不能阻塞 P0。

---

# 16. 明确不做 / 不要过度实现

十天 Demo 阶段不要投入时间：

- 自己训练 Pitch Model
- 自己训练 Source Separation Model
- 自己训练复杂 Voice Register Model
- 专业级情绪评分
- 完整 QQ 音乐账号体系
- 会员 / 支付
- 社交系统
- B 端教师后台
- 完整移动 Native App
- 复杂权限系统
- 复杂微服务
- 为了“架构漂亮”提前抽象大量无用层

目标不是做“可上线的全民 K 歌替代品”。

目标是：

> **用一个稳定 Demo 证明产品命题成立。**

---

# 17. 双人分工原则

## A — 主前端

主要负责：

- React
- UI
- Canvas
- Web Audio
- 实时 Pitch UX

额外主攻挑战：

> **音域 / 音色 / 声区 / 真假声分析**

---

## B — 主后端

主要负责：

- Python
- FastAPI
- Audio Pipeline
- LLM
- 数据处理

额外主攻挑战：

> **英文歌教学**

---

## 其他任务必须尽量均摊

不要出现：

```text
A = 只写 CSS
B = 包办全部 AI / Backend
```

两个人都应该负责完整模块。

建议占比：

| 模块 | A | B |
|---|---:|---:|
| H5 基础工程 | 65% | 35% |
| Song Upload | 50% | 50% |
| Song Profile | 50% | 50% |
| 人声分离 | 35% | 65% |
| 原唱 Pitch | 50% | 50% |
| 实时用户 Pitch | 60% | 40% |
| Pitch 可视化 | 70% | 30% |
| Difference Engine | 50% | 50% |
| 单句重练 | 50% | 50% |
| Memory | 50% | 50% |
| AI Coach | 45% | 55% |
| 音域/音色/声区/真假声 | 80% | 20% |
| 英文教学 | 20% | 80% |
| Test | 50% | 50% |
| Demo / 路演 | 50% | 50% |

---

# 18. 十天开发计划

## Day 1 — Risk First

### 当天目标

在继续开发产品功能之前，先验证最不可控的两条技术链：

```text
浏览器麦克风
→ 实时波形 / 实时 Pitch

歌曲音频
→ 人声分离
→ 原唱 Pitch / Notes
→ 歌词与时间戳
```

Day 1 不追求正式接口和漂亮页面，只追求真实输入能够产生可检查的真实输出。

A：

- React/Vite 初始化
- 麦克风权限
- Web Audio
- 实时波形
- Pitch Demo

A 侧验收：

- 桌面浏览器能请求麦克风权限，允许和拒绝都有明确状态。
- 能看到随声音变化的实时波形。
- 对稳定哼唱能输出基本连续的 Pitch，而不是随机跳动或静音误检。
- 浏览器音频能力封装在 Adapter / Service 中，不散落在页面组件。

B：

- FastAPI
- Demucs
- Pitch Model
- WhisperX

### Day 1 B 侧实验结果（已完成）

实验输入：

```text
data/day1/input/song-60s.mp3
```

已在 WSL2 Ubuntu、Python 3.11、FFmpeg 和 CPU 推理环境下跑通完整链路。

#### 1. Demucs 人声分离

模型：`htdemucs`

成功输出：

```text
data/day1/output/demucs/htdemucs/song-60s/vocals.wav
data/day1/output/demucs/htdemucs/song-60s/no_vocals.wav
```

验证结果：

- 两个 WAV 均成功生成。
- `vocals.wav` 时长约为 `60.003s`，与输入片段一致。
- 输出可以继续供 Pitch 和歌词时间对齐使用。

#### 2. Basic Pitch 旋律 / 音符提取

输入：

```text
data/day1/output/demucs/htdemucs/song-60s/vocals.wav
```

成功输出：

```text
data/day1/output/pitch/vocals_basic_pitch.csv
data/day1/output/pitch/vocals_basic_pitch.mid
data/day1/output/pitch/vocals_basic_pitch.npz
```

验证结果：

- MIDI、Note Event CSV 和模型原始 NPZ 均成功生成。
- CSV 包含音符起止时间、MIDI Pitch、力度和 Pitch Bend 数据。
- CSV 的 `pitch_bend` 是可变长度序列，不能简单按固定五列解析；后端需编写专用转换器，或从 NPZ 提取帧级 Pitch。
- Basic Pitch 输出偏向 Note / MIDI，不等同于产品所需的连续 F0 曲线。

#### 3. WhisperX 歌词识别与对齐

输入：

```text
data/day1/output/demucs/htdemucs/song-60s/vocals.wav
```

成功输出：

```text
data/day1/output/whisperx/vocals.json
```

验证结果：

- 识别语言为英文。
- 生成 4 个句段、96 个词级时间戳。
- 首词约从 `0.852s` 开始，末词约在 `58.576s` 结束，与 60 秒音频范围基本一致。
- 歌唱场景存在少量歌词误识别，因此 WhisperX 文本应视作歌词草稿，时间戳可作为自动对齐基础。
- Hero Song 应优先使用人工校对歌词或合法来源的 LRC，再与 WhisperX 时间轴合并。

#### Day 1 B 侧结论

真实音频链已跑通：

```text
song-60s.mp3
→ vocals.wav
→ Pitch / Notes
→ 句级与词级歌词时间戳
```

因此可以进入 Day 2，不再继续以安装模型或重复跑同一首样例为主要工作。

### Day 1 B 侧后续待优化

- 把 Demucs、Basic Pitch、WhisperX 的命令行实验封装为独立 Pipeline Adapter。
- 统一模型输入格式、采样率、声道数和输出目录规则。
- 将 Basic Pitch CSV / NPZ 转换为项目统一的 `PitchPoint[]` 和 Note 数据。
- 对 Pitch 做静音过滤、置信度过滤、八度跳变修正和平滑处理。
- 将 WhisperX JSON 转换为 `Sentence[]` 和 `WordTiming[]`。
- 支持“用户提供准确歌词 / LRC + WhisperX 时间轴”的校正流程。
- 研究合法、稳定、可缓存的在线歌词或 LRC 来源；不可依赖不稳定网页抓取作为唯一方案。
- 记录每个阶段的运行时间、错误信息和产物路径，用于任务进度展示。
- 当前安装包含体积较大的模型依赖；后续只做必要的环境整理，不让环境优化阻塞产品闭环。
- 测试至少一首中文歌和另一首英文歌，确认当前结果不是单一样例特例。

当天共同验证：

```text
song.mp3
→ vocals.wav
→ pitch
→ lyrics timestamp
```

如果这条链没跑通，不进入后面功能。

当前状态：B 侧链路已跑通；A 侧仍需按上述标准完成并与真实后端数据对接。

---

## Day 2 — Song Profile

### 当天目标

把 Day 1 的散落模型产物转换成稳定、可查询、前端可直接消费的 Song Profile。

A：

- 上传页面
- Analysis Loading
- Song Profile 页面
- Lyrics Timeline

- 定义前端 `SongProfile` TypeScript 类型并与后端字段保持一致。
- 上传后展示真实任务阶段，而不是固定计时动画。
- 支持 queued、processing、completed、failed 状态和失败重试入口。

B：

- `/songs/analyze`
- 串 Demucs + Pitch + Alignment

- 完善文件扩展名、MIME、空文件和大小限制校验。
- 上传后生成稳定的 `song_id`、`job_id` 和隔离的工作目录。
- 增加 `GET /songs/jobs/{job_id}` 查询分析状态。
- 将三段 Pipeline 串联为可替换 Adapter，不在路由层直接调用模型命令。
- 实现 Basic Pitch 与 WhisperX 输出转换器。
- 将失败阶段、错误代码、用户可理解错误信息分开保存。
- 保存最终 Song Profile，并允许按 `song_id` 查询。

共同：

- 定 Song Profile Schema

- 明确 PitchPoint、Note、Sentence、WordTiming、SingingHints 的单位、字段命名和可空规则。
- 用 Day 1 真实产物生成第一份可校验 Song Profile fixture。

验收：

- 上传真实音频后获得任务 ID。
- 可以查询每个分析阶段及失败原因。
- 分析完成后返回真实 Song Profile，而不是 Mock 数据。
- API 测试覆盖成功上传、非法类型、空文件、任务不存在和模型失败。

### Day 2 后端真实验收结果（2026-10-04）

实验输入：

```text
data/day2/input/WONDER.mp3
```

音频时长：

```text
45.512s
```

本次验收从真实 API 入口开始，不使用离线脚本或 Mock：

```text
POST /api/v1/songs/analyze
→ queued
→ separating_vocals
→ extracting_pitch
→ aligning_lyrics
→ building_profile
→ completed
→ GET /api/v1/songs/{song_id}
```

成功任务：

```text
job_id  = job_903d6b1e7717416889b8f85ff310a851
song_id = song_6bf25113c26448a29e28981b866764e6
```

生成的真实 Song Profile：

```text
data/songs/song_6bf25113c26448a29e28981b866764e6/profile.json
```

结果摘要：

```text
schemaVersion: 1.0
language: en
durationSeconds: 45.512
sentences: 5
word timings: 76
sentence notes: 175
raw vocal range: F3 ~ G#6
pipelineVersion: day2-v1
separationModel: htdemucs
pitchModel: basic-pitch
alignmentModel: whisperx-small
lyricsSource: asr
```

注意：`F3 ~ G#6` 是尚未经过 Day 3 清洗的 Basic Pitch 原始音域，可能包含残留伴奏、瞬时误检或八度错误，当前不能直接作为面向用户的可靠音域结论。

#### 首次真实运行发现的问题与修复

第一次真实任务在 `extracting_pitch` 阶段失败：

```text
job_id = job_202a00042afc4dc0b041be16366d17af
```

错误为：

```text
Basic Pitch did not produce expected artifacts:
vocals_basic_pitch.csv
vocals_basic_pitch.npz
```

原因：当前 Basic Pitch CLI 默认只保存 MIDI；Day 1 手动实验使用了完整输出选项，但初版 Adapter 没有显式传入。

修复：Basic Pitch Adapter 增加：

```text
--save-note-events
--save-model-outputs
```

修复后成功生成：

```text
vocals_basic_pitch.csv
vocals_basic_pitch.mid
vocals_basic_pitch.npz
```

第一次失败任务保留在 `data/jobs/` 中，用于证明失败阶段、错误代码、用户提示和详细错误能够真实持久化与查询。

#### 真实耗时

当前 WSL2 + CPU 环境下，45.5 秒音频总耗时约：

```text
15 分 18 秒
```

大致阶段耗时：

```text
Demucs:                  约 2 分 15 秒
Basic Pitch:             约 2 分 33 秒
WhisperX + Word Align:   约 10 分 30 秒
Song Profile Build:      数秒内
```

结论：真实三模型链路已经成立，但当前 CPU 全量分析速度不适合作为 2~3 分钟演示中的主要等待段。Hero Song 必须预缓存；临时上传只用于证明泛化能力，并需要使用更短片段、模型预热或更快的推理环境。

#### Day 2 后端验收状态

已完成并验证：

- 文件扩展名、MIME、文件头、空文件和大小限制校验。
- 独立 `song_id`、`job_id` 和任务工作目录。
- 任务状态持久化与 `GET /songs/jobs/{job_id}`。
- Demucs、Basic Pitch、WhisperX Adapter。
- Basic Pitch 与 WhisperX Converter。
- 自动 Pipeline 和真实阶段更新。
- 失败阶段、错误代码、用户信息、详细错误分开保存。
- Song Profile 持久化与 `GET /songs/{song_id}`。
- Day 1 真实产物 fixture 和 Day 2 真实 API 全链路。
- API 测试覆盖成功上传、非法类型、空文件、超大文件、任务不存在、模型失败、Profile 成功和 Profile 不存在。
- 当前自动测试：`33 passed`；Ruff：`All checks passed`。

尚未完成：

- 前端上传页面。
- Analysis Loading 和真实任务阶段轮询。
- Song Profile 页面与 Lyrics Timeline。
- 前端 TypeScript Schema 对齐。
- queued、processing、completed、failed UI 与失败重试入口。

因此当前结论是：

> Day 2 后端核心链路已完成真实验收；Day 2 整体仍需完成前端部分后才能正式关闭。

#### 后续优化清单

P0 / 演示稳定性优先：

- 为各 Pipeline 阶段持久化 `started_at`、`finished_at`、`duration_seconds`，不再依赖人工轮询估算耗时。
- 增加模型预热，避免 WhisperX 首次加载占用大部分等待时间。
- 使用音频内容哈希建立缓存，重复上传相同音频时跳过 Demucs、Pitch 和 Alignment。
- 为 Hero Song 固定并预缓存全部产物，演示时直接读取 Song Profile。
- 为临时上传准备更短的合法测试片段，并显示真实阶段而不是假进度。
- 为模型进程增加更合理的阶段超时、取消和服务重启恢复策略。
- 在目标手机上通过 HTTPS URL 验证上传、轮询、弱网与后台恢复。

Day 3 数据质量优化：

- 对 Pitch / Note 做静音过滤、置信度过滤、极短 Note 过滤、八度跳变修正和平滑处理。
- 音域只根据清洗后的有效数据计算，不直接展示 `F3 ~ G#6` 等原始范围。
- 从 Basic Pitch NPZ 或其他连续 F0 输出生成真实 `PitchPoint[]`，不把 Note Event 展开成伪连续曲线。
- 记录清洗前后统计，保留 Debug 可追溯性。

已确认暂缓：

- 用户上传歌词、在线歌词搜索、LRC 合并与人工校对歌词流程暂不在本轮实现，后续作为歌词质量优化单独处理。
- 当前 Song Profile 的 `lyricsSource` 保持为 `asr`，不得把未实际使用的用户歌词标为 `provided`。

部署边界：

- WSL2 只是 Windows 开发机上的 Linux 后端环境，不是手机端依赖。
- 手机只运行 React H5，并通过 HTTPS 调用后端 API；Demucs、Basic Pitch、WhisperX 均运行在后端计算环境。
- 正式部署时后端应运行在 Linux 服务器或等价容器环境，不要求手机具备 WSL。

---

## Day 3 — Reference Visualization

### 当天目标

把原唱分析结果变成用户看得懂、前端画得稳的参考时间轴。

A：

- Pitch Curve
- Canvas Timeline
- 播放进度同步
- 歌词同步
- 开始调研 vocal features

- Canvas 根据播放窗口只绘制可见数据，避免整首歌每帧重绘。
- 支持播放、暂停、拖动和跳到指定歌词句。
- 显示当前歌词和当前参考音高，不直接堆声学指标。

B：

- Pitch 数据清洗
- Note / cents
- Difference Engine v0

- 从模型输出生成统一时间步长或可插值的参考 PitchPoint。
- 过滤无声区、低置信度点和明显八度错误。
- 计算 MIDI、音名、有效音域以及句级 Pitch 摘要。
- 建立 Difference Engine 的纯函数接口和合成测试数据。

共同：

- 使用 Day 1 的 60 秒样例逐段核对音频、歌词、Pitch 曲线是否同步。
- 调整 JSON 体积和前端采样密度，避免将全部原始 NPZ 数据直接传给浏览器。

验收：

- 播放进度、歌词高亮和参考 Pitch 曲线基本同步。
- 拖动播放位置后 UI 能正确恢复。
- 后端清洗前后数据差异可在 Debug 模式检查。

### Day 3 后端连续 Pitch 实现与真实验收（2026-10-04）

连续 Pitch 数据采用双路径：

```text
主路径：Basic Pitch NPZ contour + Note Event 约束
降级路径：Basic Pitch CSV 中官方解码的 pitch_bend
```

主路径直接读取本系统 Basic Pitch Adapter 生成的可信 NPZ。Note Event 用于确定有效人声区间和主音附近的搜索范围，contour 用于恢复约 86 帧/秒的细粒度音高和帧级置信度。NPZ 缺失、损坏或结构不兼容时，自动回退到 CSV `pitch_bend`，不会让整个歌曲分析任务失败。

已完成：

- 低置信度和极短 Note 过滤。
- 静音区不生成虚假 PitchPoint。
- 局部短暂泛音/八度误判修正。
- 前端数据降采样到约 30 点/秒。
- PitchPoint 按歌词 Sentence 时间范围写入 Song Profile。
- 使用清洗后 Pitch 的 5%～95% 稳健分位数计算面向用户的音域。
- AnalysisMetadata 记录数据来源、是否降级、降级原因、过滤数量和八度修正数量。
- Difference Engine v0 支持 cents 换算与不跨静音区的参考 Pitch 插值。

真实产物验收：

```text
Day 1 60 秒样例
source: basic-pitch-npz-contour-with-note-events
fallbackUsed: false
raw notes: 222
accepted notes: 185
raw pitch points: 3664
frontend pitch points: 1311
清洗后稳健音域: A3 ~ A#4

Day 2 WONDER.mp3（45.512 秒）
source: basic-pitch-npz-contour-with-note-events
fallbackUsed: false
raw notes: 183
accepted notes: 115
octave corrections: 7
raw pitch points: 2184
frontend pitch points: 795
清洗后稳健音域: C#4 ~ C#5

Fallback 验收
缺失 NPZ 时 source: basic-pitch-csv-decoded-bends-fallback
fallbackUsed: true
仍可输出 1311 个 PitchPoint
```

自动化验证：

```text
39 passed
Ruff: All checks passed
```

当前 Day 3 后端参考 Pitch 已完成；播放同步、歌词高亮和 Canvas 曲线仍属于前端待完成内容，因此 Day 3 整体尚未关闭。

---

## Day 4 — User Live Pitch

### 当天目标

让用户真正唱一段，并在手机浏览器看到自己的 Pitch 与参考曲线同步出现。

A：

- 用户麦克风
- User Pitch Curve
- Reference + User 双曲线
- 当前音高 UI

- 封装 AudioRecorder 和 LivePitchDetector。
- 处理静音、耳机/扬声器回授、权限拒绝和页面切后台。
- 录制练习音频或 PitchPoint 序列，为唱后诊断保留原始依据。

B：

- User Pitch 数据处理
- Reference 对齐
- Pitch Difference

- 定义用户练习提交接口和数据格式。
- 将前端时间轴转换为歌曲绝对时间，处理开始延迟和暂停。
- 实现参考 Pitch 插值、有效帧匹配和 cents 计算。
- 保存 Debug 指标，区分无声、低置信度和可比较帧。

Milestone：

> 用户真的可以唱一段，并看到两条实时曲线。

验收：

- 桌面和至少一台目标手机浏览器完成权限、录音、播放和双曲线展示。
- 静音时不显示虚假偏高/偏低。
- 用户 Pitch 与歌曲进度没有持续扩大或缩小的漂移。

---

## Day 5 — Post Singing Diagnosis

### 当天目标

从逐帧差异中提炼 1–3 个可定位、可解释、值得练的问题。

A：

- 问题列表
- Problem Timeline
- 跳转对应句子

B：

实现：

- pitch high
- pitch low
- timing early
- timing late
- long note early release

共同调阈值。

B 侧实现细化：

- `pitch_high` / `pitch_low`：要求连续有效帧和最小时长，避免瞬时抖动误报。
- `timing_early` / `timing_late`：基于可靠的起音或句段边界，缺少依据时不输出。
- `long_note_early_release`：比较参考与用户的有效持续时间，排除录音截断。
- 按严重程度、持续时间和教学价值排序，不只按最大偏差排序。

共同验收：

- 合成样例对五类问题有确定结果。
- 真实演唱至少能稳定定位一个合理问题。
- 每个问题包含句子、开始/结束、事实指标、严重程度和可追溯证据。
- 风格差异不使用“唱错了”的文案。

---

## Day 6 — Sentence Practice Loop

### 当天目标

完成产品最核心的教学闭环，而不是停留在分析报告。

A：

```text
听原唱
→ 开始唱
→ 结果
→ 再试一次
```

B：

- sentence clip
- practice attempt
- improvement calculation

- 根据 Sentence 时间范围生成或按区间播放参考人声片段。
- 保存 PracticeAttempt、输入数据、问题和核心指标。
- 使用同一套指标比较第 1 次与第 2 次，避免评分口径变化。
- 输出 improved、unchanged、regressed、insufficient_data 四种明确状态。

Milestone：

> **基础产品闭环完成。**

验收：

- 从问题卡点击后可听参考、录制、分析、查看改善并再次练习。
- 至少一项指标能展示真实前后变化。
- 数据不足时诚实提示，不强行显示改善。

---

## Day 7 — Challenge Features

### 当天目标

在 P0 闭环已稳定的前提下，增加可体现差异化且有事实依据的能力。

A 主攻：

- 音域
- 声区
- 真假声
- 音色

B 主攻：

- English linking
- stress
- reduction
- elision
- Structured LLM Output
- English Coach

B 侧实现细化：

- 输入固定为 vocal clip、准确歌词、WordTiming 和可观测声学特征。
- linking、stress、reduction、elision 使用结构化 Schema。
- 先验证 `with you` 等词间停顿和重音强弱，不追求完整英语教学体系。
- LLM 只能解释已有特征，不生成精确时间或 cents。
- Structured Output 解析失败时返回降级模板，不把自由文本写入核心数据。

共同验收：

- 英文 Hero Song 至少展示一个连读或重音提示。
- 挑战功能失败不会影响上传、跟唱、诊断和单句重练。
- 声区、真假声或音色不可靠时降低存在感并标为参考。

---

## Day 8 — Memory

### 当天目标

让系统能够根据多次练习形成用户弱点和改善趋势，而不是每次从零开始。

A：

- History UI
- Trend
- 今日练习
- vocal feature integration

B：

- SQLite
- PracticeSession
- PracticeIssue
- UserWeakness
- Memory → LLM

- SQLite 建表和最小迁移/初始化机制。
- 记录 PracticeSession、PracticeAttempt、PracticeIssue、UserWeakness。
- 聚合出现次数、最近出现时间、平均偏差和改善趋势。
- Memory 提供结构化摘要给 Coach，不直接拼接整段历史自由文本。

共同完成长期个性化链路。

验收：

- 同一类问题多次出现后能形成长期弱点。
- 重练改善后趋势会更新，不只累计失败次数。
- 首页建议能够追溯到最近练习事实。

---

## Day 9 — Generalization

### 当天目标

停止添加功能，用多首歌曲找出泛化问题和现场演示风险。

不要加功能。

测试：

```text
中文歌 A
中文歌 B
英文歌 C
英文歌 D
临时上传 E
```

检查：

- Separation
- Pitch
- Alignment
- LLM Structured Output
- Web Audio
- Timing Sync
- Vocal Feature Reliability
- Cache

还需记录：

- 每首歌各阶段耗时、峰值内存、输出体积和失败阶段。
- 中文/英文识别差异、歌词错误率和词级时间戳可用性。
- Demucs 残留伴奏对 Pitch 的影响。
- 手机端首次权限、弱网、后台恢复和长音频上传表现。
- 缓存命中后是否跳过重复模型计算。

验收：

- 至少 5 首测试歌都有记录，不只保留成功案例。
- Hero Song 全链路稳定；备用 Hero Song 可切换。
- 临时上传失败时有明确提示和可恢复方案。

---

## Day 10 — Freeze

### 当天目标

冻结功能和模型版本，只提高演示稳定性与可解释性。

只允许：

- Bug Fix
- Loading
- Error Handling
- Fallback
- Performance
- Cache
- Demo Stability

准备：

### Song A

中文 Hero Demo：

```text
Live Pitch
→ Diagnosis
→ Sentence Practice
```

### Song B

英文 Hero Demo：

```text
Pitch
+
Linking
+
Stress
+
AI Coach
```

### Song C

临时重新分析：

> 证明不是预制歌曲。

冻结要求：

- 固定依赖、模型版本、阈值和 Hero Song 产物。
- 预热必要模型并确认缓存位置。
- 准备网络异常、麦克风拒绝、模型超时和上传失败的回退话术与 UI。
- 清理 Debug 信息，但保留可快速定位问题的日志。
- 在最终演示手机、浏览器和网络环境完整彩排至少两次。

最终验收：

```text
选择 / 上传歌曲
→ 理解歌曲
→ 跟唱并显示双 Pitch
→ 给出 1~3 个具体问题
→ 单句重练
→ 展示真实改善
→ Coach 用人话解释
→ Memory 记录弱点与趋势
```

整个流程应在 2~3 分钟内稳定完成。任何 P1/P2 功能都不得阻塞这条主链路。

---

# 19. Codex 工作方式

Codex 在实现本项目时请遵守：

## 19.1 先理解再改

开始一个模块之前：

1. 阅读本文件
2. 阅读已有代码
3. 明确当前模块对应哪个产品目标
4. 不要只为了“代码完整”实现与 Demo 无关的功能

---

## 19.2 不擅自改变产品方向

不要自动引入：

- 登录
- 支付
- 社交
- 复杂推荐
- 教师后台
- 不在 P0/P1 的新功能

如果发现更好的实现方式，可以修改技术方案。

不要自行改变产品主流程。

---

## 19.3 优先 Demo 可用性

选择：

```text
simple + stable + explainable
```

而不是：

```text
complex + academically impressive + unstable
```

例如：

如果一个简单 Pitch Algorithm 已经足够让 Demo 曲线稳定，就不要为了换 SOTA 模型导致两天集成成本。

---

## 19.4 所有 AI 输出尽量结构化

优先 JSON Schema。

不要让后端依赖自由文本解析。

---

## 19.5 所有分析结论要有事实来源

AI Coach 不允许凭空生成：

> “你的气息支撑不好。”

除非系统真的有对应可观测事实。

推荐结构：

```text
metric / observation
→ issue
→ teaching explanation
```

---

## 19.6 UI 不要专业工具化

用户不是声学工程师。

避免直接展示：

```text
F0 variance = 0.382
HNR = 14.2
Spectral Tilt = ...
```

应该转换成：

> “这一句后半段越来越偏高。”

技术指标可以存在内部 Debug Panel。

---

# 20. Demo 成功标准

十天后，如果现场能稳定完成下面流程，即视为 Demo 成功：

```text
上传 / 选择歌曲
↓
自动理解歌曲
↓
开始跟唱
↓
看到实时 Pitch 差异
↓
系统指出 1~3 个具体问题
↓
点击其中一句重练
↓
第二次结果发生改善
↓
AI 用人话解释
↓
History 能记住这个弱点
```

再额外做到：

```text
英文歌：
自动显示部分连读 / 重音教学
```

则 Demo 已经具备明确差异化。

---

# 21. 最终判断标准

每做一个功能，都问一句：

> **它有没有让 VocalCompass 更像“一个真的会教我的 AI 老师”？**

如果答案是否：

> 十天 Demo 阶段先不做。


