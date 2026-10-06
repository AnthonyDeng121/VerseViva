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
  isCurrent: boolean;
  supersededByTakeId?: string | null;
  createdAt: string;
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
  const [selectionType, setSelectionType] = useState<"sentence" | "segment">("sentence");
  const [startIndex, setStartIndex] = useState(0);
  const [endIndex, setEndIndex] = useState(0);
  const [vocalPartId, setVocalPartId] = useState("");
  const [saveMode, setSaveMode] = useState<"practice_replace" | "overdub_append">(
    "practice_replace",
  );
  const [state, setState] = useState<RecorderState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [takes, setTakes] = useState<RecordingTake[]>([]);
  const [selectedTake, setSelectedTake] = useState<RecordingTake | null>(null);
  const [accompanimentVolume, setAccompanimentVolume] = useState(0.55);
  const [voiceVolume, setVoiceVolume] = useState(1);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const stopTimerRef = useRef<number | null>(null);
  const accompanimentRef = useRef<HTMLAudioElement>(null);
  const voiceRef = useRef<HTMLAudioElement>(null);
  const sessionId = useMemo(() => getOrCreateSessionId(songId), [songId]);

  const safeStartIndex = Math.min(startIndex, Math.max(sentences.length - 1, 0));
  const safeEndIndex = selectionType === "sentence"
    ? safeStartIndex
    : Math.max(safeStartIndex, Math.min(endIndex, Math.max(sentences.length - 1, 0)));
  const selectedSentences = sentences.slice(safeStartIndex, safeEndIndex + 1);
  const selectionStart = selectedSentences[0]?.startSeconds ?? 0;
  const selectionEnd = selectedSentences.at(-1)?.endSeconds ?? 0;
  const activePreviewUrl = previewUrl ?? selectedTake?.audioUrl ?? null;
  const activePreviewStart = selectedTake?.selectionStartSeconds ?? selectionStart;
  const activePreviewEnd = selectedTake?.selectionEndSeconds ?? selectionEnd;

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

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    if (stopTimerRef.current !== null) window.clearTimeout(stopTimerRef.current);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
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
    if (!selectedSentences.length || selectionEnd <= selectionStart) {
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
    const selectedIds = selectedSentences.map((sentence) => sentence.id);
    const form = new FormData();
    form.set(
      "audio",
      previewBlob,
      `recording.${recordingExtension(previewBlob.type)}`,
    );
    form.set("session_id", sessionId);
    form.set(
      "track_slot_id",
      `${selectionType}:${selectedIds.join("+")}:${vocalPartId || "unassigned"}`,
    );
    form.set("selection_type", selectionType);
    form.set("sentence_ids", JSON.stringify(selectedIds));
    form.set("selection_start_seconds", String(selectionStart));
    form.set("selection_end_seconds", String(selectionEnd));
    form.set("timeline_start_seconds", String(selectionStart));
    form.set("save_mode", saveMode);
    form.set("client_duration_seconds", String(selectionEnd - selectionStart));
    if (vocalPartId) form.set("vocal_part_id", vocalPartId);

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
    } catch (reason) {
      setState("preview");
      setError(reason instanceof Error ? reason.message : "录音上传失败");
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

  if (!sentences.length) return null;

  return (
    <section className="recording-studio" aria-label="用户练唱录音">
      <div className="recording-heading">
        <div>
          <p className="eyebrow">PRACTICE TAKE</p>
          <h3>练唱这一句或这一段</h3>
        </div>
        <span className={window.isSecureContext ? "secure-ok" : "secure-warning"}>
          {window.isSecureContext ? "麦克风环境可用" : "需要 HTTPS"}
        </span>
      </div>

      <div className="recording-mode-switch">
        <button type="button" className={selectionType === "sentence" ? "active" : ""}
          onClick={() => { setSelectionType("sentence"); setEndIndex(startIndex); }}>单句</button>
        <button type="button" className={selectionType === "segment" ? "active" : ""}
          onClick={() => setSelectionType("segment")}>一段</button>
      </div>

      <div className="recording-selectors">
        <label>
          <span>{selectionType === "sentence" ? "选择句子" : "起始句"}</span>
          <select value={safeStartIndex} onChange={(event) => {
            const next = Number(event.target.value);
            setStartIndex(next);
            if (selectionType === "sentence" || endIndex < next) setEndIndex(next);
          }}>
            {sentences.map((sentence, index) => <option value={index} key={sentence.id}>
              {index + 1}. {sentence.lyrics}
            </option>)}
          </select>
        </label>
        {selectionType === "segment" && <label>
          <span>结束句</span>
          <select value={safeEndIndex} onChange={(event) => setEndIndex(Number(event.target.value))}>
            {sentences.map((sentence, index) => <option value={index} disabled={index < safeStartIndex}
              key={sentence.id}>{index + 1}. {sentence.lyrics}</option>)}
          </select>
        </label>}
        <label>
          <span>Vocal Part（可选）</span>
          <select value={vocalPartId} onChange={(event) => setVocalPartId(event.target.value)}>
            <option value="">未指定 / 普通练唱</option>
            {vocalParts.map((part) => <option value={part.id} key={part.id}>
              {part.lane} · {part.role} · {part.lyrics}
            </option>)}
          </select>
        </label>
      </div>

      <div className="take-save-mode">
        <label><input type="radio" checked={saveMode === "practice_replace"}
          onChange={() => setSaveMode("practice_replace")} />
          普通重唱：替换本次演唱轨的当前版本</label>
        <label><input type="radio" checked={saveMode === "overdub_append"}
          onChange={() => setSaveMode("overdub_append")} />
          叠唱追加：保留每一条 Take</label>
      </div>

      <p className="recording-selection-summary">
        {formatTime(selectionStart)} – {formatTime(selectionEnd)} · {selectedSentences.length} 句
      </p>
      <p className="headphone-note">建议戴耳机录制，避免伴奏被麦克风再次收录。</p>

      <div className="recording-actions">
        {state !== "recording"
          ? <button type="button" className="primary-button" disabled={state === "requesting" || state === "uploading"}
              onClick={() => void startRecording()}>
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
        <h4>本次演唱的 Take</h4>
        {[...takes].reverse().map((take) => <article key={take.takeId}
          className={`take-row ${take.isCurrent ? "current" : "history"}`}>
          <div><strong>{take.saveMode === "overdub_append" ? "叠唱 Take" : "普通练唱"}</strong>
            <small>{take.isCurrent ? "当前采用" : "历史版本"} · {formatTime(take.selectionStartSeconds)}
              – {formatTime(take.selectionEndSeconds)}</small></div>
          <button type="button" className="secondary-button" onClick={() => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            setPreviewUrl(null);
            setPreviewBlob(null);
            setSelectedTake(take);
          }}>加载混合试听</button>
        </article>)}
      </div>}
      {selectedTake && <p className="recording-selection-summary">
        正在试听已保留 Take：{formatTime(activePreviewStart)} – {formatTime(activePreviewEnd)}
      </p>}
    </section>
  );
}

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${(seconds - minutes * 60).toFixed(1).padStart(4, "0")}`;
}
