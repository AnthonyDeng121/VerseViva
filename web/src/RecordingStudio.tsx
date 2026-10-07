import { useEffect, useMemo, useRef, useState } from "react";

type RecordingSentence = {
  id: string;
  startSeconds: number;
  endSeconds: number;
  lyrics: string;
};

type RecordingVocalPart = {
  id: string;
  lane: "primary" | "secondary";
  role: string;
  lyrics: string;
  startSeconds: number;
  endSeconds: number;
  sentenceIds?: string[];
};

type PracticeOption = {
  id: string; label: string; startSeconds: number; endSeconds: number;
  sentenceIds: string[]; vocalPartId?: string;
};

type RecordingTake = {
  takeId: string;
  sessionId: string;
  trackSlotId: string;
  selectionType: "sentence" | "segment";
  sentenceIds: string[];
  vocalPartId?: string | null;
  selectionStartSeconds: number;
  selectionEndSeconds: number;
  timelineStartSeconds: number;
  saveMode: "practice_replace" | "overdub_append";
  audioUrl: string;
  mimeType: string;
  gain?: number;
  muted?: boolean;
  isCurrent: boolean;
  supersededByTakeId?: string | null;
  createdAt: string;
};

type PracticeAttempt = {
  attemptId: string;
  takeId: string;
  status: "analyzed" | "insufficient_data" | "failed";
  issues: { issueId: string; type: string; wordText: string; confidence: number }[];
  recommendations: {
    rank: number;
    issueId: string;
    headline: string;
    observation: string;
    action: string;
  }[];
  comparison: {
    result: "first_attempt" | "improved" | "unchanged" | "regressed" | "insufficient_data";
  };
  insufficientReason?: string | null;
  createdAt: string;
};

type PracticeMemory = {
  totalAttempts: number;
  reliableAttempts: number;
  phenomena: { issueType: string; issueCount: number; recentIssueCount: number; trend: string }[];
};

type RecorderState =
  | "idle"
  | "requesting"
  | "recording"
  | "preview"
  | "uploading"
  | "uploaded";

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
  "audio/webm",
  "audio/ogg;codecs=opus",
];

function recordingExtension(mimeType: string) {
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("wav")) return "wav";
  return "webm";
}

function getOrCreateSessionId(songId: string) {
  const key = `verseviva.recordingSession.${songId}`;
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const random = typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const created = `session_${random}`;
  window.localStorage.setItem(key, created);
  return created;
}

