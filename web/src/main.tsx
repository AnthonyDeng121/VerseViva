import React, { FormEvent, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { normalizeLoopTime } from "./audioTimeline";
import { RecordingStudio } from "./RecordingStudio";
import type { AnalysisJob, CharacterMark, LanguageHint, SongProfile, SongSentence, VocalPart } from "./songTypes";
import "./styles.css";

const STAGE_LABELS: Record<string, string> = {
  analyzing_vocal_parts: "Gemini 正在核查主唱与次 Vocal",
  queued: "等待开始",
  probing_audio: "正在读取音频信息",
  separating_vocals: "Demucs 正在分离人声",
  fetching_lyrics: "正在从 LRCLIB 匹配歌词",
  aligning_lyrics: "WhisperX 正在对齐歌词",
  analyzing_language: "Gemini 正在核查语言技巧",
  building_profile: "正在生成教学标记",
  completed: "分析完成",
  failed: "分析失败",
};

const HERO_SONGS = [
  { id: "song_00000000000000000000000000000003", label: "get him back!（英语）" },
  { id: "song_00000000000000000000000000000004", label: "AS IF IT'S YOUR LAST（韩语）" },
  { id: "song_00000000000000000000000000000005", label: "動物園は大変だ (日语)" },
] as const;

const ACTIVE_JOB_KEY = "verseviva.activeJobId";
const CACHED_SONGS_KEY = "verseviva.cachedSongs";
const RETIRED_SONG_IDS = new Set(["song_00000000000000000000000000000002"]);
type CachedSong = { songId: string; title: string; artist?: string | null };

function App() {
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [profile, setProfile] = useState<SongProfile | null>(null);
  const [selectedHint, setSelectedHint] = useState<LanguageHint | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [loadingHeroId, setLoadingHeroId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [pageMode, setPageMode] = useState<"upload" | "technique" | "sing">("upload");
  const [cachedSongs, setCachedSongs] = useState<CachedSong[]>(() => {
    try { return (JSON.parse(window.localStorage.getItem(CACHED_SONGS_KEY) ?? "[]") as CachedSong[])
      .filter((song) => !RETIRED_SONG_IDS.has(song.songId)); }
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
            setPageMode("technique");
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
          setPageMode("technique");
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
    setLoadingHeroId(songId);
    setError(null);
    setSelectedHint(null);
    try {
      const response = await fetch(`/api/v1/songs/${songId}`);
      if (!response.ok) throw new Error("Hero 歌曲缓存尚未生成");
      setProfile((await response.json()) as SongProfile);
      setJob(null);
      setPageMode("technique");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "读取叠唱 Hero 失败");
    } finally {
      setLoadingHeroId(null);
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
        <h1>教你学唱外语歌，并支持叠唱音轨</h1>
        <p className="intro">
          点击上传歌曲文件，输入歌曲名 + 人名，系统自动解析歌词教学并支持多轨叠唱
        </p>
        <div className="page-mode-switch" role="group" aria-label="功能切换">
          <button type="button" className={pageMode === "upload" ? "active" : ""}
            onClick={() => setPageMode("upload")}>选择歌曲</button>
          <button type="button" className={pageMode === "technique" ? "active" : ""}
            onClick={() => setPageMode("technique")}>技巧分析</button>
          <button type="button" className={pageMode === "sing" ? "active" : ""}
            onClick={() => setPageMode("sing")}>演唱</button>
        </div>
      </header>

      {pageMode === "upload" && <details className="home-collapsible">
        <summary>自行上传歌曲</summary>
      <form className="upload-card" onSubmit={submit}>
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
      </form></details>}

      {pageMode === "upload" && <details className="home-collapsible">
        <summary>示例歌曲</summary><section className="hero-shortcut">
        <div>
          <p>可以直接选择官方示例歌曲片段展示功能</p>
        </div>
        {HERO_SONGS.map((song) => (
          <button className="secondary-button" type="button" key={song.id}
            disabled={loadingHeroId !== null} onClick={() => void loadHero(song.id)}>
            {loadingHeroId === song.id ? `正在读取 ${song.label}…` : song.label}
          </button>
        ))}
        {loadingHeroId && <p className="hero-loading" aria-live="polite">
          正在读取示例歌词和音频索引，请稍候；首次打开可能需要几秒。
        </p>}
      </section></details>}

      {pageMode === "upload" && <details className="home-collapsible">
        <summary>已缓存歌曲</summary><section className="song-cache">
        <div>{cachedSongs.map((song) => <button className="secondary-button" type="button"
          key={song.songId} onClick={() => void loadHero(song.songId)}>
          {song.title}{song.artist ? ` · ${song.artist}` : ""}
        </button>)}</div>
        {cachedSongs.length === 0 && <p>还没有这台设备上传过的歌曲片段。</p>}
      </section></details>}

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
          {job.audio_duration_seconds && job.estimated_total_seconds
            ? <div className="runtime-summary">
                <strong>{formatDuration(job.audio_duration_seconds)} 音频预计约需 {formatDuration(job.estimated_total_seconds)}</strong>
                <span>换算基准：每 30 秒音频约 {formatDuration(
                  job.estimated_total_seconds / job.audio_duration_seconds * 30,
                )}</span>
                <span>按当前 WSL2 + CPU 基准估算；服务器 GPU/CPU 会改变实际速度</span>
                <span>已记录外部 API 调用批次 {job.api_call_count ?? 0} 次</span>
              </div>
            : <p>正在读取音频时长，完成后会换算本次预计用时。</p>}
          {job.stage_runtimes && job.stage_runtimes.length > 0 && <details className="runtime-details">
            <summary>查看各阶段实际耗时</summary>
            <ul>{job.stage_runtimes.map((runtime) => <li key={runtime.stage}>
              <span>{STAGE_LABELS[runtime.stage] ?? runtime.stage}</span>
              <span>{runtime.completed_at
                ? `实际 ${formatDuration(runtime.elapsed_seconds ?? 0)}`
                : `已运行 ${formatDuration(Math.max(0, (Date.now() - new Date(runtime.started_at).getTime()) / 1000))}`}
                {runtime.estimated_seconds ? ` / 预计 ${formatDuration(runtime.estimated_seconds)}` : ""}
                {runtime.cache_hit ? " · 命中缓存" : ""}
                {runtime.api_call_count ? ` · API ${runtime.api_call_count} 次` : ""}</span>
            </li>)}</ul>
          </details>}
          {job.status === "processing" && job.updated_at &&
            Date.now() - new Date(job.updated_at).getTime() > 120_000 && (
              <p className="stale-note">
                该阶段较长时间未更新，模型可能仍在处理或网络响应较慢。
                任务已保存，可以稍后刷新页面查看最新进度。
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

      {!profile && pageMode !== "upload" && <section className="empty-mode-card">
        <strong>请先选择歌曲</strong>
        <p>选择示例歌曲或自行上传歌曲后，才能使用技巧分析和演唱功能。</p>
        <button className="primary-button" type="button" onClick={() => setPageMode("upload")}>
          去选择歌曲
        </button>
      </section>}

      {profile && pageMode !== "upload" && (
        <ProfileView profile={profile} selectedHint={selectedHint} onSelect={setSelectedHint}
          mode={pageMode} />
      )}
    </main>
  );
}

function ProfileView({
  profile,
  selectedHint,
  onSelect,
  mode,
}: {
  profile: SongProfile;
  selectedHint: LanguageHint | null;
  onSelect: (hint: LanguageHint) => void;
  mode: "technique" | "sing";
}) {
  const [currentTime, setCurrentTime] = useState(0);
  const [lyricsMode, setLyricsMode] = useState<"standard" | "layers">("standard");
  const [playbackRate, setPlaybackRate] = useState<0.75 | 1>(1);
  const [loopSentenceId, setLoopSentenceId] = useState<string | null>(null);
  const [audioMode, setAudioMode] = useState<"source" | "vocal">("source");
  const [playbackStopToken, setPlaybackStopToken] = useState(0);
  const sourceAudioRef = useRef<HTMLAudioElement>(null);
  const vocalAudioRef = useRef<HTMLAudioElement>(null);
  const stopReferencePlayback = () => {
    sourceAudioRef.current?.pause();
    vocalAudioRef.current?.pause();
  };
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
    const normalizedTime = loopSentence
      ? normalizeLoopTime(time, loopSentence.startSeconds, loopSentence.endSeconds)
      : time;
    if (loopSentence && normalizedTime !== time) {
      for (const referencePlayer of [sourceAudioRef.current, vocalAudioRef.current]) {
        if (referencePlayer && Number.isFinite(referencePlayer.duration)) {
          referencePlayer.currentTime = normalizedTime;
        }
      }
      setCurrentTime(normalizedTime);
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
          <h2>{displaySongTitle(profile.title)}</h2>
        </div>
        <div className="audio-mode-switch" role="group" aria-label="参考音轨">
          <button type="button" className={audioMode === "source" ? "active" : ""}
            onClick={() => { setAudioMode("source"); setPlaybackStopToken((value) => value + 1); }}>原曲</button>
          {profile.audio.vocalUrl && <button type="button" className={audioMode === "vocal" ? "active" : ""}
            onClick={() => { setAudioMode("vocal"); setPlaybackStopToken((value) => value + 1); }}>人声</button>}
        </div>
      </div>

      <div className="players">
        {audioMode === "source" && <label>
          <span>原曲</span>
          <AudioPlayer audioRef={sourceAudioRef} src={profile.audio.sourceUrl}
            playbackRate={playbackRate} onTimeChange={handleTimeChange}
            onPlay={() => {
              vocalAudioRef.current?.pause();
              setPlaybackStopToken((value) => value + 1);
            }} />
        </label>}
        {audioMode === "vocal" && profile.audio.vocalUrl && (
          <label>
            <span>人声</span>
            <AudioPlayer audioRef={vocalAudioRef} src={profile.audio.vocalUrl}
              playbackRate={playbackRate} onTimeChange={handleTimeChange}
              onPlay={() => {
                sourceAudioRef.current?.pause();
                setPlaybackStopToken((value) => value + 1);
              }} />
          </label>
        )}
      </div>

      {mode === "technique" && <><div className="learning-playback-controls" aria-label="听句控制">
        <div className="speed-switch" role="group" aria-label="播放速度">
          <button className={playbackRate === 1 ? "active" : ""} type="button" onClick={() => setPlaybackRate(1)}>原速</button>
          <button className={playbackRate === 0.75 ? "active" : ""} type="button" onClick={() => setPlaybackRate(0.75)}>0.75×</button>
        </div>
        <button className={`sentence-loop-button ${loopSentence ? "active" : ""}`}
          type="button" disabled={profile.sentences.length === 0} onClick={toggleSentenceLoop}>
          {loopSentence ? "停止循环" : "循环当前句"}
        </button>
        <span>点击歌词跳转</span>
      </div>

      <div className="legend" aria-label="标记说明">
        <span><b>×</b>吞音(不发音)</span>
        <span><b>‿</b>连读(二合一)</span>
        <span><b>└┘</b>连读(改音)</span>
      </div>

      <div className="lyrics-stage-heading">
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
              双轨歌词
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

      {selectedHint && <HintDetail sentence={profile.sentences.find((sentence) =>
        sentence.languageHints.some((hint) => hint.id === selectedHint.id))}
        initialHintId={selectedHint.id} />}</>}

      {mode === "sing" && <SingingLyrics currentTime={currentTime} sentences={profile.sentences}
        vocalParts={profile.vocalParts} />}
      <div className={mode === "sing" ? "recording-page" : "recording-page hidden"}>
      <RecordingStudio
        songId={profile.songId}
        sentences={profile.sentences}
        vocalParts={profile.vocalParts}
        accompanimentUrl={profile.audio.accompanimentUrl}
        sourceUrl={profile.audio.sourceUrl}
        onTimelineChange={setCurrentTime}
        onRecordingStart={stopReferencePlayback}
        onExclusivePlaybackStart={stopReferencePlayback}
        playbackStopToken={playbackStopToken}
      /></div>

    </section>
  );
}

function displaySongTitle(title: string) {
  return title.replace(/\s*[—-]\s*Language\s*&\s*Vocal\s*Layers\s*$/i, "").trim();
}

function SingingLyrics({ currentTime, sentences, vocalParts }: {
  currentTime: number; sentences: SongSentence[]; vocalParts: VocalPart[];
}) {
  const activeSentence = sentences.find((sentence) => currentTime >= sentence.startSeconds
    && currentTime < sentence.endSeconds);
  const activeParts = vocalParts.filter((part) => currentTime >= part.startSeconds
    && currentTime < part.endSeconds);
  const primary = activeParts.find((part) => part.lane === "primary");
  const secondary = activeParts.find((part) => part.lane === "secondary");
  return <section className="singing-focus" aria-live="polite">
    <p className="singing-primary">{primary ? withoutParenthetical(primary.lyrics)
      : activeSentence?.lyrics ?? "选择一条音轨开始编辑"}</p>
    {secondary && <p className="singing-secondary">{secondary.lyrics}</p>}
  </section>;
}

function AudioPlayer({
  audioRef,
  src,
  playbackRate,
  onTimeChange,
  onPlay,
}: {
  audioRef: React.RefObject<HTMLAudioElement | null>;
  src: string;
  playbackRate: number;
  onTimeChange: (time: number, player: HTMLAudioElement) => void;
  onPlay: () => void;
}) {
  const [playbackMessage, setPlaybackMessage] = useState("正在连接音频资源…");
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = 0.3;
      audioRef.current.playbackRate = playbackRate;
    }
  }, [audioRef, playbackRate, src]);
  return (<div className="audio-player-state">
    <audio
      ref={audioRef}
      controls
      preload="metadata"
      src={src}
      onPlay={onPlay}
      onLoadedMetadata={(event) => {
        event.currentTarget.volume = 0.3;
        event.currentTarget.playbackRate = playbackRate;
        setPlaybackMessage("音频已就绪");
      }}
      onLoadStart={() => setPlaybackMessage("正在连接音频资源…")}
      onWaiting={() => setPlaybackMessage("网络或服务器供给较慢，正在缓冲音频…")}
      onCanPlay={() => setPlaybackMessage("音频已就绪")}
      onPlaying={() => setPlaybackMessage("正在播放")}
      onPause={() => setPlaybackMessage("播放已暂停")}
      onStalled={() => setPlaybackMessage("音频传输暂时中断，正在重新缓冲…")}
      onError={() => setPlaybackMessage("音频读取失败，请刷新后重试")}
      onTimeUpdate={(event) => onTimeChange(event.currentTarget.currentTime, event.currentTarget)}
      onSeeked={(event) => onTimeChange(event.currentTarget.currentTime, event.currentTarget)}
    />
    <small className="audio-playback-message">{playbackMessage}</small>
  </div>);
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
    .filter((part) => part.lane === "primary" && withoutParenthetical(part.lyrics).length > 0)
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
  const annotationText = sentence.pronunciation?.text ?? sentence.lyrics;
  const marksAt = new Map<number, { mark: CharacterMark; hint: LanguageHint }[]>();
  const visibleHints = sentence.languageHints.filter(
    (hint) => !crossesParentheticalLane(sentence, hint),
  );
  for (const hint of visibleHints) {
    for (const mark of hint.marks) {
      const values = marksAt.get(mark.startCharIndex) ?? [];
      values.push({ mark, hint });
      marksAt.set(mark.startCharIndex, values);
      if (mark.symbol === "×") {
        const text = annotationText.toLowerCase();
        const index = mark.startCharIndex;
        if (text[index] === "e" && /[a-z]/.test(text[index - 1] ?? "")
          && !/[a-z]/.test(text[index + 1] ?? "")) {
          const previous = marksAt.get(index - 1) ?? [];
          previous.push({ mark: { ...mark, startCharIndex: index - 1, endCharIndex: index - 1 }, hint });
          marksAt.set(index - 1, previous);
        } else if (/[a-z]/.test(text[index] ?? "") && text[index + 1] === "e"
          && !/[a-z]/.test(text[index + 2] ?? "")) {
          const next = marksAt.get(index + 1) ?? [];
          next.push({ mark: { ...mark, startCharIndex: index + 1, endCharIndex: index + 1 }, hint });
          marksAt.set(index + 1, next);
        }
      }
    }
  }
  const wordRanges = sentence.pronunciation ? [] : findWordRanges(sentence);
  const activeWord = wordRanges.find(
    ({ word }) => currentTime >= word.startSeconds && currentTime < word.endSeconds,
  );

  return (
    <p
      className={`lyric-line ${active ? "active" : ""} ${past ? "past" : ""} ${compact ? "compact" : ""}`}
      data-sentence-id={sentence.id}
      role="button"
      tabIndex={0}
      onClick={() => {
        onSeek(sentence.startSeconds);
        if (visibleHints[0]) onSelect(visibleHints[0]);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onSeek(sentence.startSeconds);
      }}
      title="跳到这句"
    >
      {sentence.pronunciation && <span className="lyric-original">{sentence.lyrics}</span>}
      <span className={sentence.pronunciation ? "lyric-pronunciation" : "lyric-original-only"}>
      {Array.from(annotationText).map((character, index) => (
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
                  {mark.symbol === "└─┘" ? "└┘" : mark.symbol}
                </button>
              ))}
          </span>
        </React.Fragment>
      ))}
      </span>
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

function crossesParentheticalLane(sentence: SongSentence, hint: LanguageHint) {
  if (hint.startWordIndex === undefined || hint.endWordIndex === undefined
    || hint.startWordIndex === hint.endWordIndex) return false;
  const annotationText = sentence.pronunciation?.text ?? sentence.lyrics;
  const words = Array.from(annotationText.matchAll(/[A-Za-z]+(?:['’][A-Za-z]+)*/g));
  const start = words[hint.startWordIndex]?.index;
  const end = words[hint.endWordIndex]?.index;
  if (start === undefined || end === undefined) return false;
  const laneAt = (index: number) => {
    const prefix = sentence.lyrics.slice(0, index);
    return prefix.lastIndexOf("(") > prefix.lastIndexOf(")") ? "secondary" : "primary";
  };
  return laneAt(start) !== laneAt(end);
}

function HintDetail({ sentence, initialHintId }: {
  sentence?: SongSentence; initialHintId: string;
}) {
  const initialHint = sentence?.languageHints.find((hint) => hint.id === initialHintId);
  const selectedLane = sentence && initialHint ? laneForHint(sentence, initialHint) : null;
  const hints = sentence?.languageHints.filter((hint) => !crossesParentheticalLane(sentence, hint)
    && (selectedLane === null || laneForHint(sentence, hint) === selectedLane)) ?? [];
  const initialIndex = Math.max(0, hints.findIndex((hint) => hint.id === initialHintId));
  const [index, setIndex] = useState(initialIndex);
  useEffect(() => setIndex(initialIndex), [initialHintId, initialIndex]);
  if (!sentence || !hints.length) return null;
  const hint = hints[index % hints.length];
  const detail = hint.details.find((item) => item.locale === "zh-CN") ?? hint.details[0];
  if (!detail) return null;
  const mark = hint.marks[0];
  const displayMark = mark?.symbol === "└─┘" ? "└┘" : mark?.symbol ?? "";
  const words = Array.from(sentence.lyrics.matchAll(/[A-Za-z]+(?:['’][A-Za-z]+)*/g));
  const before = [...words].reverse().find((word) => (word.index ?? 0) <= (mark?.startCharIndex ?? 0));
  const after = words.find((word) => (word.index ?? 0) > (mark?.startCharIndex ?? 0));
  const technique = displayMark === "×"
    ? `${before?.[0] ?? "目标音"}${displayMark}${after ? ` ${after[0]}` : ""}`
    : `${before?.[0] ?? ""}${displayMark}${after?.[0] ?? ""}`;
  const count = hints.length;
  return (
    <aside className="hint-detail">
      <button className="hint-arrow" type="button" aria-label="上一个语言点"
        disabled={count < 2} onClick={() => setIndex((index - 1 + count) % count)}>‹</button>
      <div className="hint-content">
        <div className="detail-heading"><TechniqueDisplay value={technique} symbol={displayMark} />
          <span>{index + 1}/{count}</span></div>
        {sentence.pronunciation && <div className="pronunciation-breakdown">
          <p><b>原文：</b>{sentence.lyrics}</p>
          <p><b>辅助读音：</b>{hint.canonicalPronunciation ?? sentence.pronunciation.text}</p>
          {hint.observedPronunciation && <p><b>演唱提示：</b>{hint.observedPronunciation}</p>}
        </div>}
        <p className="action"><b>建议：</b>{detail.action}</p>
        <p><b>专业分析：</b>{detail.explanation}</p>
      </div>
      <button className="hint-arrow" type="button" aria-label="下一个语言点"
        disabled={count < 2} onClick={() => setIndex((index + 1) % count)}>›</button>
    </aside>
  );
}

function laneForHint(sentence: SongSentence, hint: LanguageHint) {
  const index = hint.marks[0]?.startCharIndex ?? 0;
  const prefix = sentence.lyrics.slice(0, index);
  return prefix.lastIndexOf("(") > prefix.lastIndexOf(")") ? "secondary" : "primary";
}

function TechniqueDisplay({ value, symbol }: { value: string; symbol: string }) {
  const parts = value.split(symbol);
  const left = parts[0] ?? "";
  const right = parts[1] ?? "";
  const before = Array.from(left);
  const after = Array.from(right);
  const markClass = symbol === "×" ? "elision" : symbol === "‿" ? "boundary link" : "boundary merge";
  return <strong className="technique-display">
    {before.map((character, index) => <span className="lyric-character" key={`before-${index}`}>
      {character}{(index === before.length - 1 || (symbol === "×"
        && before.at(-1)?.toLowerCase() === "e" && index === before.length - 2))
        && <i className={`character-mark below ${markClass}`}>
        {symbol}</i>}
    </span>)}
    {after.length > 0 && <span className="technique-gap"> </span>}
    {after.map((character, index) => <span className="lyric-character" key={`after-${index}`}>{character}</span>)}
  </strong>;
}

function formatDuration(seconds: number) {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds - minutes * 60);
  return remaining ? `${minutes} 分 ${remaining} 秒` : `${minutes} 分钟`;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
