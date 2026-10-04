# VerseViva 声声不息 — Project Context / AGENTS.md

> 本文件是 VerseViva 的产品与实现上下文源文件。任何进入仓库的开发者或 AI Agent，都应先阅读本文，再决定实现方案。
>
> VerseViva 继承自 VocalCompass 的音频分析底座，但已经改变产品方向：音准比较不再是主卖点，而是支持“外语歌曲演唱教学”的基础证据。

---

# 1. 产品定义

## 1.1 名称

- 英文名：**VerseViva**
- 中文名：**声声不息**
- 比赛展示全称：**VerseViva 声声不息 — AI 外语歌曲演唱教练**

`Verse` 代表歌词、乐句与语言；`Viva` 代表鲜活、生命力与对音乐的热爱。

当前名称用于 TME 比赛与 Demo。正式商业化前必须重新完成商标、域名、应用商店与社交账号检索。

## 1.2 一句话

**VerseViva 是一个 AI 外语歌曲演唱教练，帮助用户听懂原唱如何把语言放进旋律里，并通过逐句反馈真正唱出来。**

品牌表达：

> 听懂每一句，唱活每一首。

产品表达：

> 不只告诉你歌词怎么读，而是教你在歌里怎么唱。

## 1.3 核心用户问题

用户可能认识歌词、查过音标，音准也基本正确，但唱出来仍然“不像歌”：

- 每个词彼此断开，像逐词朗读
- 重音位置不对，整句没有推进感
- 功能词唱得过重、过长
- 吞音、弱读、连读只会模仿，无法理解
- 知道自己“不像原唱”，却不知道具体差在哪里
- 看完提示以后没有逐句重练，也无法确认第二遍是否改善

VerseViva 要完成：

```text
选择一首外语歌
→ 看懂原唱的语言处理
→ 听见自己的实际差异
→ 获得一个具体可执行的建议
→ 单句重练
→ 用同一指标比较前后两遍
→ 看见改善并形成长期记忆
```

---

# 2. 产品边界与差异化

## 2.1 我们不做什么

VerseViva 不是：

- 全民 K 歌的音准评分替代品
- 通用英语学习 App
- 只展示翻译、音标或谐音的歌词工具
- 专业声乐医学诊断系统
- 用一个总分结束体验的 K 歌评分器

## 2.2 我们回答的独特问题

```text
K 歌产品：你唱得准不准？
歌词/翻译产品：这句是什么意思、怎么念？
VerseViva：原唱怎样把这句话唱进旋律，你实际唱成了什么，下一遍怎么改？
```

## 2.3 最重要的产品原则

### Language in music

分析对象不是脱离旋律的标准口语，而是语言在歌曲中的真实处理：

- linking：词与词如何连接
- stress：句中哪些词或音节被突出
- reduction：功能词如何缩短、弱化
- elision：哪些音可能被省略或融合
- phrase timing：歌词如何占据旋律时值
- phrasing：一整句如何连续表达，而不是逐词拼接

### 不同不等于错误

原唱是参考演绎，不是唯一正确答案。必须区分：

- 可观察问题：不必要的词间停顿、重音位置明显偏离、歌词漏唱、起止时机偏离
- 风格差异：音色、力度、尾音、真假声或情绪处理不同

对风格差异只能描述，不得使用“唱错了”。

### 事实先于解释

```text
Audio / Algorithm
        ↓
observable facts
        ↓
structured issue
        ↓
LLM coaching
```

LLM 只能解释已有事实，不得凭感觉生成毫秒、cents、音素准确率或声学结论。

---

# 3. Demo 必须证明的四件事

## 3.1 AI 能理解原唱的语言演唱方式

对一首英文歌生成：

- 人声分离结果
- 句级、词级时间轴
- 旋律与 Note/Pitch 参考
- 候选连读、重读、弱读与乐句提示
- 可播放和可解释的 Song Language Profile

## 3.2 AI 能听见用户真正唱出来的语言差异

第一版优先识别：

