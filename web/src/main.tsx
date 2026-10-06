import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

type AnalysisJob = {
  job_id: string;
  song_id: string;
  title: string;
  artist?: string | null;
  status: "queued" | "processing" | "completed" | "failed";
  stage: string;
  progress: number;
  attempt_count?: number;
  error?: { stage: string; message: string; detail?: string } | null;
  warnings?: { stage: string; message: string; detail?: string }[];
  updated_at?: string;
};

type CharacterMark = {
  symbol: string;
  startCharIndex: number;
  endCharIndex: number;
  placement: "above" | "below" | "inline" | "bridge";
};

type LanguageHint = {
  id: string;
  phenomenon: string;
  confidence: number;
  source: string;
  marks: CharacterMark[];
  details: { locale: string; explanation: string; action: string }[];
  evidence: {
    evidenceStrength?: string;
    needsHumanReview?: boolean;
    result?: string;
  };
};

type SongSentence = {
  id: string;
  startSeconds: number;
  endSeconds: number;
  lyrics: string;
  words: {
    id: string;
    text: string;
    startSeconds: number;
    endSeconds: number;
  }[];
  languageHints: LanguageHint[];
};

type VocalPart = {
  id: string;
  lane: "primary" | "secondary";
  role: "lead" | "harmony" | "backing_vocal" | "response" | "ad_lib" | "double" | "overlap";
  startSeconds: number;
  endSeconds: number;
  lyrics: string;
  sentenceIds: string[];
  source: "acoustic_candidate" | "audio_model_candidate" | "lyrics_structure_candidate" | "lyrics_provider" | "human_curated";
  confidence: number;
  needsHumanReview: boolean;
  evidence: Record<string, unknown>;
};

type SongProfile = {
  songId: string;
  title: string;
  audio: { sourceUrl: string; vocalUrl?: string | null };
  sentences: SongSentence[];
  vocalParts: VocalPart[];
  analysis: {
    lyricsSource?: string;
    lyricsProvider?: string | null;
    lyricsMatchConfidence?: number | null;
    languageAnalysisProvider?: string | null;
    languageAnalysisModel?: string | null;
    vocalArrangementMode?: "single_track" | "dual_track";
  };
};

const STAGE_LABELS: Record<string, string> = {
  analyzing_vocal_parts: "正在解析主唱与次 Vocal",
  queued: "等待开始",
  probing_audio: "正在读取音频信息",
  separating_vocals: "正在分离人声",
  extracting_pitch: "正在提取对齐辅助特征",
  fetching_lyrics: "正在从 LRCLIB 匹配歌词",
  aligning_lyrics: "正在对齐歌词",
  analyzing_language: "正在核查跨词发音",
  building_profile: "正在生成教学标记",
  completed: "分析完成",
  failed: "分析失败",
};

const HERO_SONGS = [
  { id: "song_00000000000000000000000000000002", label: "Juno" },
  { id: "song_00000000000000000000000000000003", label: "get him back! bridge" },
] as const;

const ACTIVE_JOB_KEY = "verseviva.activeJobId";

