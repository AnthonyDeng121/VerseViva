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

**VerseViva 是一个 AI 外语歌曲演唱教练，帮助用户看见并听懂原唱在真实演唱中如何省略、合并或改变声音，再通过逐句反馈真正唱出来。**

品牌表达：

> 听懂每一句，唱活每一首。

产品表达：

> 不只告诉你歌词怎么读，而是教你在歌里怎么唱。

## 1.3 核心用户问题

用户可能认识歌词、查过音标，音准也基本正确，但唱出来仍然“不像歌”：

- 知道原唱“吞了音”，却不知道具体是哪个字母或音素没有释放
- 把跨词的相同辅音发了两遍，听起来生硬
- 听到连读后的新声音，却无法还原它由哪两个音融合而来
- 只会模仿吞音、合并、同化等现象，不理解嘴唇、舌位和气流动作
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

分析对象不是脱离旋律的标准口语规则，而是某一版原唱中实际可听见、可定位、可模仿的语流变化：

- consonant elision：具体哪个辅音在本次演唱中没有清楚出现
- unreleased stop：辅音形成闭塞但没有独立释放
- identical consonant merging：跨词的相同辅音共享一次发音动作
- coalescent assimilation：相邻音融合成新的听感，例如 `/t/ + /j/` 接近 `/tʃ/`
- resyllabification：前词尾音进入下一词的起始动作
- vowel linking：元音边界出现可观察的连接动作
- phrase timing / pitch / energy：只作为定位、对齐和验证上述现象的辅助证据

“两个词时间上挨得近”不自动等于连读；只有跨词边界发生了可描述、可模仿的发音动作共享或音变，才显示连读类标记。日常口语里的“功能词必弱读、内容词必重读”不得直接作为歌曲诊断规则；`can` 可以因本次旋律被突出，`want` 也可以被快速带过。

### 双层教学界面

演唱主界面只显示歌词与语言无关的字符标记，不在歌词行旁直接堆叠中文标签：

```text
bad  bad‿do  you  want‿me
  ×    └─┘          ×
```

- `×`：对应字母或音素在本次原唱中没有清楚出现或释放
- `‿`：跨词发生连续的发音动作；不能仅凭时间接近添加
- `└─┘`：两个字符或音素共享、合并或融合为一个动作
- 其他符号必须在设计系统中有唯一、稳定的含义

用户展开某一句或点击标记后，才显示中文解释、发音动作和下一遍练习建议。标记层与解释层必须在 Schema 中分离，以便未来韩语等语言复用同一套交互，而不把中文写死在歌词渲染中。

### 不同不等于错误

原唱是参考演绎，不是唯一正确答案。必须区分：

- 可观察问题：目标音是否出现或释放、相邻音是否发生合并或融合、用户是否额外发出了参考演唱中没有的音、歌词漏唱、起止时机偏离
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
- 候选省音、未释放、相同辅音合并、融合音变与再音节化提示
- 可播放和可解释的 Song Language Profile

## 3.2 AI 能听见用户真正唱出来的语言差异

第一版优先识别：

- `expected_elision_realized`：参考中未清楚出现的音，用户进行了独立释放
- `identical_consonants_separated`：参考中共享一次动作的同辅音，用户发成两次
- `coalescent_assimilation_missing`：参考中发生融合的相邻音，用户仍逐个发出；可靠时才输出
- `target_phoneme_omitted`：参考中清楚存在的目标音被用户遗漏；可靠时才输出
- `insufficient_data`：音素证据不足、伴奏遮蔽或对齐不可靠时诚实返回

词间间隔、时值、能量和 Pitch 可以继续计算，但只用于定位音素窗口、置信度控制和辅助解释，不能单独把“间隔小”包装成连读。

音高差异继续计算，但只用于对齐、置信度控制和辅助解释，不作为首页核心卖点。

## 3.3 AI 能教用户改一处具体问题

```text
发现 want 的 `t` 在参考中未清楚释放，而用户单独弹出了 `t`
→ 听原唱
→ 0.75× 慢速听
→ 只练这一小段
→ 用户再唱
→ 比较同一个目标音的释放证据
→ 明确显示 improved / unchanged / regressed / insufficient_data
```

## 3.4 AI 能记住长期语言演唱弱点

例如：

```json
{
  "consonantElision": {"count": 6, "recentImprovement": 0.34},
  "identicalConsonantMerging": {"count": 4},
  "coalescentAssimilation": {"count": 5}
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

用户首先看到的是字符标记，而不是中文标签或声学工程数据：

```text
bad  bad‿do  you  want‿me
  ×    └─┘          ×
