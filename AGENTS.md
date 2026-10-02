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

A：

- React/Vite 初始化
- 麦克风权限
- Web Audio
- 实时波形
- Pitch Demo

B：

- FastAPI
- Demucs
- Pitch Model
- WhisperX

当天共同验证：

```text
song.mp3
→ vocals.wav
→ pitch
→ lyrics timestamp
```

如果这条链没跑通，不进入后面功能。

---

## Day 2 — Song Profile

A：

- 上传页面
- Analysis Loading
- Song Profile 页面
- Lyrics Timeline

B：

- `/songs/analyze`
- 串 Demucs + Pitch + Alignment

共同：

- 定 Song Profile Schema

---

## Day 3 — Reference Visualization

A：

- Pitch Curve
- Canvas Timeline
- 播放进度同步
- 歌词同步
- 开始调研 vocal features

B：

- Pitch 数据清洗
- Note / cents
- Difference Engine v0

---

## Day 4 — User Live Pitch

A：

- 用户麦克风
- User Pitch Curve
- Reference + User 双曲线
- 当前音高 UI

B：

- User Pitch 数据处理
- Reference 对齐
- Pitch Difference

Milestone：

> 用户真的可以唱一段，并看到两条实时曲线。

---

## Day 5 — Post Singing Diagnosis

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

---

## Day 6 — Sentence Practice Loop

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

Milestone：

> **基础产品闭环完成。**

---

## Day 7 — Challenge Features

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

---

## Day 8 — Memory

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

共同完成长期个性化链路。

---

## Day 9 — Generalization

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

---

## Day 10 — Freeze

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

---

# 22. CPU / 轻量优先的 10 天替代计划（2026-10 修订）

> 本计划是原第 18 节「十天开发计划」的替代执行方案，不删除、不覆盖原计划。
> 适用于本地没有可用 GPU、模型下载时间或磁盘空间有限的团队。原计划仍保留，具备资源时可按原计划执行。

## 22.1 调整原则

- 产品目标不变，调整模型验证顺序和 Demo 的计算位置。
- 不要求 Day 1 下载并跑通 Demucs、Pitch、WhisperX 三套重型依赖。
- 先用短音频、现成歌词/时间戳和轻量 F0 算法验证数据链路。
- 麦克风实时 Pitch 优先在浏览器端运行；用户录音不需要实时上传服务器推理。
- 后端 Pipeline 可替换，先提供 Mock / 轻量实现，避免业务流程依赖大模型。
- Hero Song 可预先分析并缓存 Song Profile；上传新歌仍提供真实分析路径及耗时/失败状态。
- Demucs、WhisperX 等仅在确有产品收益、机器和网络预算允许时引入。
- Mock、手工时间戳或风格差异必须明确标注，不可伪装成模型事实。

## 22.2 能力分层

### 必须真实运行

- 文件上传、格式/大小校验、任务状态和错误处理。
- 浏览器麦克风采集及用户实时 Pitch，可用 YIN/自相关等轻量算法。
- 参考 Pitch 可视化、对齐和 Difference Engine。
- 单句重练、前后对比和练习记录。

### 可轻量实现或使用已有数据

- 参考 Pitch：先用短清唱片段或已有 vocal stem，以轻量 F0 提取验证；可试 `librosa.pyin` 或 `aubio`，按效果和延迟决定。
- 歌词：先接收用户提供的歌词及手工/已有时间戳。没有词级对齐时降级为句级，不编造词级事实。
- Hero Song：允许预计算并缓存 Pitch、歌词时间戳和提示。
- Coach：先按结构化事实生成模板建议，之后再接 LLM。

### 暂缓且不阻塞闭环

- Demucs 人声分离模型。
- WhisperX 及其 ASR / 对齐模型。
- Basic Pitch，除非轻量 Pitch 无法满足参考旋律展示。
- 声区、真假声和专业音色分类。

## 22.3 环境与资源策略

- 使用 WSL2 Ubuntu 的 Python 3.11 项目虚拟环境 `.venv`。新增依赖先检查兼容性，避免多环境重复安装 PyTorch。
- 只有确认需要某个模型后才安装其依赖，并记录依赖、权重下载量、缓存位置、内存和推理耗时。
- `data/` 存放本地样例和输出，不提交音频及权重。
- 若模型下载或推理耗时过长，停止模型验证，用短样例/预计算数据推进接口和闭环。
- CPU 分析必须提供排队、超时、进度或失败状态，不得假装实时完成。

## 22.4 新 10 天执行计划

### Day 1 — 环境与最小音频探针

