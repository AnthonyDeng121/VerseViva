import React, { FormEvent, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { RecordingStudio } from "./RecordingStudio";
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
  identityStatus: "confirmed" | "candidate";
  timingStatus: "aligned_sentence_fallback" | "audio_model_observed" | "human_curated";
  timingConfidence?: number | null;
  timingNeedsHumanReview: boolean;
  evidence: Record<string, unknown>;
};

type SongProfile = {
  songId: string;
  title: string;
  audio: {
    sourceUrl: string;
    vocalUrl?: string | null;
    accompanimentUrl?: string | null;
  };
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
  fetching_lyrics: "正在从 LRCLIB 匹配歌词",
  aligning_lyrics: "正在对齐歌词",
  analyzing_language: "正在核查跨词发音",
  building_profile: "正在生成教学标记",
  completed: "分析完成",
  failed: "分析失败",
};

const HERO_SONGS = [
  { id: "song_00000000000000000000000000000002", label: "Juno" },
  { id: "song_00000000000000000000000000000003", label: "get him back!" },
] as const;

const ACTIVE_JOB_KEY = "verseviva.activeJobId";
const CACHED_SONGS_KEY = "verseviva.cachedSongs";
type CachedSong = { songId: string; title: string; artist?: string | null };

function App() {
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [profile, setProfile] = useState<SongProfile | null>(null);
  const [selectedHint, setSelectedHint] = useState<LanguageHint | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [pageMode, setPageMode] = useState<"upload" | "sing">("upload");
  const [cachedSongs, setCachedSongs] = useState<CachedSong[]>(() => {
    try { return JSON.parse(window.localStorage.getItem(CACHED_SONGS_KEY) ?? "[]") as CachedSong[]; }
    catch { return []; }
  });

  function rememberSong(item: CachedSong) {
    setCachedSongs((current) => {
      const next = [item, ...current.filter((cached) => cached.songId !== item.songId)].slice(0, 20);
      window.localStorage.setItem(CACHED_SONGS_KEY, JSON.stringify(next));
      return next;
    });
  }

  useEffect(() => {
    const jobId = window.localStorage.getItem(ACTIVE_JOB_KEY);
    let cancelled = false;
    void (async () => {
      try {
        if (!jobId) return;
        const response = await fetch(`/api/v1/songs/jobs/${jobId}`);
        if (!response.ok) {
          if (response.status === 404) window.localStorage.removeItem(ACTIVE_JOB_KEY);
          if (response.status === 404 && !jobId) return;
          throw new Error("恢复上次分析任务失败");
        }
        const restoredJob = (await response.json()) as AnalysisJob;
        if (cancelled) return;
        setJob(restoredJob);
        setTitle(restoredJob.title);
        setArtist(restoredJob.artist ?? "");
        if (restoredJob.status === "completed") {
          const profileResponse = await fetch(`/api/v1/songs/${restoredJob.song_id}`);
          if (!profileResponse.ok) throw new Error("恢复上次分析结果失败");
          const restoredProfile = (await profileResponse.json()) as SongProfile;
          if (!cancelled) {
            setProfile(restoredProfile);
            setPageMode("sing");
            rememberSong({ songId: restoredProfile.songId, title: restoredProfile.title,
              artist: restoredJob.artist });
          }
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
          setPageMode("sing");
          rememberSong({ songId: nextJob.song_id, title: nextJob.title, artist: nextJob.artist });
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
      setPageMode("sing");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "读取叠唱 Hero 失败");
    }
  }

  function dismissJob() {
    window.localStorage.removeItem(ACTIVE_JOB_KEY);
    setJob(null);
    setError(null);
  }

  return (
    <main>
      <header className="hero">
        <p className="eyebrow">VERSEVIVA · 声声不息</p>
        <h1>教你学唱英文歌，并支持叠唱音轨</h1>
        <p className="intro">
          点击上传歌曲文件，输入歌曲名 + 人名，系统自动解析歌词教学并支持多轨叠唱
        </p>
        <div className="page-mode-switch" role="group" aria-label="功能切换">
          <button type="button" className={pageMode === "upload" ? "active" : ""}
            onClick={() => setPageMode("upload")}>上传歌曲</button>
          <button type="button" className={pageMode === "sing" ? "active" : ""}
            onClick={() => setPageMode("sing")} disabled={!profile}>演唱</button>
        </div>
      </header>

      {pageMode === "upload" && <form className="upload-card" onSubmit={submit}>
        <label>
          <span>歌曲文件</span>
          <input name="audio" type="file" accept=".mp3,.wav,.flac,audio/*" required />
        </label>
        <label>
          <span>歌曲名（必填，请区分大小写）</span>
          <input
            name="title"
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="例如：Poker Face"
            required
          />
        </label>
        <label>
          <span>歌手（必填，请区分大小写）</span>
          <input
            name="artist"
            type="text"
            value={artist}
            onChange={(event) => setArtist(event.target.value)}
            placeholder="例如：Lady Gaga"
            required
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
      </form>}

      {pageMode === "upload" && <section className="hero-shortcut">
        <div>
          <strong>示例歌曲</strong>
          <p>直接打开示例，体验语言标记与左右双轨歌词。</p>
        </div>
        {HERO_SONGS.map((song) => (
          <button className="secondary-button" type="button" key={song.id} onClick={() => loadHero(song.id)}>
            打开 {song.label}
          </button>
        ))}
      </section>}

      {pageMode === "upload" && cachedSongs.length > 0 && <section className="song-cache">
        <strong>这台设备已缓存的歌曲</strong>
        <div>{cachedSongs.map((song) => <button className="secondary-button" type="button"
          key={song.songId} onClick={() => void loadHero(song.songId)}>
          {song.title}{song.artist ? ` · ${song.artist}` : ""}
        </button>)}</div>
      </section>}

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
              <button className="secondary-button" type="button" onClick={dismissJob}>
                取消并返回
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

      {profile && pageMode === "sing" && (
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
  const [playbackRate, setPlaybackRate] = useState<0.75 | 1>(1);
  const [loopSentenceId, setLoopSentenceId] = useState<string | null>(null);
  const [audioMode, setAudioMode] = useState<"source" | "vocal">("source");
  const sourceAudioRef = useRef<HTMLAudioElement>(null);
  const vocalAudioRef = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    setCurrentTime(0);
    setPlaybackRate(1);
    setLoopSentenceId(null);
    setAudioMode("source");
    setLyricsMode(profile.sentences.length === 0 && profile.vocalParts.length > 0 ? "layers" : "standard");
  }, [profile.songId, profile.sentences.length, profile.vocalParts.length]);
  const activeSentence = profile.sentences.find(
    (sentence) => currentTime >= sentence.startSeconds && currentTime < sentence.endSeconds,
  );
  const loopSentence = profile.sentences.find((sentence) => sentence.id === loopSentenceId);
  const seekTo = (time: number) => {
    for (const player of [sourceAudioRef.current, vocalAudioRef.current]) {
      if (player && Number.isFinite(player.duration)) player.currentTime = time;
    }
    if (loopSentenceId) {
      const selectedSentence = profile.sentences.find(
        (sentence) => time >= sentence.startSeconds && time < sentence.endSeconds,
      );
      if (selectedSentence) setLoopSentenceId(selectedSentence.id);
    }
    setCurrentTime(time);
  };
  const handleTimeChange = (time: number) => {
    if (loopSentence && time >= loopSentence.endSeconds) {
      for (const referencePlayer of [sourceAudioRef.current, vocalAudioRef.current]) {
        if (referencePlayer && Number.isFinite(referencePlayer.duration)) {
          referencePlayer.currentTime = loopSentence.startSeconds;
        }
      }
      setCurrentTime(loopSentence.startSeconds);
      return;
    }
    setCurrentTime(time);
  };
  const toggleSentenceLoop = () => {
    const target = loopSentence ?? activeSentence ?? profile.sentences[0];
    if (!target) return;
    if (loopSentence) {
      setLoopSentenceId(null);
      return;
    }
    setLoopSentenceId(target.id);
    seekTo(target.startSeconds);
  };
  return (
    <section className="profile-card">
      <div className="profile-heading">
        <div className="profile-title-line">
          <p className="eyebrow">分析结果</p>
          <h2>{displaySongTitle(profile.title)}</h2>
        </div>
        <div className="audio-mode-switch" role="group" aria-label="参考音轨">
          <button type="button" className={audioMode === "source" ? "active" : ""}
            onClick={() => setAudioMode("source")}>原曲</button>
          {profile.audio.vocalUrl && <button type="button" className={audioMode === "vocal" ? "active" : ""}
            onClick={() => setAudioMode("vocal")}>人声</button>}
        </div>
      </div>

      <div className="players">
        {audioMode === "source" && <label>
          <span>原曲</span>
          <AudioPlayer audioRef={sourceAudioRef} src={profile.audio.sourceUrl}
            playbackRate={playbackRate} onTimeChange={handleTimeChange} />
        </label>}
        {audioMode === "vocal" && profile.audio.vocalUrl && (
          <label>
            <span>人声</span>
            <AudioPlayer audioRef={vocalAudioRef} src={profile.audio.vocalUrl}
              playbackRate={playbackRate} onTimeChange={handleTimeChange} />
          </label>
        )}
      </div>

      <div className="learning-playback-controls" aria-label="听句控制">
        <div className="speed-switch" role="group" aria-label="播放速度">
          <button className={playbackRate === 1 ? "active" : ""} type="button" onClick={() => setPlaybackRate(1)}>原速</button>
          <button className={playbackRate === 0.75 ? "active" : ""} type="button" onClick={() => setPlaybackRate(0.75)}>0.75×</button>
        </div>
        <button className={`sentence-loop-button ${loopSentence ? "active" : ""}`}
          type="button" disabled={profile.sentences.length === 0} onClick={toggleSentenceLoop}>
          {loopSentence ? `循环中：${loopSentence.lyrics}` : "循环当前句"}
        </button>
        <span>点击歌词可跳到该句</span>
      </div>

      <div className="legend" aria-label="标记说明">
        <span><b>×</b>：吞音（不发该音）</span>
        <span><b>‿</b>：连读（读音二合一）</span>
        <span><b>└─┘</b>：连读（读音改变）</span>
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
            onSeek={seekTo}
            onSelect={onSelect}
          />
        : <KaraokeLyrics
            sentences={profile.sentences}
            currentTime={currentTime}
            onSelect={onSelect}
            onSeek={seekTo}
          />}

      {selectedHint && <HintDetail hint={selectedHint} />}

      <RecordingStudio
        songId={profile.songId}
        sentences={profile.sentences}
        vocalParts={profile.vocalParts}
        accompanimentUrl={profile.audio.accompanimentUrl}
        onTimelineChange={setCurrentTime}
      />

    </section>
  );
}

function displaySongTitle(title: string) {
  return title.replace(/\s*[—-]\s*Language\s*&\s*Vocal\s*Layers\s*$/i, "").trim();
}

function AudioPlayer({
  audioRef,
  src,
  playbackRate,
  onTimeChange,
}: {
  audioRef: React.RefObject<HTMLAudioElement | null>;
  src: string;
  playbackRate: number;
  onTimeChange: (time: number, player: HTMLAudioElement) => void;
}) {
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = 0.3;
      audioRef.current.playbackRate = playbackRate;
    }
  }, [audioRef, playbackRate, src]);
  return (
    <audio
      ref={audioRef}
      controls
      preload="metadata"
      src={src}
      onLoadedMetadata={(event) => {
        event.currentTarget.volume = 0.3;
        event.currentTarget.playbackRate = playbackRate;
      }}
      onTimeUpdate={(event) => onTimeChange(event.currentTarget.currentTime, event.currentTarget)}
      onSeeked={(event) => onTimeChange(event.currentTarget.currentTime, event.currentTarget)}
    />
  );
}