export function RecordingStudio({
  songId,
  sentences,
  vocalParts,
  accompanimentUrl,
  onTimelineChange,
}: {
  songId: string;
  sentences: RecordingSentence[];
  vocalParts: RecordingVocalPart[];
  accompanimentUrl?: string | null;
  onTimelineChange?: (time: number) => void;
}) {
  const [startIndex, setStartIndex] = useState(0);
  const [endIndex, setEndIndex] = useState(0);
  const [lane, setLane] = useState<"primary" | "secondary">("primary");
  const [state, setState] = useState<RecorderState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [takes, setTakes] = useState<RecordingTake[]>([]);
  const [attempts, setAttempts] = useState<PracticeAttempt[]>([]);
  const [memory, setMemory] = useState<PracticeMemory | null>(null);
  const [analyzingTakeId, setAnalyzingTakeId] = useState<string | null>(null);
  const [selectedTake, setSelectedTake] = useState<RecordingTake | null>(null);
  const [accompanimentVolume, setAccompanimentVolume] = useState(0.55);
  const [voiceVolume, setVoiceVolume] = useState(1);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const stopTimerRef = useRef<number | null>(null);
  const accompanimentRef = useRef<HTMLAudioElement>(null);
  const voiceRef = useRef<HTMLAudioElement>(null);
  const mixContextRef = useRef<AudioContext | null>(null);
  const sessionId = useMemo(() => getOrCreateSessionId(songId), [songId]);

  const practiceOptions = useMemo<PracticeOption[]>(() => {
    const laneParts = vocalParts.filter((part) => part.lane === lane)
      .sort((left, right) => left.startSeconds - right.startSeconds);
    if (laneParts.length) return laneParts.map((part) => ({
      id: part.id, label: part.lyrics.replace(/^\(|\)$/g, ""),
      startSeconds: part.startSeconds, endSeconds: part.endSeconds,
      sentenceIds: part.sentenceIds?.length ? part.sentenceIds : sentences
        .filter((sentence) => sentence.startSeconds < part.endSeconds
          && sentence.endSeconds > part.startSeconds).map((sentence) => sentence.id),
      vocalPartId: part.id,
    }));
    if (lane === "secondary") return [];
    return sentences.map((sentence) => ({ id: sentence.id, label: sentence.lyrics,
      startSeconds: sentence.startSeconds, endSeconds: sentence.endSeconds,
      sentenceIds: [sentence.id] }));
  }, [lane, sentences, vocalParts]);
  const safeStartIndex = Math.min(startIndex, Math.max(practiceOptions.length - 1, 0));
  const safeEndIndex = Math.max(safeStartIndex, Math.min(endIndex, Math.max(practiceOptions.length - 1, 0)));
  const selectedOptions = practiceOptions.slice(safeStartIndex, safeEndIndex + 1);
  const selectionType = safeStartIndex === safeEndIndex ? "sentence" : "segment";
  const selectionStart = selectedOptions[0]?.startSeconds ?? 0;
  const selectionEnd = selectedOptions.at(-1)?.endSeconds ?? 0;
  const activePreviewUrl = previewUrl ?? selectedTake?.audioUrl ?? null;
  const activePreviewStart = selectedTake?.selectionStartSeconds ?? selectionStart;
  const activePreviewEnd = selectedTake?.selectionEndSeconds ?? selectionEnd;
  const selectedVocalPartId = selectedOptions.length === 1 ? selectedOptions[0]?.vocalPartId : undefined;

  useEffect(() => { setStartIndex(0); setEndIndex(0); }, [lane, songId]);

  useEffect(() => {
    let cancelled = false;
    void fetch(`/api/v1/songs/${songId}/takes?session_id=${encodeURIComponent(sessionId)}`)
      .then((response) => {
        if (!response.ok) throw new Error("恢复本次练唱录音失败");
        return response.json() as Promise<RecordingTake[]>;
      })
      .then((items) => {
        if (!cancelled) setTakes(items);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "恢复录音失败");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, songId]);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      fetch(`/api/v1/songs/${songId}/attempts?session_id=${encodeURIComponent(sessionId)}`),
      fetch(`/api/v1/practice/memory?session_id=${encodeURIComponent(sessionId)}`),
    ]).then(async ([attemptResponse, memoryResponse]) => {
      if (!attemptResponse.ok || !memoryResponse.ok) throw new Error("恢复练唱记忆失败");
      const [restoredAttempts, restoredMemory] = await Promise.all([
        attemptResponse.json() as Promise<PracticeAttempt[]>,
        memoryResponse.json() as Promise<PracticeMemory>,
      ]);
      if (!cancelled) {
        setAttempts(restoredAttempts);
        setMemory(restoredMemory);
      }
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : "恢复练唱记忆失败");
    });
    return () => { cancelled = true; };
  }, [sessionId, songId]);

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    if (stopTimerRef.current !== null) window.clearTimeout(stopTimerRef.current);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    void mixContextRef.current?.close();
  }, [previewUrl]);

  useEffect(() => {
    if (accompanimentRef.current) accompanimentRef.current.volume = accompanimentVolume;
  }, [accompanimentVolume]);

  useEffect(() => {
    if (voiceRef.current) voiceRef.current.volume = voiceVolume;
  }, [voiceVolume]);

  function resetPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setPreviewBlob(null);
    setSelectedTake(null);
    setState("idle");
  }

  async function startRecording() {
    setError(null);
    resetPreview();
    if (!window.isSecureContext) {
      setError("手机麦克风需要 HTTPS 安全连接，请使用移动端 HTTPS 预览地址。");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("当前浏览器不支持麦克风录音，请使用新版 Safari 或 Chrome。");
      return;
    }
    if (!selectedOptions.length || selectionEnd <= selectionStart) {
      setError("请先选择有效的单句或片段。");
      return;
    }

    setState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
          channelCount: 1,
        },
      });
      streamRef.current = stream;
      const mimeType = MIME_CANDIDATES.find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => setError("录音被浏览器中断，请重试。");
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || mimeType || "audio/webm",
        });
        const url = URL.createObjectURL(blob);
        setPreviewBlob(blob);
        setPreviewUrl(url);
        setState("preview");
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        accompanimentRef.current?.pause();
      };

      recorder.start(250);
      setState("recording");
      if (accompanimentRef.current && accompanimentUrl) {
        accompanimentRef.current.currentTime = selectionStart;
        accompanimentRef.current.volume = accompanimentVolume;
        await accompanimentRef.current.play();
      }
      stopTimerRef.current = window.setTimeout(
        () => stopRecording(),
        Math.max((selectionEnd - selectionStart) * 1000, 500),
      );
    } catch (reason) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setState("idle");
      const name = reason instanceof DOMException ? reason.name : "";
      setError(
        name === "NotAllowedError"
          ? "麦克风权限被拒绝，请在浏览器网站设置中允许后重试。"
          : reason instanceof Error ? reason.message : "无法启动录音。",
      );
    }
  }

  function stopRecording() {
    if (stopTimerRef.current !== null) {
      window.clearTimeout(stopTimerRef.current);
      stopTimerRef.current = null;
    }
    const recorder = recorderRef.current;
    if (recorder?.state === "recording") recorder.stop();
    accompanimentRef.current?.pause();
  }

  async function uploadRecording() {
    if (!previewBlob) return;
    setState("uploading");
    setError(null);
    const selectedIds = Array.from(new Set(selectedOptions.flatMap((option) => option.sentenceIds)));
    const form = new FormData();
    form.set(
      "audio",
      previewBlob,
      `recording.${recordingExtension(previewBlob.type)}`,
    );
    form.set("session_id", sessionId);
    form.set(
      "track_slot_id",
      `${lane}:${selectedIds.join("+")}`,
    );
    form.set("selection_type", selectionType);
    form.set("sentence_ids", JSON.stringify(selectedIds));
    form.set("selection_start_seconds", String(selectionStart));
    form.set("selection_end_seconds", String(selectionEnd));
    form.set("timeline_start_seconds", String(selectionStart));
    form.set("save_mode", "overdub_append");
    form.set("client_duration_seconds", String(selectionEnd - selectionStart));
    if (selectedVocalPartId) form.set("vocal_part_id", selectedVocalPartId);

    try {
      const response = await fetch(`/api/v1/songs/${songId}/takes`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "录音上传失败");
      }
      const created = await response.json() as RecordingTake;
      const restored = await fetch(
        `/api/v1/songs/${songId}/takes?session_id=${encodeURIComponent(sessionId)}`,
      );
      setTakes(restored.ok ? await restored.json() as RecordingTake[] : [...takes, created]);
      setSelectedTake(created);
      setState("uploaded");
      await analyzeTake(created.takeId);
    } catch (reason) {
      setState("preview");
      setError(reason instanceof Error ? reason.message : "录音上传失败");
    }
  }

  async function analyzeTake(takeId: string) {
    setAnalyzingTakeId(takeId);
    try {
      const response = await fetch(`/api/v1/takes/${takeId}/analyze`, { method: "POST" });
      if (!response.ok) {
        const payload = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "本次练唱分析失败");
      }
      const attempt = await response.json() as PracticeAttempt;
      setAttempts((current) => [...current.filter((item) => item.takeId !== takeId), attempt]);
      const memoryResponse = await fetch(
        `/api/v1/practice/memory?session_id=${encodeURIComponent(sessionId)}`,
      );
      if (memoryResponse.ok) setMemory(await memoryResponse.json() as PracticeMemory);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "本次练唱分析失败");
    } finally {
      setAnalyzingTakeId(null);
    }
  }

  async function playMix() {
    if (!voiceRef.current || !activePreviewUrl) return;
    setError(null);
    voiceRef.current.currentTime = 0;
    voiceRef.current.volume = voiceVolume;
    const starts: Promise<void>[] = [voiceRef.current.play()];
    if (accompanimentRef.current && accompanimentUrl) {
      accompanimentRef.current.currentTime = activePreviewStart;
      accompanimentRef.current.volume = accompanimentVolume;
      starts.push(accompanimentRef.current.play());
    }
    try {
      await Promise.all(starts);
    } catch {
      setError("浏览器阻止了播放，请再点一次混合试听。");
    }
  }

  function stopMix() {
    voiceRef.current?.pause();
    accompanimentRef.current?.pause();
  }

  async function playAllTakes() {
    const activeTakes = takes.filter((take) => take.isCurrent && !take.muted);
    if (!activeTakes.length) return;
    stopAllTakes();
    setError(null);
    try {
      const AudioContextClass = window.AudioContext;
      const context = new AudioContextClass();
      mixContextRef.current = context;
      await context.resume();
      const decoded = await Promise.all(activeTakes.map(async (take) => {
        const response = await fetch(take.audioUrl);
        if (!response.ok) throw new Error("读取已保存录音失败");
        return context.decodeAudioData(await response.arrayBuffer());
      }));
      const timelineStart = Math.min(...activeTakes.map((take) => take.timelineStartSeconds));
      const audioStart = context.currentTime + 0.08;
      decoded.forEach((buffer, index) => {
        const take = activeTakes[index];
        const source = context.createBufferSource();
        const gain = context.createGain();
        gain.gain.value = take.gain ?? 1;
        source.buffer = buffer;
        source.connect(gain).connect(context.destination);
        source.start(audioStart + Math.max(0, take.timelineStartSeconds - timelineStart));
      });
      if (accompanimentRef.current && accompanimentUrl) {
        accompanimentRef.current.currentTime = timelineStart;
        accompanimentRef.current.volume = accompanimentVolume;
        await accompanimentRef.current.play();
      }
      onTimelineChange?.(timelineStart);
    } catch (reason) {
      stopAllTakes();
      setError(reason instanceof Error ? reason.message : "无法播放全部轨道");
    }
  }

  function stopAllTakes() {
    accompanimentRef.current?.pause();
    const context = mixContextRef.current;
    mixContextRef.current = null;
    if (context && context.state !== "closed") void context.close();
  }

  if (!sentences.length) return null;

  return (
    <section className="recording-studio" aria-label="用户练唱录音">
      <div className="recording-heading">
        <div>
          <p className="eyebrow">PRACTICE TAKE</p>
          <h3>选择轨道与练唱范围</h3>
        </div>
        <span className={window.isSecureContext ? "secure-ok" : "secure-warning"}>
          {window.isSecureContext ? "麦克风环境可用" : "需要 HTTPS"}
        </span>
      </div>

      <div className="recording-mode-switch" role="group" aria-label="演唱轨道">
        <button type="button" className={lane === "primary" ? "active" : ""}
          onClick={() => setLane("primary")}>主轨</button>
        <button type="button" className={lane === "secondary" ? "active" : ""}
          onClick={() => setLane("secondary")}>次轨</button>
      </div>

      <div className="recording-selectors">
        <label>
          <span>起始句</span>
          <select value={safeStartIndex} onChange={(event) => {
            const next = Number(event.target.value);
            setStartIndex(next);
            if (endIndex < next) setEndIndex(next);
          }}>
            {practiceOptions.map((option, index) => <option value={index} key={option.id}>
              {index + 1}. {option.label}
            </option>)}
          </select>
        </label>
        <label>
          <span>结束句</span>
          <select value={safeEndIndex} onChange={(event) => setEndIndex(Number(event.target.value))}>
            {practiceOptions.map((option, index) => <option value={index} disabled={index < safeStartIndex}
              key={option.id}>{index + 1}. {option.label}</option>)}
          </select>
        </label>
      </div>

      <p className="recording-selection-summary">
        {lane === "primary" ? "主轨" : "次轨"} · {formatTime(selectionStart)} – {formatTime(selectionEnd)}
        · {selectedOptions.length === 1 ? "单句" : `${selectedOptions.length} 句`}
      </p>
      {practiceOptions.length === 0 && <p className="recording-warning">这首歌没有可练习的次轨歌词。</p>}
      <p className="headphone-note">建议戴耳机录制，避免伴奏被麦克风再次收录。</p>

      <div className="recording-actions">
        {state !== "recording"
          ? <button type="button" className="primary-button"
              onClick={() => void startRecording()} disabled={state === "requesting" || state === "uploading" || practiceOptions.length === 0}>
              {state === "requesting" ? "正在请求麦克风…" : "开始录音"}
            </button>
          : <button type="button" className="record-stop-button" onClick={stopRecording}>停止录音</button>}
        {previewBlob && <button type="button" className="secondary-button"
          disabled={state === "uploading"} onClick={() => void uploadRecording()}>
          {state === "uploading" ? "正在上传…" : "保留这一遍"}
        </button>}
        {previewBlob && <button type="button" className="secondary-button" onClick={resetPreview}>丢弃并重录</button>}
      </div>

      {error && <p className="recording-error">{error}</p>}
      {state === "recording" && <p className="recording-live">● 正在录制；到片段结尾会自动停止</p>}
      {analyzingTakeId && <p className="recording-live">正在听这一遍的语言动作并更新练唱记忆…</p>}

      {attempts.length > 0 && <PracticeFeedback attempt={attempts.at(-1)!} memory={memory} />}

      {activePreviewUrl && <div className="mix-preview">
        <h4>伴奏 + 用户人声混合试听</h4>
        <div className="volume-controls">
          <label><span>伴奏 {Math.round(accompanimentVolume * 100)}%</span>
            <input type="range" min="0" max="1" step="0.01" value={accompanimentVolume}
              onChange={(event) => setAccompanimentVolume(Number(event.target.value))} /></label>
          <label><span>用户人声 {Math.round(voiceVolume * 100)}%</span>
            <input type="range" min="0" max="1" step="0.01" value={voiceVolume}
              onChange={(event) => setVoiceVolume(Number(event.target.value))} /></label>
        </div>
        <div className="recording-actions">
          <button type="button" className="secondary-button" onClick={() => void playMix()}>混合试听</button>
          <button type="button" className="secondary-button" onClick={stopMix}>停止试听</button>
        </div>
        <audio controls ref={voiceRef} src={activePreviewUrl}
          onPlay={() => {
            if (accompanimentRef.current && accompanimentUrl) {
              accompanimentRef.current.currentTime = activePreviewStart + (voiceRef.current?.currentTime ?? 0);
              void accompanimentRef.current.play().catch(() => undefined);
            }
          }}
          onPause={() => accompanimentRef.current?.pause()}
          onTimeUpdate={(event) => onTimelineChange?.(activePreviewStart + event.currentTarget.currentTime)}
          onEnded={() => accompanimentRef.current?.pause()} />
      </div>}

      {accompanimentUrl
        ? <audio ref={accompanimentRef} src={accompanimentUrl} preload="metadata"
            onTimeUpdate={(event) => {
              if (state === "recording") onTimelineChange?.(event.currentTarget.currentTime);
            }} />
        : <p className="recording-warning">当前 Profile 没有 Demucs 伴奏资产，可录音但无法混合伴奏。</p>}

      {takes.length > 0 && <div className="take-history">
        <div className="take-history-heading">
          <h4>本次演唱的 Take</h4>
          <div className="recording-actions">
            <button type="button" className="primary-button" onClick={() => void playAllTakes()}>
              全部轨道试听
            </button>
            <button type="button" className="secondary-button" onClick={stopAllTakes}>停止</button>
          </div>
        </div>
        {[...takes].reverse().map((take) => <article key={take.takeId}
          className={`take-row ${take.isCurrent ? "current" : "history"}`}>
          <div><strong>{take.saveMode === "overdub_append" ? "叠唱 Take" : "普通练唱"}</strong>
            <small>{take.isCurrent ? "当前采用" : "历史版本"} · {formatTime(take.selectionStartSeconds)}
              – {formatTime(take.selectionEndSeconds)}</small></div>
          <div className="take-row-actions">
            <button type="button" className="secondary-button" onClick={() => {
              if (previewUrl) URL.revokeObjectURL(previewUrl);
              setPreviewUrl(null);
              setPreviewBlob(null);
              setSelectedTake(take);
            }}>加载混合试听</button>
            {attempts.find((item) => item.takeId === take.takeId)?.status !== "analyzed" &&
              <button type="button" className="secondary-button"
                disabled={analyzingTakeId === take.takeId}
                onClick={() => void analyzeTake(take.takeId)}>
                {analyzingTakeId === take.takeId
                  ? "分析中…"
                  : attempts.some((item) => item.takeId === take.takeId)
                    ? "重新分析并记住"
                    : "分析并记住"}
              </button>}
          </div>
        </article>)}
      </div>}
      {selectedTake && <p className="recording-selection-summary">
        正在试听已保留 Take：{formatTime(activePreviewStart)} – {formatTime(activePreviewEnd)}
      </p>}
    </section>
  );
}

