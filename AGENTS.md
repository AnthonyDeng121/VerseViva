# VerseViva 声声不息 — Project Context / AGENTS.md

> 本文件是 VerseViva 的产品与实现上下文源文件。任何进入仓库的开发者或 AI Agent，都应先阅读本文，再决定实现方案。
>
> VerseViva 继承自 VocalCompass 的音频分析底座，但已经改变产品方向：音准比较不再是主卖点，而是支持“外语歌曲演唱教学”的基础证据。

---

# 1. 产品定义

## 1.1 名称

- 英文名：**VerseViva**
- 中文名：**声声不息**
- 比赛展示全称：**VerseViva 声声不息 — AI 外语歌曲演唱与分轨练习教练**

`Verse` 代表歌词、乐句与语言；`Viva` 代表鲜活、生命力与对音乐的热爱。

当前名称用于 TME 比赛与 Demo。正式商业化前必须重新完成商标、域名、应用商店与社交账号检索。

## 1.2 一句话

**VerseViva 是一个 AI 外语歌曲演唱与分轨练习教练，帮助用户看懂原唱如何处理声音与 Vocal 层次，分别练习主唱、和声和重叠句，再把它们叠成完整演唱。**

品牌表达：

> 听懂每一句，唱活每一首。

产品表达：

> 不只告诉你歌词怎么读，而是教你在歌里怎么唱。

扩展表达：

> 一个人，也能把一首歌里的多层人声唱完整。

## 1.3 核心用户问题

用户可能认识歌词、查过音标，音准也基本正确，但唱出来仍然“不像歌”：

- 知道原唱“吞了音”，却不知道具体是哪个字母或音素没有释放
- 把跨词的相同辅音发了两遍，听起来生硬
- 听到连读后的新声音，却无法还原它由哪两个音融合而来
- 只会模仿吞音、合并、同化等现象，不理解嘴唇、舌位和气流动作
- 知道自己“不像原唱”，却不知道具体差在哪里
- 看完提示以后没有逐句重练，也无法确认第二遍是否改善
- 主唱未结束时，和声、回应或下一句已经进入，一个人无法一遍同时完成
- 普通 K 歌只有一条滚动歌词和一次录音，不告诉用户当前该唱主 Vocal 还是次 Vocal
- 想补唱和声或背景句，却无法按同一时间轴反复录制并叠加回放

VerseViva 要完成：

```text
选择一首外语歌
→ 看懂原唱的语言处理与 Vocal 层次
→ 听见自己的实际差异
→ 获得一个具体可执行的建议
→ 单句重练
→ 用同一指标比较前后两遍
→ 分别录制一遍无法同时完成的次 Vocal
→ 在同一时间轴叠唱并回放
→ 看见改善并形成长期记忆
```

---

# 2. 产品边界与差异化

## 2.1 我们不做什么

VerseViva 不是：

- 全民 K 歌的音准评分替代品
- 完整数字音频工作站（DAW）或专业混音软件
- 承诺自动把任意混合人声完美拆成独立主唱、和声和背景人声的分轨工具
- 通用英语学习 App
- 只展示翻译、音标或谐音的歌词工具
- 专业声乐医学诊断系统
- 用一个总分结束体验的 K 歌评分器

## 2.2 我们回答的独特问题