- `linking_gap`：应连续的词之间出现明显停顿
- `stress_mismatch`：突出位置与参考演唱明显不同
- `function_word_overemphasis`：功能词相对过重或过长
- `phrase_timing_early`
- `phrase_timing_late`
- `lyric_omission`：可靠时才输出

音高差异继续计算，但只用于对齐、置信度控制和辅助解释，不作为首页核心卖点。

## 3.3 AI 能教用户改一处具体问题

```text
发现 with‿you 中间断开
→ 听原唱
→ 0.75× 慢速听
→ 只练这一小段
→ 用户再唱
→ 比较词间停顿或连续性
→ 明确显示 improved / unchanged / regressed / insufficient_data
```

## 3.4 AI 能记住长期语言演唱弱点

例如：

```json
{
  "linkingGap": {"count": 6, "recentImprovement": 0.34},
  "stressMismatch": {"count": 4},
  "functionWordOveremphasis": {"count": 5}
}
```

Memory 只能从真实 PracticeAttempt 聚合，不得虚构用户进步。

---

# 4. 核心体验

## Step 1：选择英文歌曲

- Hero Song：预缓存完整产物
- 临时上传：用于证明不是写死歌曲
- 第一阶段只正式承诺英文，其他语言属于扩展方向

## Step 2：理解原唱

用户看到的是教学标记，而不是声学工程数据：

```text
I wanna‿be WITH‿YOU toNIGHT
       连读      连读       重音
```

支持：

- 原速听
- 慢速听
- 只听人声
- 按句循环
- 点击提示查看简短解释

## Step 3：跟唱与录制

- 播放参考歌曲或人声片段
- 录制用户演唱
- 保留录音、用户词级时间轴与必要的声学特征
- Pitch 曲线可存在，但不占据主要视觉层级

## Step 4：唱后诊断

不要先给总分。优先显示：

> 这次最值得改的一处语言表达

示例：

> `with you` 原唱几乎一口气带过；你在两个词之间停顿约 180ms，所以听起来更像逐词朗读。

每条问题必须包含：

- 对应句子和词
- 音频时间范围
- 问题类型
- 可观察指标与证据
- 置信度
- 一条可执行建议
- “练这一句”入口

## Step 5：单句重练

```text
听参考
→ 看语言提示
→ 跟唱
→ 分析
→ 前后比较
→ 再试一次
```

## Step 6：长期成长

- 最近反复出现的语言问题
- 哪一种问题正在改善
- 今天推荐练哪一句或哪一类现象
- 不累计羞辱性的“失败次数”，强调练习和改善趋势

---

# 5. 技术原则

## 5.1 已有底座继续保留

VocalCompass 阶段已经跑通并验证：

```text
Song Audio
→ Demucs vocal stem
→ Basic Pitch notes / continuous contour
→ WhisperX sentence and word alignment
→ Song Profile
```

这些能力不删除。它们在 VerseViva 中成为 Language Coaching Pipeline 的输入。

## 5.2 新 Pipeline

```text
                         Song Audio
                              │
                  ┌───────────┴───────────┐
                  ↓                       ↓
             Vocal Stem                Lyrics
                  │                       │
          ┌───────┼────────┐              │
          ↓       ↓        ↓              ↓
       Pitch   Energy   Alignment      Text/G2P
          │       │        │              │
          └───────┴────────┴──────┬───────┘
                                  ↓
                     Song Language Profile
                                  │
                   ┌──────────────┴──────────────┐
                   ↓                             ↓
             Reference clip                User recording
                   │                             │
                   └──────────────┬──────────────┘
                                  ↓
                      Language Difference Engine
                                  ↓
                     Structured coaching facts
                                  ↓
                         Coach + Practice Loop
```

## 5.3 专用分析与 LLM 分工

算法或音频模型负责：

- 词和句子的开始、结束时间
- 词间无声或低能量间隔
- 时值比例
- 起音和句段边界
- Pitch、Note、能量等辅助特征
- 用户与参考的可比较帧

LLM 负责：