- 验证 WSL、项目虚拟环境、FFmpeg、FastAPI 和 CPU PyTorch；检查版本兼容。
- 选 10–30 秒清唱或 vocal stem，不先做人声分离。
- 用轻量 F0 工具试提 Pitch，记录耗时、静音误检和八度跳变。
- 准备带句级时间戳的歌词 JSON；词级对齐不是门槛。
- 若 Pitch 依赖仍需大量下载，使用合成正弦/人工曲线验证数据契约，不继续等待。

验收：API 环境正常；能生成带时间戳的 F0，或记录轻量方案失败及替代路线；前端可用固定 JSON 绘图。

### Day 2 — Song Profile 与上传任务

- 固定 Song Profile、PitchPoint、WordTiming 和 AnalysisJob Schema。
- 完成上传格式/大小校验、持久化、任务 ID 和状态查询。
- Pipeline 支持 Mock、轻量分析和未来模型实现替换；添加接口与 Schema 测试。

验收：上传返回可查询任务；无模型时明确表示降级/等待，不返回伪造的完成结果。

### Day 3 — 参考曲线与歌词时间轴

- 完成参考 Pitch 清洗、静音区处理和时间轴规范。
- 前端显示参考 Pitch、句级歌词并与播放进度同步。
- 为 Hero Song 准备来源清楚的预计算 Profile。

验收：样例 Profile 可稳定播放、定位句子和绘图；预计算与实时分析标记清楚。

### Day 4 — 实时用户 Pitch

- 前端实现麦克风权限、录音生命周期和浏览器端实时 Pitch。
- 处理静音、噪声、权限拒绝、设备切换和移动浏览器限制。
- 后端定义练习结果契约，不要求实时上传原始音频。

验收：用户实际唱时能看到连续 Pitch；拒绝权限时有清晰回退状态。

### Day 5 — Difference Engine v0

- 对齐参考与用户 Pitch，过滤低置信度和静音区。
- 实现 pitch_high、pitch_low；只有存在可靠时间依据时才报告节奏问题。
- 为阈值、缺失数据和边界条件添加测试。

验收：合成偏高/偏低样例结果确定；缺数据不会被解释成唱错。

### Day 6 — 唱后诊断与问题定位

- 按句聚合差异，选出最值得改的 1–3 个问题。
- 点击问题可跳转对应句子及播放区间。
- 文案只依据观测事实，风格差异不标成错误。

验收：一次跟唱后展示问题、时间范围和证据，并可跳转复听。

### Day 7 — 单句重练闭环

- 实现参考片段播放、用户重唱和再次分析。
- 对比两次同一句的可用指标，显示改善、未改善或数据不足。
- 保存 attempt；此日不要求接入 LLM。

验收：前后结果真实来自分析数据，能走完单句重练。

### Day 8 — Memory 与结构化 Coach

- SQLite 保存 PracticeSession、PracticeIssue 和弱点摘要。
- 根据重复出现的客观问题生成个性化建议。
- Coach 可先用模板，后接 LLM；输入输出使用固定 Schema。

验收：重复问题能被记住，建议可追溯到历史事实。

### Day 9 — 可选重模型评估与泛化

- 测试中文/英文、清唱/伴奏、短/长音频，记录轻量方案边界。
- 只挑一个能解决当前差距的模型试装（Demucs 或 WhisperX），不同时全装。
- 比较效果、CPU 耗时、下载量、内存与缓存体积；无明显收益则不接入。
- 验证新歌失败、排队、缓存和降级流程。

验收：哪些是真实实时、哪些是预计算均透明；是否引入重模型有数据依据。

### Day 10 — Freeze 与演示稳定性

- 冻结新功能，只修 Bug、加载/错误状态、缓存和性能。
- 确保 Hero Song 完整演示：跟唱 → 差异 → 单句重练 → 改善 → Memory。
- 用临时上传歌曲演示当前真实可支持的路径，不承诺未完成的自动分离/词级对齐。
- 在目标手机浏览器和同一网络测试麦克风、播放、布局与 API 可达性。

验收：2–3 分钟内稳定完成教学闭环；数据来源和分析耗时透明；重模型未完成不阻塞 Demo。

## 22.5 重型模型决策门

安装每个模型前先回答：

1. 它解决哪个当前阻塞的用户体验问题？
2. 能否用短 vocal stem、用户歌词、缓存或轻量算法先完成 Demo？
3. 安装包、权重、额外依赖和首次推理耗时分别多少？
4. CPU 延迟是否可接受，超时是否有回退？
5. 短样例效果是否有可见提升，而不只是增加技术复杂度？

没有明确收益就暂缓下载。此计划降低模型依赖和现场推理风险，但不改变产品最终要逐步实现任意歌曲自动理解的方向。