```text
K 歌产品：你唱得准不准？
歌词/翻译产品：这句是什么意思、怎么念？
VerseViva：原唱具体改变了哪些声音、有哪些同时发生的 Vocal；你实际唱成了什么，下一遍该改或补唱哪一层？
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

### Vocal 编排也是可学习结构

歌曲里同时发生的主唱、和声、背景句、回应、ad-lib、叠唱和跨句重叠，不应被压成一条无法实际演唱的歌词。主 / 次双轨是面向用户的默认教学视图，能覆盖大部分学习场景；底层模型必须允许同一时间轴上存在多个 Vocal Part，且同一 Vocal Part 可以保留多个非破坏性 Overdub Take。双轨界面不等于把工程限制为两条音轨。系统使用共享时间轴上的两条教学 lane：

- `primary`：当前主要演唱线，通常是 lead vocal
- `secondary`：与主线不能同时完成，或适合单独补录的 harmony / backing vocal / response / ad-lib / double / overlap

双轨歌词默认左右并列：左侧 primary，右侧 secondary。移动端仍保留左右语义，必要时通过紧凑字号、水平滚动或聚焦某一轨保证可读性，不自动改成上下布局。每一段必须显示角色和进入时机，用户可单独练习、录制、静音和回放，再将多次 Take 按同一时间轴叠加。每条 Take 都必须可独立调节前后偏移和音量。

用户不只能录制系统检测到的重叠声部：他们可以在任意歌曲区间自行选择叠录片段并追加多个 Take。人工或模型标注的重叠 Vocal Part 是高质量的练习入口和时机参考，不是录音权限边界。

第一版不假装拥有完美的自动声部分离：Demucs 的 vocals stem 通常仍包含所有人声层。Gemini 等音频理解模型可以提出和声、主副声轨重叠的时间候选。当前比赛 Demo 所采用歌词来源中的括号内容已经过产品负责人/人工验证，可直接作为确定的 secondary / response / ad-lib 声部文本，并保留 `lyrics_provider` 来源；Gemini 只负责核查该确定文本在音频中的出现与时间，不负责重新判断它是不是声部。确定声部文本不等于已经获得独立音轨；没有独立 stem 时仍不得提供或声称“只听和声”。

### 通用音素操作与语言现象分层

核心 Schema 不按语言无限增加固定枚举。任何英语、韩语或其他语言现象，先表示为一个或多个通用音素操作：

- `delete`：输入音消失
- `unreleased`：音仍有构形或闭塞，但没有独立释放
- `merge`：两个或多个输入音共享或融合成较少的输出音
- `substitute`：输入音在本次演唱中实现为另一音
- `insert`：出现歌词标准音素中没有的声音
- `resegment`：声音跨词或音节边界重新组织
- `lengthen` / `shorten`：音段相对延长或缩短

`phenomenon` 保存语言层名称，例如英语 `coalescent_assimilation`、韩语 `nasalization`；`transformations` 保存跨语言可比较的实际操作。一个复杂现象可以由多个 transformation 组成。新增语言时优先增加规则和解释，不修改核心操作模型。

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

# 3. Demo 必须证明的五件事

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

## 3.4 用户能把无法同时唱的 Vocal 分层完成

对 Hero Song 至少选择一处主唱与和声、回应或重叠句同时出现的片段：

```text
看主 / 次 Vocal 双轨歌词
→ 先录 primary take
→ 再录 secondary take
→ 自动按歌曲时间轴对齐
→ 分轨静音、重录或一起回放
```

验收不依赖音高评分，而是证明两个真实录音 Take 能按正确进入时机同步回放。系统必须保留录音延迟校准或偏移量，不得把明显错位包装成成功。

## 3.5 AI 能记住长期语言演唱弱点

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
- 同时发生的人声显示为主 / 次 Vocal 双轨歌词，并标明 harmony、response、ad-lib 等角色
- 可只看或循环当前 Vocal Part；没有独立音轨时不得伪装成“只听和声”

## Step 3：跟唱与录制

- 播放参考歌曲或人声片段
- 录制用户演唱
- 保留录音、用户词级时间轴与必要的声学特征
- 录音必须关联目标 sentence 和 Vocal Part，允许在同一时间轴追加 Take
- 比赛主流程不展示音高评分或 Pitch 曲线；Pitch 只保留为对齐、置信度和声部候选判断的底层证据

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

## Step 6：分轨叠唱

```text
选择 primary / secondary
→ 听参考与看进入提示
→ 戴耳机录制一个 Take
→ 校正设备录音延迟
→ 与已有 Take 同步回放
→ 静音、保留或重录这一层
```

第一版只需支持少量 Vocal Part 和 Take，不提供复杂剪辑、插件、自动调音或专业混音功能。

## Step 7：长期成长

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

这些能力不删除。它们在 VerseViva 中成为 Language Coaching 与 Vocal Arrangement Pipeline 的输入。Pitch 不再形成面向用户的评分赛道，但仍可作为内部对齐和候选证据。

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
                Song Language + Vocal Part Profile
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
               Coach + Practice Loop + Overdub Timeline
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
- 对完整人声音频和时间轴提出 Vocal Part 候选；候选不得冒充已分离声部或人工确认结果

## 5.4 语言与 Vocal Part 标注必须可追溯

每个提示要区分来源：

- `acoustic_observed`：声学数据直接支持
- `text_rule_candidate`：文本规则或 G2P 推导，尚需声学确认
- `llm_suggestion`：模型建议，只能作为辅助
- `human_curated`：Hero Song 人工校对

不允许把 LLM 猜测伪装成声学事实。

Vocal Part 另外使用：

- `acoustic_candidate`：由重叠区间、能量、Pitch 或时间轴等特征提出的候选
- `audio_model_candidate`：音频理解模型提出但尚未人工确认的候选
- `lyrics_structure_candidate`：联网歌词的括号、重复行或排版结构提出的候选，不能单独证明独立声部
- `human_curated`：Hero Song 人工确认的声部、歌词与时间范围

`candidate` 只能用于快速标注和人工复核。比赛 Demo 有一条例外：当前选定歌词来源的括号内容已经过人工验证，可直接作为确定的 secondary 文本，来源为 `lyrics_provider`，不需要再次把“是否属于次 Vocal”标成待人工复核。Gemini 只绑定 cue ID，使用 Demucs 输出的整体人声 stem 核查该确定文本是否在本次音频中可听见，并返回起止时间，不得改写、生成或否定歌词文本。Gemini 给出的时间和听感证据仍属于模型结果，可以保留置信度和时间复核状态。WhisperX 负责 primary 及可对齐文本的单词级时间戳。确定歌词声部不等于取得独立 stem；没有独立 stem 时，不能声称系统已经从参考歌曲中提取了可单独播放的和声音轨。

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
          "language": "en",
          "phenomenon": "consonant_elision",
          "transformations": [
            {
              "operation": "delete",
              "inputSegments": ["t"],
              "outputSegments": []
            }
          ],
          "startWordIndex": 5,
          "endWordIndex": 6,
          "startSeconds": 14.1,
          "endSeconds": 14.5,
          "source": "human_curated",
          "confidence": 0.95,
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

## 6.4 Vocal Part 与 Overdub Take

```json
{
  "vocalParts": [
    {
      "id": "part_harmony_01",
      "lane": "secondary",
      "role": "harmony",
      "startSeconds": 18.2,
      "endSeconds": 21.6,
      "lyrics": "example harmony line",
      "sentenceIds": ["sentence_04"],
      "source": "human_curated",
      "confidence": 1.0
    }
  ]
}
```

每个 Overdub Take 必须保存：

- take ID、session ID 与 vocal part ID
- 原始录音引用，不进行破坏性覆盖
- 歌曲时间轴上的开始时间
- 设备或本次会话的录音延迟补偿值
- gain / mute 等最小回放状态
- 创建时间与是否为当前采用版本

同一 Vocal Part 可以有多个 Take，同一 Session 也可以包含超过两个同时回放的 Take。主 / 次双轨只是歌词教学视图，不是录音数量上限。每条 Take 的 `timelineOffset` / latency compensation / manual offset 和 `gain` 必须独立保存，以支持类似全民 K 歌的前后对齐与音量调节。

Vocal Part 是参考歌曲的编排事实或候选；Overdub Take 是用户的实际录音，两者不得混为一类数据。

Overdub 功能的目标产品形态是可迁移到 TME / 全民 K 歌的演唱流程中；比赛 Demo 保持独立、简单的实现，但数据语义和交互不应锁死为仅支持两轨或固定片段。

---

# 7. 技术栈

## Frontend

- React
- TypeScript
- Vite
- Web Audio API / AudioWorklet
- 多轨回放使用共享 AudioContext 时钟与显式 latency offset
- Canvas 2D 只用于确有必要的时间轴，不用于恢复 Pitch 曲线主界面

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
- Audio LLM：候选音变与 Vocal Part 复核实验，不作为无人工校对的唯一事实源

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
- Hero Song 人工校对的 primary / secondary Vocal Part
- 主 / 次 Vocal 左右双轨歌词（移动端保留左右语义）
- 至少两次分轨录音、延迟补偿、静音 / 重录与同步叠加回放

## P1 — 强化差异化

- 更多省音、未释放、相同辅音合并与融合音变
- phrase timing（只作为音变定位与练习的辅助能力）
- 用户长期弱点与趋势
- 今日练习建议
- 自动生成候选语言提示并人工快速校正
- 歌词翻译与歌曲含义（不能挤占 P0）
- 自动提出 Vocal Part 候选并提供人工快速校正
- 更多 Take、基础音量平衡与片段级重录

## P2 — 后续探索

- 全量音素准确率评分
- 韩语等语言的音变规则与 G2P Adapter（复用字符标记 + 展开详情 Schema）
- 情绪和风格模仿
- 音色、真假声、声区
- 任意歌曲的主唱 / 和声自动高质量独立 stem 分离
- 自动调音、复杂剪辑、效果器与专业混音
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
- 面向用户的 Pitch 曲线、音准总分或“唱准多少分”主流程
- 专业 DAW 级剪辑、母带、效果器、自动调音和无限轨工程

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
- Song Language Profile 1.4 与可追溯 `LanguageHint`
- CMUdict/G2P 相邻词边界候选生成
- Gemini Structured Output 受限核查 Adapter
- Audio LLM 结果到 `×`、`‿`、合并桥的确定性映射
- 上传、任务进度、原曲 / 人声播放与语言标记展开详情的前端骨架
- 《get him back!》bridge 的 WhisperX 时间锚点、歌词结构候选、可追溯 Vocal Part 缓存和左右双轨展示
- Gemini Vocal Part 严格 Structured Output 适配器（真实运行受 API 额度影响，候选不自动升级为人工事实）
- LRCLIB 无 Key 歌词检索，支持歌名 + 歌手精确检索、来源记录和匹配置信度
- 联网歌词优先、WhisperX 时间轴辅助的模糊歌词对齐；匹配窗口会扩展到完整歌词行，避免末句被截断
- 上传任务的真实阶段、错误详情、Warning、失败产物保留和原任务重试
- 页面刷新后从服务端恢复最近任务、进度、错误或已完成 Profile
- Gemini 语言分析 Prompt 已针对 `If you`、`Let you`、`want you`、`did you` 等高歧义边界加强声学证据约束
- `×`、`‿`、`└─┘` 均使用字符下方标记；中文解释只在详情层展示
- 音乐软件式歌词视图：句级自动滚动、词级时间高亮，不再按句使用独立卡片
- 原曲与人声播放器默认音量 30%
- 普通歌词 / 叠唱歌词已融合在同一个歌曲学习页面，共享播放时间轴与语言标注
- 上传歌曲支持明确的 `single_track` / `dual_track` 编排模式：联网歌词含括号走双轨，否则走单轨
- 两条编排 Pipeline 均先经过 Demucs；双轨 Gemini 核查显式使用 `vocals.wav`，而不是带伴奏原曲
- 双轨失败时保留歌词结构候选并记录 Warning；Vocal Part 产物支持任务内缓存
- Song Profile 记录 `vocalArrangementMode`，任务增加 `analyzing_vocal_parts` 阶段
- 当前回归基线：除本机 Windows 缺少 `ffprobe` 的 Day 1 真实媒体测试外，82 项后端测试通过；Ruff 与前端生产构建通过

## 尚未完成

- 完整可用并经过手机验证的前端产品流程；当前桌面骨架已可用，慢速、句循环和手机交互仍需补齐
- G2P 未登录词、缩写和多发音词的消歧
- 参考演唱语言特征提取
- 用户演唱上传与对齐
- Language Difference Engine
- 单句重练 UI 与比较
- Coach、Memory 与最终比赛 Demo
- Hero Song Vocal Part 听感人工复核与精确时间校正；自动候选已有，尚不能替代人工真值
- 浏览器录音延迟校准和多 Take 同步回放
- 真实 Gemini API 全曲成本、限流、超时与结果质量评测
- Demucs 当前只分离“整体人声 / 伴奏”，不会自动得到可独立播放的 lead / harmony stem
- 当前通用上传代码仍把括号声部保存为 `lyrics_structure_candidate` 并要求人工复核，与上述已确认产品规则不一致；下一轮代码任务必须优先改回 `lyrics_provider` 确定文本，同时只让 Gemini 的时间定位保持模型置信度

## 当前上传解析流程（2026-10-06）

```text
上传歌曲
→ 校验并创建独立 song_id / job_id
→ ffprobe 读取时长
→ Demucs 分离整体 vocals.wav 与伴奏
→ Basic Pitch 提取内部辅助特征
→ LRCLIB 按歌名 + 歌手检索歌词
→ WhisperX 对分离后整体人声进行句级、词级对齐
→ 以联网歌词为文本真值进行模糊对齐和完整行恢复
→ 检查联网歌词是否含括号
   ├─ 无括号：single_track 编排 Pipeline，不伪造 Vocal Part
   └─ 有括号：dual_track 编排 Pipeline
      → 将已人工验证的括号文本建立为 lyrics_provider 确定 secondary
      → Gemini 使用 Demucs vocals.wav 核查 secondary 在本次音频中是否可听见及其时间
      → 失败时保留确定的 secondary 文本，时间使用歌词对齐回退值并记录 Warning