- 根据歌词提出候选语言现象
- 用初学者能懂的中文解释结构化事实
- 生成下一遍的动作建议
- 结合历史弱点调整建议优先级

## 5.4 语言标注必须可追溯

每个提示要区分来源：

- `acoustic_observed`：声学数据直接支持
- `text_rule_candidate`：文本规则或 G2P 推导，尚需声学确认
- `llm_suggestion`：模型建议，只能作为辅助
- `human_curated`：Hero Song 人工校对

不允许把 LLM 猜测伪装成声学事实。

---

# 6. 核心数据结构

## 6.1 Song Language Profile

```json
{
  "songId": "song_xxx",
  "title": "Example",
  "language": "en",
  "durationSeconds": 45.5,
  "sentences": [
    {
      "id": "sentence_01",
      "startSeconds": 12.4,
      "endSeconds": 16.2,
      "lyrics": "I wanna be with you tonight",
      "words": [],
      "pitchContour": [],
      "languageHints": [
        {
          "type": "linking",
          "startWordIndex": 3,
          "endWordIndex": 4,
          "display": "with‿you",
          "source": "human_curated",
          "confidence": 0.95,
          "evidence": {}
        }
      ]
    }
  ]
}
```

## 6.2 Language Issue

```json
{
  "type": "linking_gap",
  "sentenceId": "sentence_01",
  "startWordIndex": 3,
  "endWordIndex": 4,
  "startSeconds": 14.1,
  "endSeconds": 14.7,
  "metrics": {
    "referenceGapMs": 24,
    "userGapMs": 182
  },
  "severity": "medium",
  "confidence": 0.88,
  "evidenceRefs": []
}
```

## 6.3 Practice Attempt

必须保存：

- sentence ID
- attempt number
- 录音或可追溯音频引用
- 输入特征
- 检测到的问题
- 核心指标
- 与上一遍的比较结果
- 分析版本

---

# 7. 技术栈

## Frontend

- React
- TypeScript
- Vite
- Web Audio API / AudioWorklet
- Canvas 2D（只在确实需要曲线时使用）

## Backend

- Python 3.11+
- FastAPI
- SQLite（Demo）

## Audio / AI

- Demucs：人声分离
- WhisperX：ASR 与词级时间对齐
- Basic Pitch：Note、Pitch 与辅助对齐证据
- G2P / pronunciation lexicon：英文音素与音节候选
- 规则与声学特征：第一版语言差异检测
- LLM structured output：解释与教学建议

优先使用成熟方案；不训练自有模型。

---

# 8. 功能优先级

## P0 — 比赛 Demo 不成立就缺失的能力

- 英文歌曲上传与预缓存 Hero Song
- 人声分离
- 句级、词级歌词时间轴
- Song Language Profile
- Hero Song 人工校对的语言提示
- 原速、慢速、人声与按句循环播放
- 麦克风录制用户演唱
- 用户词级时间对齐
- `linking_gap` 检测
- 至少一种重音或时值差异检测
- 结构化 Language Issue
- 单句重练
- 前后两遍使用同一指标比较
- 基于事实的 Coach 文案

## P1 — 强化差异化

- reduction / function-word overemphasis
- phrase timing
- 用户长期弱点与趋势
- 今日练习建议
- 自动生成候选语言提示并人工快速校正
- 歌词翻译与歌曲含义（不能挤占 P0）

## P2 — 后续探索

- 细粒度音素纠音
- 日语、韩语、粤语等语言
- 情绪和风格模仿
- 音色、真假声、声区
- 社区、分享、排行

---

# 9. 明确不做

比赛阶段不投入：

- 与全民 K 歌竞争综合评分
- 自研声学基础模型
- 所有英语音素的母语级评分
- 一开始支持多语言
- 复杂登录、支付、社交或教师后台
- 专业医学级声带、音色或声区判断
- 无事实来源的 AI 自由诊断
- 为架构漂亮而增加复杂微服务

---

# 10. 迁移现状

## 已完成且复用

