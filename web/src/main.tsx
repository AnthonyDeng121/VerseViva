import React, { FormEvent, useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

type AnalysisJob = {
  job_id: string;
  song_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  stage: string;
  progress: number;
  attempt_count?: number;
  error?: { stage: string; message: string; detail?: string } | null;
  warnings?: { stage: string; message: string; detail?: string }[];
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
  languageHints: LanguageHint[];
};

type SongProfile = {
  songId: string;
  title: string;
  audio: { sourceUrl: string; vocalUrl: string };
  sentences: SongSentence[];
  analysis: {
    lyricsSource?: string;
    lyricsProvider?: string | null;
    lyricsMatchConfidence?: number | null;
    languageAnalysisProvider?: string | null;
    languageAnalysisModel?: string | null;
  };
};

const STAGE_LABELS: Record<string, string> = {
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

function App() {
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [profile, setProfile] = useState<SongProfile | null>(null);
  const [selectedHint, setSelectedHint] = useState<LanguageHint | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      setJob((await response.json()) as AnalysisJob);
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
          <input name="title" type="text" placeholder="可选；文件名不清楚时填写" />
        </label>
        <label>
          <span>歌手</span>
          <input name="artist" type="text" placeholder="可选；填写后可降低同名歌误匹配" />
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
          <audio controls preload="metadata" src={profile.audio.sourceUrl} />
        </label>
        <label>
          <span>人声</span>
          <audio controls preload="metadata" src={profile.audio.vocalUrl} />
        </label>
      </div>

      <div className="legend" aria-label="标记说明">
        <span><b>×</b> 未清晰释放</span>
        <span><b>‿</b> 跨词承接</span>
        <span><b>└─┘</b> 合并或融合</span>
      </div>

      <div className="lyrics-list">
        {profile.sentences.map((sentence) => (
          <AnnotatedLine key={sentence.id} sentence={sentence} onSelect={onSelect} />
        ))}
      </div>

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

function AnnotatedLine({
  sentence,
  onSelect,
}: {
  sentence: SongSentence;
  onSelect: (hint: LanguageHint) => void;
}) {
  const marksAt = new Map<number, { mark: CharacterMark; hint: LanguageHint }[]>();
  for (const hint of sentence.languageHints) {
    for (const mark of hint.marks) {
      const values = marksAt.get(mark.startCharIndex) ?? [];
      values.push({ mark, hint });
      marksAt.set(mark.startCharIndex, values);
    }
  }

  return (
    <p className="lyric-line">
      {Array.from(sentence.lyrics).map((character, index) => (
        <React.Fragment key={`${sentence.id}-${index}`}>
          <span className="lyric-character">
            {character}
            {(marksAt.get(index) ?? [])
              .filter(({ mark }) => mark.placement !== "bridge")
              .map(({ mark, hint }) => (
                <button
                  key={`${hint.id}-${mark.symbol}`}
                  className={`character-mark ${mark.placement}`}
                  onClick={() => onSelect(hint)}
                  title="查看解释"
                >
                  {mark.symbol}
                </button>
              ))}
          </span>
          {(marksAt.get(index) ?? [])
            .filter(({ mark }) => mark.placement === "bridge")
            .map(({ mark, hint }) => (
              <button
                key={`${hint.id}-${mark.symbol}`}
                className="bridge-mark"
                onClick={() => onSelect(hint)}
                title="查看解释"
              >
                {mark.symbol}
              </button>
            ))}
        </React.Fragment>
      ))}
    </p>
  );
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