→ 无论单轨或双轨，都执行 G2P 候选 + Gemini 语言现象核查
→ 生成包含 LanguageHint、VocalPart 和来源证据的 Song Profile
→ 前端在同一页面提供普通歌词 / 叠唱歌词切换和时间高亮
```

这里的 `vocals.wav` 仍包含主唱、和声、回应和 ad-lib 等所有人声层。双轨 Pipeline 当前解决的是“编排识别与教学分 lane”，不是高质量声源级主唱 / 和声分离。

## 已知性能事实

WSL2 + CPU 环境下，45.5 秒真实音频全链路曾耗时约 15 分钟，其中 WhisperX 占主要部分。因此：

- Hero Song 必须预缓存
- 临时上传使用短片段
- 页面必须显示真实任务阶段
- 模型预热、缓存与更快推理环境属于演示稳定性工作

---

# 11. 重新规划的十天开发计划

本计划从 VerseViva 转向之日重新计时。每一天必须产出可验收结果，不按“写了多少代码”判断完成。

## 当前接力顺序（下一轮开发按此执行）

### 第一步：上传链路真实验收与稳定化

- 使用至少一首无括号歌曲和一首含括号歌曲重新上传，确认分别生成 `single_track` 与 `dual_track`
- 先修正当前实现：括号内确定声部必须使用 `lyrics_provider`，不得继续保存为 `lyrics_structure_candidate` 或要求重新确认其声部身份
- 检查 LRCLIB 完整歌词、WhisperX 时间轴、Gemini 语言标注和 Vocal Part 缓存
- 验证刷新恢复、失败详情、Warning 和重试按钮
- 记录 Demucs、WhisperX、Gemini 各阶段实际耗时与 API 调用次数
- 对 Gemini 429 / 503、超时和非法 JSON 增加有限重试与明确降级，不无限等待在 82% 或新阶段

验收：两首真实歌曲都能走完全链路；双轨歌曲使用整体人声 stem 进行核查；任何失败都有具体阶段、真实原因和可恢复入口。

### 第二步：完成“理解原唱”P0 交互

- 补齐原速 / 0.75×、按句循环、点击某句跳转和只听整体人声
- 校准普通歌词与双轨歌词的滚动、高亮及移动端左右语义
- 为候选 Vocal Part 提供来源、置信度和“需人工复核”状态，不伪装为已分离和声
- 人工校对《Juno》的语言提示，并为《get him back!》bridge 校对 primary / secondary 时间

验收：手机和桌面均可在同一页面理解一处语言现象，并区分需要分次演唱的两个 Vocal lane。

### 第三步：用户单句录音与对齐

- 实现 AudioRecorder、权限与静音检测、录音上传
- 录音绑定 sentence ID、vocal part ID 和 take ID
- WhisperX 对齐用户录音；低质量时返回 `insufficient_data`
- 保存原始录音和对齐产物，刷新后可恢复

验收：用户可选择一句录制并获得可追溯的词级时间依据，失败不会覆盖旧录音。

### 第四步：最小语言差异检测与重练闭环

- 优先实现 `expected_elision_realized`
- 再选择一个可靠的相同辅音合并或 `/t/ + /j/` 融合差异
- 保存 PracticeAttempt，并用同一指标比较前后两遍
- Coach 只解释结构化事实，规则模板作为 LLM 失败降级

验收：真实完成一次“第一遍独立释放目标音，第二遍不再释放”的可重复改善展示。

### 第五步：Overdub 叠唱闭环

- 在同一歌曲学习页选择 primary / secondary 或任意时间区间
- 使用共享 AudioContext 时钟录制多个非破坏性 Take
- 保存 latency compensation、manual offset、gain、mute 和采用状态
- 支持两层真实录音同步回放、静音、重录和独立偏移

验收：两个真实 Take 在 Hero 片段的正确进入时间同步播放；没有独立 harmony stem 时只提供混合参考和进入提示。

### 第六步：泛化、Memory 与比赛冻结

- SQLite 持久化 session / attempt / issue / take
- 测试至少三首英文歌并记录准确性、性能和失败原因
- 从真实 PracticeAttempt 聚合长期弱点，不虚构改善
- 预缓存 Hero Song，完成手机验收和 2–3 分钟比赛流程

## Day 1 — Product Reset & Language Spike

目标：证明一个最小语言现象可以从真实音频中被观察。

- 完成品牌、README、Schema 与代码命名迁移
- 确定英文 Hero Song 为 Sabrina Carpenter 的《Juno》，先使用前两句，并补选一处真实 Vocal 重叠片段
- 人工标注这些句子中具体字母/音素的省略、未释放、相同辅音合并与融合音变候选
- 从参考人声中定位目标音素窗口，检查闭塞、释放、能量与频谱证据
- 制作一个“参考音变处理 vs 逐字母清楚发音”的合成或人工录制对照
- 人工记录 Hero Song 中 primary / secondary Vocal Part 的角色、歌词与进入时间

验收：

- 至少一个 `want‿me` 类样例能定位到具体字符，并输出可检查的目标音释放证据
- 标记和指标与音频听感方向一致
- 没有使用 LLM 虚构数值
- 至少找到一处适合双轨歌词和分次叠唱的真实片段；若前两句没有重叠，不得伪造

## Day 2 — Song Language & Vocal Part Profile

目标：把歌曲分析产物升级为前端可消费的语言教学与 Vocal 编排 Profile。

- 定义 `LanguageHint`、来源、证据与置信度
- 为现有 Sentence / WordTiming 增加语言提示
- 增加英文文本规范化、词索引与基础 G2P/音节信息
- Hero Song 提示支持人工校对与缓存
- 定义 `VocalPart` 的 lane、role、共享时间轴、来源与置信度
- 保持旧 Song Profile 兼容或提供显式 Schema 迁移

验收：

- API 可返回完整 Hero Song Language Profile
- 每条提示能定位到具体词和音频区间
- Schema 测试覆盖空值、非法索引和来源类型
- API 能表达时间上重叠的 primary / secondary Vocal Part

## Day 3 — Learn the Original UI

目标：用户能在手机上看懂并听懂原唱的一句。

- 歌词逐词渲染与播放高亮
- `×`、`‿`、合并桥等纯字符标记的视觉表达，歌词主界面不直接显示中文标签
- 原速、0.75×、只听人声、按句循环
- 点击标记或展开句子后才显示中文解释与发音动作
- 同时出现的 Vocal Part 使用左右双轨歌词；手机通过紧凑布局、水平滚动或单轨聚焦保持左右语义
- 不制作面向用户的 Pitch 曲线或音高评分界面

验收：

- 手机浏览器可播放、拖动、循环并保持歌词同步
- 用户能在 30 秒内理解一处语言现象
- 用户能分清同一时刻该唱的 primary 与需要补录的 secondary

## Day 4 — User Recording & Alignment

目标：用户能唱一句，并得到可靠的词级时间依据。

- 封装 AudioRecorder
- 处理权限拒绝、静音、后台切换与录音截断
- 提交用户句段录音
- 对齐用户音频与目标句歌词
- 保存对齐质量、未识别词和可比较区间
- 录音关联 sentence / vocal part / take ID，并记录浏览器报告或校准得到的延迟信息

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

## Day 8 — Vocal Layers & Overdub

目标：让一个人通过多次录制完成原歌中无法同时唱出的 Vocal 层。

- 展示 Hero Song 人工校对的 primary / secondary 双轨歌词
- Overdub Hero 片段使用 Olivia Rodrigo 的《get him back!》bridge，原始短片段位于 `data/day3/input/get him back!.mp3`
- 先录 primary take，再按同一歌曲时间轴录 secondary take
- 使用共享 AudioContext 时钟和 latency offset 同步回放
- 支持分轨静音、保留、重录和最小音量平衡
- 没有独立和声 stem 时，只提供混合参考与进入提示，不伪造 solo harmony
- 允许用户选择任意歌曲区间叠录，并对每个 Take 独立调节前后偏移与音量

验收：

- 两个真实 Take 能在目标位置同步叠加，进入时机与听感一致
- 手机窄屏仍能看清两条 Vocal，录音失败可恢复且不会覆盖旧 Take

## Day 9 — Generalization & TME Story

目标：补齐真实记忆，停止加功能，并验证泛化和比赛叙事。

- SQLite 保存 session / attempt / issue / overdub take
- 聚合语言问题出现次数、最近时间与改善趋势
- 测试至少 3 首英文歌
- Hero Song 完整链路
- 备用 Hero Song
- 临时短片段上传
- 记录每阶段耗时、失败原因与缓存命中
- 明确展示与音准 K 歌、单轨歌词和歌词翻译产品的区别

验收：

- 不是只对一个固定句子写死
- 至少两首歌能生成可用语言提示
- Hero Song 能稳定完成语言教学与双轨叠唱两段闭环
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
→ 看见一处与主唱重叠的次 Vocal
→ 分别录制两层并同步叠唱回放
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
10. 如果一个功能不能让用户更清楚“这一句为什么这样唱、当前是哪一层 Vocal、下一遍该改或补唱什么”，比赛阶段先不做。

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
→ 系统展示一处重叠 Vocal，用户分别录制并同步回放
→ 系统记住这一类长期弱点
```

最终判断标准：

> **它有没有证明：VerseViva 不只教“单词怎么念”，还教“声音如何成为歌、一个人如何唱完整首歌里的多层 Vocal”？**