function App() {
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [profile, setProfile] = useState<SongProfile | null>(null);
  const [selectedHint, setSelectedHint] = useState<LanguageHint | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");

  useEffect(() => {
    const jobId = window.localStorage.getItem(ACTIVE_JOB_KEY);
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(
          jobId ? `/api/v1/songs/jobs/${jobId}` : "/api/v1/songs/jobs/latest",
        );
        if (!response.ok) {
          if (response.status === 404) window.localStorage.removeItem(ACTIVE_JOB_KEY);
          if (response.status === 404 && !jobId) return;
          throw new Error("恢复上次分析任务失败");
        }
        const restoredJob = (await response.json()) as AnalysisJob;
        if (cancelled) return;
        setJob(restoredJob);
        setTitle(restoredJob.title ?? "");
        setArtist(restoredJob.artist ?? "");
        if (restoredJob.status === "completed") {
          const profileResponse = await fetch(`/api/v1/songs/${restoredJob.song_id}`);
          if (!profileResponse.ok) throw new Error("恢复上次分析结果失败");
          const restoredProfile = (await profileResponse.json()) as SongProfile;
          if (!cancelled) setProfile(restoredProfile);
        }
      } catch (restoreError) {
        if (!cancelled) {
          setError(restoreError instanceof Error ? restoreError.message : "恢复任务失败");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (job?.job_id) window.localStorage.setItem(ACTIVE_JOB_KEY, job.job_id);
  }, [job?.job_id]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/v1/songs/jobs/${job.job_id}`);
        if (!response.ok) throw new Error("读取分析进度失败");
        const nextJob = (await response.json()) as AnalysisJob;
        setJob(nextJob);
        if (nextJob.status === "completed") {
          const profileResponse = await fetch(`/api/v1/songs/${nextJob.song_id}`);
          if (!profileResponse.ok) throw new Error("读取歌曲标注失败");
          setProfile((await profileResponse.json()) as SongProfile);
        } else if (nextJob.status === "failed") {
          setError(nextJob.error?.message ?? "歌曲分析失败");
        }
      } catch (pollError) {
        setError(pollError instanceof Error ? pollError.message : "读取分析进度失败");
      }
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [job]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setProfile(null);
    setSelectedHint(null);
    try {
      const form = new FormData(event.currentTarget);
      const response = await fetch("/api/v1/songs/analyze", { method: "POST", body: form });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "上传失败");
      }
      const createdJob = (await response.json()) as AnalysisJob;
      setJob(createdJob);
      setTitle(createdJob.title ?? title);
      setArtist(createdJob.artist ?? artist);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "上传失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function retry() {
    if (!job) return;
    setRetrying(true);
    setError(null);
    try {
      const response = await fetch(`/api/v1/songs/jobs/${job.job_id}/retry`, {
        method: "POST",
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "重试失败");
      }
      setJob((await response.json()) as AnalysisJob);
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "重试失败");
    } finally {
      setRetrying(false);
    }
  }

  async function loadHero(songId: string) {
    setError(null);
    setSelectedHint(null);
    try {
      const response = await fetch(`/api/v1/songs/${songId}`);
      if (!response.ok) throw new Error("Hero 歌曲缓存尚未生成");
      setProfile((await response.json()) as SongProfile);
      setJob(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "读取叠唱 Hero 失败");
    }
  }

  return (
    <main>
      <header className="hero">
        <p className="eyebrow">VERSEVIVA · 声声不息</p>
        <h1>听见原唱怎么把词唱在一起</h1>
        <p className="intro">
          只需上传英文歌曲，系统会查找歌词、分离人声、对齐每个词，并用字符标出可听见的语言现象。
        </p>
      </header>

      <form className="upload-card" onSubmit={submit}>
        <label>
          <span>歌曲文件</span>
          <input name="audio" type="file" accept=".mp3,.wav,.flac,audio/*" required />
        </label>
        <label>
          <span>歌曲名</span>
          <input
            name="title"
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="可选；文件名不清楚时填写"
          />
        </label>
        <label>
          <span>歌手</span>
          <input
            name="artist"
            type="text"
            value={artist}
            onChange={(event) => setArtist(event.target.value)}
            placeholder="可选；填写后可降低同名歌误匹配"
          />
        </label>
        <details>
          <summary>高级：手动提供歌词</summary>
          <label>
            <span>歌词（会优先于 LRCLIB）</span>
            <textarea name="lyrics" rows={7} placeholder="仅在自动查词不准时使用" />
          </label>
        </details>
        <button className="primary-button" disabled={submitting}>
          {submitting ? "正在上传…" : "上传并分析"}
        </button>
      </form>

      <section className="hero-shortcut">
        <div>
          <strong>已缓存 Hero Songs</strong>
          <p>语音标记与左右 Vocal Part 在同一界面展示。</p>
        </div>
        {HERO_SONGS.map((song) => (
          <button className="secondary-button" type="button" key={song.id} onClick={() => loadHero(song.id)}>
            打开 {song.label}
          </button>
        ))}
      </section>

      {job && !profile && (
        <section className="status-card" aria-live="polite">
          <div className="status-line">
            <strong>
              {job.status === "failed"
                ? `失败：${STAGE_LABELS[job.error?.stage ?? job.stage] ?? job.error?.stage}`
                : STAGE_LABELS[job.stage] ?? job.stage}
            </strong>
            <span>{job.progress}%</span>
          </div>
          <div className="progress-track">
            <div className="progress-value" style={{ width: `${job.progress}%` }} />
          </div>
          <p>完整歌曲在 CPU 环境下可能需要较长时间，Hero Song 应优先使用缓存。</p>
          {job.status === "processing" && job.updated_at &&
            Date.now() - new Date(job.updated_at).getTime() > 120_000 && (
              <p className="stale-note">
                该阶段较长时间未更新，可能仍在请求模型，也可能正在等待后端重启。
                任务编号已保存，刷新页面后会自动恢复。
              </p>
            )}
          {job.status === "failed" && job.error && (
            <div className="failure-detail">
              <strong>{job.error.message}</strong>
              {job.error.detail && <code>{job.error.detail}</code>}
              <p>已完成的阶段产物会保留，重试时不会重复计算。</p>
              <button className="retry-button" onClick={retry} disabled={retrying}>
                {retrying ? "正在重试…" : "从失败处重试"}
              </button>
            </div>
          )}
          {job.warnings?.map((warning, index) => (
            <div className="warning-detail" key={`${warning.stage}-${index}`}>
              <strong>{warning.message}</strong>
              {warning.detail && <code>{warning.detail}</code>}
            </div>
          ))}
        </section>
      )}

      {error && !job?.error && <p className="error-card">{error}</p>}

      {profile && (
        <ProfileView profile={profile} selectedHint={selectedHint} onSelect={setSelectedHint} />
      )}
    </main>
  );
}

function ProfileView({
  profile,
  selectedHint,
  onSelect,
}: {
  profile: SongProfile;
  selectedHint: LanguageHint | null;
  onSelect: (hint: LanguageHint) => void;
}) {
  const [currentTime, setCurrentTime] = useState(0);
  const [lyricsMode, setLyricsMode] = useState<"standard" | "layers">("standard");
  useEffect(() => {
    setCurrentTime(0);
    setLyricsMode(profile.sentences.length === 0 && profile.vocalParts.length > 0 ? "layers" : "standard");
  }, [profile.songId, profile.sentences.length, profile.vocalParts.length]);
  const hintCount = useMemo(
    () => profile.sentences.reduce((total, sentence) => total + sentence.languageHints.length, 0),
    [profile],
  );
  return (
    <section className="profile-card">
      <div className="profile-heading">
        <div>
          <p className="eyebrow">分析结果</p>
          <h2>{profile.title}</h2>
        </div>
        <span>{hintCount} 处标记</span>
      </div>

      <div className="players">
        <label>
          <span>原曲</span>
          <AudioPlayer src={profile.audio.sourceUrl} onTimeChange={setCurrentTime} />
        </label>
        {profile.audio.vocalUrl && (
          <label>
            <span>人声</span>
            <AudioPlayer src={profile.audio.vocalUrl} onTimeChange={setCurrentTime} />
          </label>
        )}
      </div>

      <div className="legend" aria-label="标记说明">
        <span><b>×</b> 未清晰释放</span>
        <span><b>‿</b> 跨词承接</span>
        <span><b>└─┘</b> 合并或融合</span>
      </div>

      <div className="lyrics-stage-heading">
        <div>
          <p className="eyebrow">SYNCED LYRICS</p>
          <h3>歌曲学习歌词</h3>
        </div>
        {profile.vocalParts.length > 0 && (
          <div className="lyrics-mode-switch" role="group" aria-label="歌词视图">
            <button
              className={lyricsMode === "standard" ? "active" : ""}
              onClick={() => setLyricsMode("standard")}
              type="button"
            >
              普通歌词
            </button>
            <button
              className={lyricsMode === "layers" ? "active" : ""}
              onClick={() => setLyricsMode("layers")}
              type="button"
            >
              叠唱歌词
            </button>
          </div>
        )}
      </div>

      {lyricsMode === "layers" && profile.vocalParts.length > 0
        ? <VocalLayers
            vocalParts={profile.vocalParts}
            sentences={profile.sentences}
            currentTime={currentTime}
            onSelect={onSelect}
          />
        : <KaraokeLyrics
            sentences={profile.sentences}
            currentTime={currentTime}
            onSelect={onSelect}
          />}

      {selectedHint && <HintDetail hint={selectedHint} />}

      <p className="model-note">
        歌词来源：{profile.analysis.lyricsSource ?? "asr"}
        {profile.analysis.lyricsProvider ? ` / ${profile.analysis.lyricsProvider}` : ""}。
        标注来源：{profile.analysis.languageAnalysisProvider ?? "未启用"}
        {profile.analysis.languageAnalysisModel ? ` / ${profile.analysis.languageAnalysisModel}` : ""}。
        LLM 标注属于候选，弱证据不会显示；比赛 Hero Song 仍需人工校对。
      </p>
    </section>
  );
}

function AudioPlayer({
  src,
  onTimeChange,
}: {
  src: string;
  onTimeChange: (time: number) => void;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = 0.3;
  }, [src]);
  return (
    <audio
      ref={audioRef}
      controls
      preload="metadata"
      src={src}
      onLoadedMetadata={(event) => { event.currentTarget.volume = 0.3; }}
      onTimeUpdate={(event) => onTimeChange(event.currentTarget.currentTime)}
      onSeeked={(event) => onTimeChange(event.currentTarget.currentTime)}
    />
  );
}

function KaraokeLyrics({
  sentences,
  currentTime,
  onSelect,
}: {
  sentences: SongSentence[];
  currentTime: number;
  onSelect: (hint: LanguageHint) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const activeSentenceId = sentences.find(
    (sentence) => currentTime >= sentence.startSeconds && currentTime < sentence.endSeconds,
  )?.id;
  useEffect(() => {
    if (!activeSentenceId || !containerRef.current) return;
    const active = containerRef.current.querySelector(`[data-sentence-id="${activeSentenceId}"]`);
    active?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activeSentenceId]);
  if (sentences.length === 0) {
    return <p className="lyrics-empty">当前缓存只包含 Vocal 分层信息；重新上传音频可生成语言标注歌词。</p>;
  }
  return (
    <div className="lyrics-viewport" ref={containerRef}>
      <div className="lyrics-list">
        {sentences.map((sentence) => (
          <AnnotatedLine
            key={sentence.id}
            sentence={sentence}
            currentTime={currentTime}
            active={sentence.id === activeSentenceId}
            past={currentTime > sentence.endSeconds}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}

const ROLE_LABELS: Record<VocalPart["role"], string> = {
  lead: "Lead",
  harmony: "Harmony",
  backing_vocal: "Backing vocal",
  response: "Response",
  ad_lib: "Ad-lib",
  double: "Double",
  overlap: "Overlap",
};

const SOURCE_LABELS: Record<VocalPart["source"], string> = {
  acoustic_candidate: "声学 / ASR 候选",
  audio_model_candidate: "音频模型候选",
  lyrics_structure_candidate: "歌词结构候选",
  lyrics_provider: "歌词网站",
  human_curated: "人工校对",
};

function VocalLayers({
  vocalParts,
  sentences,
  currentTime,
  onSelect,
}: {
  vocalParts: VocalPart[];
  sentences: SongSentence[];
  currentTime: number;
  onSelect: (hint: LanguageHint) => void;
}) {
  const sentencesById = new Map(sentences.map((sentence) => [sentence.id, sentence]));
  const primary = vocalParts
    .filter((part) => part.lane === "primary")
    .sort((left, right) => left.startSeconds - right.startSeconds);
  const secondary = vocalParts
    .filter((part) => part.lane === "secondary")
    .sort((left, right) => left.startSeconds - right.startSeconds);
  const assignedSecondary = new Set<string>();
  const rows = primary.map((part) => {
    const overlapping = secondary.filter((candidate) => {
      const overlaps = candidate.startSeconds < part.endSeconds
        && candidate.endSeconds > part.startSeconds;
      if (overlaps) assignedSecondary.add(candidate.id);
      return overlaps;
    });
    return { primary: [part], secondary: overlapping };
  });
  for (const part of secondary) {
    if (!assignedSecondary.has(part.id)) rows.push({ primary: [], secondary: [part] });
  }

  return (
    <section className="vocal-layers" aria-label="左右双轨歌词">
      <div className="vocal-lane-scroll">
        <div className="vocal-lane-grid">
          <div className="vocal-lane-title primary">
            <strong>主 Vocal</strong><span>PRIMARY</span>
          </div>
          <div className="vocal-lane-title secondary">
            <strong>次 Vocal</strong><span>SECONDARY</span>
          </div>
          {rows.map((row, rowIndex) => (
            <React.Fragment key={`vocal-row-${rowIndex}`}>
              <div className="vocal-lane-cell primary">
                {row.primary.length > 0
                  ? row.primary.map((part) => <VocalPartCard
                      part={part}
                      sentence={sentencesById.get(part.sentenceIds[0])}
                      currentTime={currentTime}
                      onSelect={onSelect}
                      key={part.id}
                    />)
                  : <p className="empty-vocal-lane">此时无主 Vocal 标注</p>}
              </div>
              <div className="vocal-lane-cell secondary">
                {row.secondary.length > 0
                  ? row.secondary.map((part) => <VocalPartCard
                      part={part}
                      currentTime={currentTime}
                      onSelect={onSelect}
                      key={part.id}
                    />)
                  : <p className="empty-vocal-lane">此时无次 Vocal 标注</p>}
              </div>
            </React.Fragment>
          ))}
        </div>
      </div>
    </section>
  );
}

function VocalPartCard({
  part,
  sentence,
  currentTime,
  onSelect,
}: {
  part: VocalPart;
  sentence?: SongSentence;
  currentTime: number;
  onSelect: (hint: LanguageHint) => void;
}) {
  const sourceLabel = SOURCE_LABELS[part.source];
  const active = currentTime >= part.startSeconds && currentTime < part.endSeconds;
  return (
    <article className={`vocal-part ${active ? "active" : ""}`}>
      <div className="vocal-part-meta">
        <strong>{ROLE_LABELS[part.role]}</strong>
        <span>{formatPartTime(part.startSeconds)} – {formatPartTime(part.endSeconds)}</span>
      </div>
      {sentence
        ? <AnnotatedLine
            sentence={sentence}
            currentTime={currentTime}
            active={active}
            past={currentTime > part.endSeconds}
            onSelect={onSelect}
            compact
          />
        : <p>{part.lyrics}</p>}
      <small>
        {sourceLabel}
        {part.needsHumanReview ? " · 需复核" : ""}
        {` · ${Math.round(part.confidence * 100)}%`}
      </small>
    </article>
  );
}

function formatPartTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds - minutes * 60;
  return `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`;
}

function AnnotatedLine({
  sentence,
  currentTime,
  active,
  past,
  onSelect,
  compact = false,
}: {
  sentence: SongSentence;
  currentTime: number;
  active: boolean;
  past: boolean;
  onSelect: (hint: LanguageHint) => void;
  compact?: boolean;
}) {
  const marksAt = new Map<number, { mark: CharacterMark; hint: LanguageHint }[]>();
  for (const hint of sentence.languageHints) {
    for (const mark of hint.marks) {
      const values = marksAt.get(mark.startCharIndex) ?? [];
      values.push({ mark, hint });
      marksAt.set(mark.startCharIndex, values);
    }
  }
  const wordRanges = findWordRanges(sentence);
  const activeWord = wordRanges.find(
    ({ word }) => currentTime >= word.startSeconds && currentTime < word.endSeconds,
  );

  return (
    <p
      className={`lyric-line ${active ? "active" : ""} ${past ? "past" : ""} ${compact ? "compact" : ""}`}
      data-sentence-id={sentence.id}
    >
      {Array.from(sentence.lyrics).map((character, index) => (
        <React.Fragment key={`${sentence.id}-${index}`}>
          <span className={`lyric-character ${
            activeWord && index >= activeWord.start && index <= activeWord.end ? "active-word" : ""
          }`}>
            {character}
            {(marksAt.get(index) ?? [])
              .map(({ mark, hint }) => (
                <button
                  key={`${hint.id}-${mark.symbol}`}
                  className="character-mark below"
                  onClick={() => onSelect(hint)}
                  title="查看解释"
                >
                  {mark.symbol}
                </button>
              ))}
          </span>
        </React.Fragment>
      ))}
    </p>
  );
}

function findWordRanges(sentence: SongSentence) {
  const matches = Array.from(sentence.lyrics.matchAll(/[A-Za-z]+(?:['’][A-Za-z]+)*/g));
  let cursor = 0;
  return sentence.words.flatMap((word) => {
    const normalized = normalizeWord(word.text);
    const relativeIndex = matches.slice(cursor).findIndex(
      (match) => normalizeWord(match[0]) === normalized,
    );
    if (relativeIndex < 0) return [];
    const matchIndex = cursor + relativeIndex;
    const match = matches[matchIndex];
    cursor = matchIndex + 1;
    const start = match.index ?? 0;
    return [{ word, start, end: start + match[0].length - 1 }];
  });
}

function normalizeWord(value: string) {
  return value.toLowerCase().replaceAll("’", "'").replace(/[^a-z']/g, "");
}

function HintDetail({ hint }: { hint: LanguageHint }) {
  const detail = hint.details.find((item) => item.locale === "zh-CN") ?? hint.details[0];
  if (!detail) return null;
  return (
    <aside className="hint-detail">
      <div className="detail-heading">
        <strong>{hint.marks.map((mark) => mark.symbol).join(" ")} · {hint.phenomenon}</strong>
        <span>{hint.evidence.evidenceStrength ?? "unknown"}</span>
      </div>
      <p>{detail.explanation}</p>
      <p className="action"><b>下一遍：</b>{detail.action}</p>
      {hint.evidence.needsHumanReview && <p className="review-note">这条候选需要人工复核。</p>}
    </aside>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