function KaraokeLyrics({
  sentences,
  currentTime,
  onSelect,
  onSeek,
}: {
  sentences: SongSentence[];
  currentTime: number;
  onSelect: (hint: LanguageHint) => void;
  onSeek: (time: number) => void;
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
            onSeek={onSeek}
          />
        ))}
      </div>
    </div>
  );
}

function VocalLayers({
  vocalParts,
  sentences,
  currentTime,
  onSeek,
  onSelect,
}: {
  vocalParts: VocalPart[];
  sentences: SongSentence[];
  currentTime: number;
  onSeek: (time: number) => void;
  onSelect: (hint: LanguageHint) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const primary = vocalParts
    .filter((part) => part.lane === "primary")
    .sort((left, right) => left.startSeconds - right.startSeconds);
  const secondary = vocalParts
    .filter((part) => part.lane === "secondary")
    .sort((left, right) => left.startSeconds - right.startSeconds);
  const assignedSecondary = new Set<string>();
  const rows = primary.map((part) => {
    const overlapping = secondary.filter((candidate) => {
      if (assignedSecondary.has(candidate.id)) return false;
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
  const activeRow = rows.findIndex((row) => [...row.primary, ...row.secondary].some(
    (part) => currentTime >= part.startSeconds && currentTime < part.endSeconds,
  ));
  useEffect(() => {
    if (activeRow < 0 || !containerRef.current) return;
    containerRef.current.querySelector(`[data-vocal-row="${activeRow}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
  }, [activeRow]);

  return (
    <section className="vocal-layers" aria-label="左右双轨歌词">
      <div className="vocal-lane-scroll" ref={containerRef}>
        <div className="vocal-lane-grid">
          <div className="vocal-lane-title primary">
            <strong>主 Vocal</strong><span>PRIMARY</span>
          </div>
          <div className="vocal-lane-title secondary">
            <strong>次 Vocal</strong><span>SECONDARY</span>
          </div>
          {rows.map((row, rowIndex) => (
            <React.Fragment key={`vocal-row-${rowIndex}`}>
              <div className="vocal-lane-cell primary" data-vocal-row={rowIndex}>
                {row.primary.length > 0
                  ? row.primary.map((part) => <AnnotatedVocalPart part={part} sentences={sentences}
                      lyrics={withoutParenthetical(part.lyrics)} currentTime={currentTime}
                      onSeek={onSeek} onSelect={onSelect} key={part.id} />)
                  : null}
              </div>
              <div className="vocal-lane-cell secondary">
                {row.secondary.length > 0
                  ? row.secondary.map((part) => <AnnotatedVocalPart part={part} sentences={sentences}
                      currentTime={currentTime} onSeek={onSeek} onSelect={onSelect} key={part.id} />)
                  : null}
              </div>
            </React.Fragment>
          ))}
        </div>
      </div>
    </section>
  );
}

function AnnotatedVocalPart({ part, sentences, lyrics = part.lyrics, currentTime, onSeek, onSelect }: {
  part: VocalPart; sentences: SongSentence[]; lyrics?: string; currentTime: number;
  onSeek: (time: number) => void; onSelect: (hint: LanguageHint) => void;
}) {
  const source = sentences.find((sentence) => part.sentenceIds.includes(sentence.id))
    ?? sentences.find((sentence) => sentence.startSeconds < part.endSeconds
      && sentence.endSeconds > part.startSeconds);
  const projected = source ? projectSentence(source, lyrics, part) : {
    id: part.id, lyrics, startSeconds: part.startSeconds, endSeconds: part.endSeconds,
    words: [], languageHints: [],
  };
  return <AnnotatedLine sentence={projected} currentTime={currentTime}
    active={currentTime >= part.startSeconds && currentTime < part.endSeconds}
    past={currentTime >= part.endSeconds} onSelect={onSelect} onSeek={onSeek} compact />;
}

function projectSentence(source: SongSentence, lyrics: string, part: VocalPart): SongSentence {
  const sourceChars = Array.from(source.lyrics);
  const targetChars = Array.from(lyrics);
  const targetToSource = new Map<number, number>();
  const exactStart = source.lyrics.toLocaleLowerCase().indexOf(lyrics.toLocaleLowerCase());
  if (exactStart >= 0) {
    targetChars.forEach((_, target) => targetToSource.set(target, exactStart + target));
  } else {
    let cursor = 0;
    for (let target = 0; target < targetChars.length; target += 1) {
      const wanted = targetChars[target].toLocaleLowerCase();
      const found = sourceChars.findIndex((character, index) => index >= cursor
        && character.toLocaleLowerCase() === wanted);
      if (found >= 0) { targetToSource.set(target, found); cursor = found + 1; }
    }
  }
  const sourceToTarget = new Map(Array.from(targetToSource, ([target, original]) => [original, target]));
  const languageHints = source.languageHints.flatMap((hint) => {
    const marks = hint.marks.flatMap((mark) => {
      const mapped = sourceToTarget.get(mark.startCharIndex);
      return mapped === undefined ? [] : [{ ...mark, startCharIndex: mapped, endCharIndex: mapped }];
    });
    return marks.length ? [{ ...hint, marks }] : [];
  });
  return { ...source, id: part.id, lyrics, startSeconds: part.startSeconds,
    endSeconds: part.endSeconds, words: [], languageHints };
}

function withoutParenthetical(lyrics: string) {
  return lyrics.replace(/\s*\([^)]*\)/g, "").trim();
}

function AnnotatedLine({
  sentence,
  currentTime,
  active,
  past,
  onSelect,
  onSeek,
  compact = false,
}: {
  sentence: SongSentence;
  currentTime: number;
  active: boolean;
  past: boolean;
  onSelect: (hint: LanguageHint) => void;
  onSeek: (time: number) => void;
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
      role="button"
      tabIndex={0}
      onClick={() => onSeek(sentence.startSeconds)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onSeek(sentence.startSeconds);
      }}
      title="跳到这句"
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
                  className={`character-mark below ${
                    mark.symbol === "×" ? "elision" : mark.symbol === "‿" ? "boundary link" : "boundary merge"
                  }`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelect(hint);
                  }}
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