- FastAPI 基础工程
- 上传校验、任务状态与失败持久化
- 独立 `song_id` / `job_id` 与工作目录
- Demucs、Basic Pitch、WhisperX Adapter
- Basic Pitch / WhisperX Converter
- Song Profile 存储与查询
- 连续 Pitch 清洗、降采样与稳健音域
- Difference Engine v0 的 cents 与参考 Pitch 插值
- 39 项后端测试与 Ruff 验证（迁移前基线）

## 尚未完成

- 可用的前端产品流程
- Song Language Profile Schema
- 英文 G2P / 音节结构
- 参考演唱语言特征提取
- 用户演唱上传与对齐
- Language Difference Engine
- 单句重练 UI 与比较
- Coach、Memory 与最终比赛 Demo

## 已知性能事实

WSL2 + CPU 环境下，45.5 秒真实音频全链路曾耗时约 15 分钟，其中 WhisperX 占主要部分。因此：

- Hero Song 必须预缓存
- 临时上传使用短片段
- 页面必须显示真实任务阶段
- 模型预热、缓存与更快推理环境属于演示稳定性工作

---

# 11. 重新规划的十天开发计划

本计划从 VerseViva 转向之日重新计时。每一天必须产出可验收结果，不按“写了多少代码”判断完成。

## Day 1 — Product Reset & Language Spike

目标：证明一个最小语言现象可以从真实音频中被观察。

- 完成品牌、README、Schema 与代码命名迁移
- 确定英文 Hero Song 和 2–3 个目标句
- 人工标注这些句子的 linking / stress / reduction 候选
- 从参考人声中测量词间间隔、词时值和能量包络
- 制作一个“连读 vs 明显停顿”的合成或人工录制对照

验收：

- 至少一个 `with‿you` 类样例能输出可检查的 reference/user gap 指标
- 指标与音频听感方向一致
- 没有使用 LLM 虚构数值

## Day 2 — Song Language Profile

目标：把歌曲分析产物升级为前端可消费的语言教学 Profile。

- 定义 `LanguageHint`、来源、证据与置信度
- 为现有 Sentence / WordTiming 增加语言提示
- 增加英文文本规范化、词索引与基础 G2P/音节信息
- Hero Song 提示支持人工校对与缓存
- 保持旧 Song Profile 兼容或提供显式 Schema 迁移

验收：

- API 可返回完整 Hero Song Language Profile
- 每条提示能定位到具体词和音频区间
- Schema 测试覆盖空值、非法索引和来源类型

## Day 3 — Learn the Original UI

目标：用户能在手机上看懂并听懂原唱的一句。

- 歌词逐词渲染与播放高亮
- linking、stress、reduction 的视觉表达
- 原速、0.75×、只听人声、按句循环
- 点击提示显示一句人话解释
- 参考 Pitch 降为辅助视图，不占据首页中心

验收：

- 手机浏览器可播放、拖动、循环并保持歌词同步
- 用户能在 30 秒内理解一处语言现象

## Day 4 — User Recording & Alignment

目标：用户能唱一句，并得到可靠的词级时间依据。

- 封装 AudioRecorder
- 处理权限拒绝、静音、后台切换与录音截断
- 提交用户句段录音
- 对齐用户音频与目标句歌词
- 保存对齐质量、未识别词和可比较区间

验收：

- 桌面和至少一台目标手机完成录音上传
- 失败或低置信度时诚实返回 `insufficient_data`

## Day 5 — Language Difference Engine v0

目标：稳定检测最小的差异化能力。

- 实现 `linking_gap`
- 实现 `phrase_timing_early/late`
- 尝试一个可靠的 `stress_mismatch` 或时值比例问题
- 建立纯函数接口、阈值配置和 Debug Evidence
- 使用合成样例与真实样例共同测试

验收：

- 明显连读和明显断开有确定、可重复的不同结果
- 每个问题含指标、置信度和证据引用
- 没有可靠依据时不输出

## Day 6 — Sentence Practice Loop

目标：完成 VerseViva 的核心教学闭环。