```

支持：

- 原速听
- 慢速听
- 只听人声
- 按句循环
- 点击标记或展开句子后查看中文解释、发音动作与练习建议

## Step 3：跟唱与录制

- 播放参考歌曲或人声片段
- 录制用户演唱
- 保留录音、用户词级时间轴与必要的声学特征
- Pitch 曲线可存在，但不占据主要视觉层级

## Step 4：唱后诊断

不要先给总分。优先显示：

> 这次最值得改的一处语言表达

示例：

> `want` 的 `t` 在参考演唱中没有清楚释放；你单独弹出了这个音。下一遍唱完 `wan-` 后直接闭唇进入 `me`。

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
       Pitch   Energy   Alignment      G2P/phonology
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
- 目标音素窗口、辅音闭塞与释放候选
- 音素的存在、缺失、合并与融合证据
- 词间无声或低能量间隔（辅助证据）
- 时值比例（辅助证据）
- 起音和句段边界
- Pitch、Note、能量等辅助特征
- 用户与参考的可比较帧

LLM 负责：

- 根据歌词、G2P 与语言规则提出候选音变，不得直接确认声学事实
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
      "lyrics": "How bad bad do you want me",
      "words": [],
      "pitchContour": [],
      "languageHints": [
        {
          "id": "hint_want_t",
          "type": "consonant_elision",
          "startWordIndex": 5,
          "endWordIndex": 6,
          "startSeconds": 14.1,
          "endSeconds": 14.5,
          "source": "human_curated",
          "confidence": 0.95,
          "underlyingPhonemes": ["t"],
          "observedPhonemes": [],
          "marks": [
            {
              "symbol": "×",
              "startCharIndex": 22,
              "endCharIndex": 22,
              "placement": "below"
            }
          ],
          "details": [
            {
              "locale": "zh-CN",
              "explanation": "原唱没有清楚释放 want 末尾的 t。",
              "action": "唱完 wan 后直接闭唇进入 me，不要额外弹出 t。"
            }
          ],
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
  "type": "expected_elision_realized",
  "sentenceId": "sentence_01",
  "startWordIndex": 3,
  "endWordIndex": 4,
  "startSeconds": 14.1,
  "endSeconds": 14.7,
  "metrics": {
    "phoneme": "t",
    "referenceReleaseConfidence": 0.12,
    "userReleaseConfidence": 0.86
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
- 至少一种目标辅音的“参考未清楚释放、用户独立释放”检测
- 至少一种跨词音素合并或融合的结构化标记
- 结构化 Language Issue
- 单句重练
- 前后两遍使用同一指标比较
- 基于事实的 Coach 文案

## P1 — 强化差异化

- 更多省音、未释放、相同辅音合并与融合音变
- phrase timing（只作为音变定位与练习的辅助能力）
- 用户长期弱点与趋势
- 今日练习建议
- 自动生成候选语言提示并人工快速校正
- 歌词翻译与歌曲含义（不能挤占 P0）

## P2 — 后续探索

- 全量音素准确率评分
- 韩语等语言的音变规则与 G2P Adapter（复用字符标记 + 展开详情 Schema）
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
- 人工标注这些句子中具体字母/音素的省略、未释放、相同辅音合并与融合音变候选
- 从参考人声中定位目标音素窗口，检查闭塞、释放、能量与频谱证据
- 制作一个“参考音变处理 vs 逐字母清楚发音”的合成或人工录制对照

验收：

- 至少一个 `want‿me` 类样例能定位到具体字符，并输出可检查的目标音释放证据
- 标记和指标与音频听感方向一致
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
- `×`、`‿`、合并桥等纯字符标记的视觉表达，歌词主界面不直接显示中文标签
- 原速、0.75×、只听人声、按句循环
- 点击标记或展开句子后才显示中文解释与发音动作
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

- 实现 `expected_elision_realized`
- 实现一个可靠的 `identical_consonants_separated` 或 `coalescent_assimilation_missing`
- 时间、能量、频谱与对齐只作为目标音素判断的证据
- 建立纯函数接口、阈值配置和 Debug Evidence
- 使用合成样例与真实样例共同测试

验收：

- 参考音变处理和逐字母清楚发音有确定、可重复的不同结果
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

- 真实完成一次“额外释放目标辅音 → 不再独立释放”或同类可观察改善
- UI 不用虚构综合分数表达进步

## Day 7 — Coach & Second Language Feature

目标：把事实转化成清晰、克制、可执行的教学。

- 定义严格的 Coach Structured Output
- 输入只包含事实、歌词、提示和历史摘要
- 增加第二种可靠音变：优先相同辅音合并，其次 `/t/ + /j/` 等融合音变
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

- 多次辅音省略或合并问题形成长期弱点
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
→ 看见原唱在具体字符上的省音 / 合并 / 融合标记
→ 听原唱这一句
→ 用户唱
→ 指出一个具体语言差异
→ 单句重练
→ 显示同一指标真实改善
→ Coach 用人话解释
→ Memory 记录成长
```

---

# 12. Codex 工作方式

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

# 13. Demo 成功标准

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