function PracticeFeedback({ attempt, memory }: {
  attempt: PracticeAttempt;
  memory: PracticeMemory | null;
}) {
  const comparisonLabels = {
    first_attempt: "这是这个片段的第一遍可靠记录",
    improved: "与上一遍相比，这次有改善",
    unchanged: "与上一遍相比，主要问题暂未变化",
    regressed: "这次出现了新的重点，可再试一遍",
    insufficient_data: "本次证据不足，未计入趋势",
  };
  return <section className="practice-feedback" aria-live="polite">
    <div className="practice-feedback-heading">
      <div>
        <p className="eyebrow">本次建议</p>
        <h4>{attempt.status === "analyzed" ? comparisonLabels[attempt.comparison.result] : "暂不下结论"}</h4>
      </div>
      {memory && <span>{memory.reliableAttempts}/{memory.totalAttempts} 次可靠分析</span>}
    </div>
    {attempt.status === "insufficient_data"
      ? <p className="recording-warning">{attempt.insufficientReason ?? "本次录音不足以可靠判断，请重录。"}</p>
      : attempt.recommendations.length > 0
        ? <ol className="practice-recommendations">
            {attempt.recommendations.map((item) => <li key={item.issueId}>
              <strong>{item.headline}</strong>
              <p>{item.observation}</p>
              <p className="practice-action">下一遍：{item.action}</p>
            </li>)}
          </ol>
        : <p className="practice-success">现有目标没有发现可靠差异，这一遍会作为成功记录保留。</p>}
    {memory && memory.phenomena.length > 0 && <div className="memory-summary">
      <strong>练唱记忆</strong>
      <p>{memory.phenomena.slice(0, 2).map((item) =>
        `${issueTypeLabel(item.issueType)}：累计 ${item.issueCount} 次${item.trend === "improving" ? "，近期在改善" : ""}`,
      ).join("；")}</p>
    </div>}
  </section>;
}

function issueTypeLabel(issueType: string) {
  return ({
    expected_elision_realized: "尾音多释放",
    identical_consonants_separated: "相同辅音分开",
    coalescent_assimilation_missing: "融合动作缺失",
    target_phoneme_omitted: "目标音遗漏",
  } as Record<string, string>)[issueType] ?? issueType;
}

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${(seconds - minutes * 60).toFixed(1).padStart(4, "0")}`;
}