- 从问题卡进入目标句
- 听参考 / 慢速听 / 录制 / 分析 / 再试
- 保存 PracticeAttempt
- 用同一指标比较两遍
- 输出 improved / unchanged / regressed / insufficient_data

验收：

- 真实完成一次“180ms → 约 50ms”或同类可观察改善
- UI 不用虚构综合分数表达进步

## Day 7 — Coach & Second Language Feature

目标：把事实转化成清晰、克制、可执行的教学。

- 定义严格的 Coach Structured Output
- 输入只包含事实、歌词、提示和历史摘要
- 增加第二种可靠语言现象：优先 stress，其次 function-word duration
- Structured Output 失败时使用规则模板降级

验收：

- Coach 不产生输入中不存在的数值
- 建议能明确告诉用户下一遍做什么

## Day 8 — Memory & Personalization

目标：让系统记住用户反复出现的问题与真实改善。

- SQLite 保存 session / attempt / issue
- 聚合问题出现次数、最近时间与改善趋势
- 首页生成“今天建议练什么”
- 只传结构化历史摘要给 Coach

验收：

- 多次 linking 问题形成长期弱点
- 改善后趋势能够更新，而不是只累计失败

## Day 9 — Generalization & TME Story

目标：停止加功能，验证泛化和比赛叙事。

- 测试至少 3 首英文歌
- Hero Song 完整链路
- 备用 Hero Song
- 临时短片段上传
- 记录每阶段耗时、失败原因与缓存命中
- 明确展示与 K 歌评分、歌词翻译产品的区别

验收：

- 不是只对一个固定句子写死
- 至少两首歌能生成可用语言提示
- 失败路径可恢复

## Day 10 — Freeze & Rehearsal

只允许：

- Bug Fix
- Loading / Error Handling
- Cache / Fallback
- 性能与手机适配
- 演示文案和讲述顺序

最终 2–3 分钟流程：

```text
选择英文歌
→ 看见原唱 linking / stress
→ 听原唱这一句
→ 用户唱
→ 指出一个具体语言差异
→ 单句重练
→ 显示同一指标真实改善
→ Coach 用人话解释
→ Memory 记录成长
```

---

# 12. 双人分工建议

## A — 体验与浏览器音频主责

- React / Mobile H5
- 歌词与语言提示 UI
- 播放、循环、慢速与录音
- 实时状态和练习闭环
- 手机适配与可用性测试

## B — 音频与语言分析主责

- FastAPI / Pipeline
- Alignment / G2P / acoustic features
- Language Difference Engine
- Coach structured output
- 存储、缓存与测试

共同负责：

- Hero Song 人工校对
- 阈值调试
- 真实用户录音
- Demo 稳定性
- 比赛叙事

任何一方都不应只负责样式或只包办全部 AI。

---

# 13. Codex 工作方式

1. 修改前先读本文与相关代码。
2. 先说明当前任务如何服务语言教学闭环。
3. 优先 simple + stable + explainable。
4. 所有 AI 输出尽量使用 JSON Schema。
5. 所有诊断必须能追溯到音频、时间戳或结构化事实。
6. 不擅自恢复以音准评分为中心的旧方向。
7. 不因 P2 功能阻塞 P0。
8. 修改 Schema、API 或 Pipeline 时必须补测试。
9. 不把 Hero Song 的人工标注伪装成完全自动能力。
10. 如果一个功能不能让用户更清楚“这一句语言为什么这样唱、下一遍怎么改”，比赛阶段先不做。

---

# 14. Demo 成功标准

十天后，如果能稳定完成以下流程，即视为 VerseViva Demo 成功：

```text
系统展示一处原唱语言处理
→ 用户能听懂这个现象
→ 用户实际唱一句
→ 系统定位具体词和可观察差异
→ 用户点击练这一句
→ 第二遍同一指标发生真实改善
→ Coach 给出有事实依据的解释
→ 系统记住这一类长期弱点
```

最终判断标准：

> **它有没有证明：VerseViva 教的不是“单词怎么念”，而是“语言如何成为歌”？**
