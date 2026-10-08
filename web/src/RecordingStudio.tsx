import { useEffect, useMemo, useRef, useState } from "react";

import type { RecorderState } from "./audioTimeline";
import { MixTimeline } from "./MixTimeline";
import { PracticeFeedback } from "./PracticeFeedback";

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
  displayName: string;
  sessionId: string;
  trackSlotId: string;
  selectionType: "sentence" | "segment";
  sentenceIds: string[];
  vocalPartId?: string | null;
  selectionStartSeconds: number;
  selectionEndSeconds: number;
  timelineStartSeconds: number;
  saveMode: "practice_replace" | "overdub_append";
  purpose: "guided_practice" | "free_overdub";
  audioUrl: string;
  mimeType: string;
  gain?: number;
  latencyCompensationMs?: number;
  manualOffsetMs?: number;
  muted?: boolean;
  isCurrent: boolean;
  supersededByTakeId?: string | null;
  createdAt: string;
};

export type PracticeAttempt = {
  attemptId: string;
  takeId: string;
  trackSlotId: string;
  sentenceIds: string[];
  status: "analyzed" | "insufficient_data" | "failed";
  issues: { issueId: string; type: string; sentenceId: string; wordText: string; confidence: number }[];
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
  sentenceComparisons?: Record<string, {
    result: "first_attempt" | "improved" | "unchanged" | "regressed" | "insufficient_data";
  }>;
  insufficientReason?: string | null;
  createdAt: string;
};

export type PracticeMemory = {
  totalAttempts: number;
  reliableAttempts: number;
  phenomena: { issueType: string; issueCount: number; recentIssueCount: number; trend: string }[];
};

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
  "audio/webm",
  "audio/ogg;codecs=opus",
];
const DEFAULT_RECORDING_ADVANCE_MS = 500;

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
  sourceUrl,
  onTimelineChange,
  onRecordingStart,
  onRecordingFinished,
  onExclusivePlaybackStart,
  playbackStopToken,
}: {
  songId: string;
  sentences: RecordingSentence[];
  vocalParts: RecordingVocalPart[];
  accompanimentUrl?: string | null;
  sourceUrl?: string | null;
  onTimelineChange?: (time: number) => void;
  onRecordingStart?: () => void;
  onRecordingFinished?: () => void;
  onExclusivePlaybackStart?: () => void;
  playbackStopToken?: number;
}) {
  const [startIndex, setStartIndex] = useState(0);
  const [endIndex, setEndIndex] = useState(0);
  const [lane, setLane] = useState<"primary" | "secondary">("primary");
  const [purpose, setPurpose] = useState<"guided_practice" | "free_overdub">("guided_practice");
  const [recordingReference, setRecordingReference] = useState<"accompaniment" | "source">("accompaniment");
  const [state, setState] = useState<RecorderState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [takes, setTakes] = useState<RecordingTake[]>([]);
  const [attempts, setAttempts] = useState<PracticeAttempt[]>([]);
  const [memory, setMemory] = useState<PracticeMemory | null>(null);
  const [analyzingTakeId, setAnalyzingTakeId] = useState<string | null>(null);
  const [accompanimentVolume, setAccompanimentVolume] = useState(0.55);
  const [mixVoiceVolume, setMixVoiceVolume] = useState(1);
  const [previewVoiceVolume, setPreviewVoiceVolume] = useState(1);
  const [previewOffsetMs, setPreviewOffsetMs] = useState(0);
  const [editingTakeId, setEditingTakeId] = useState<string | null>(null);
  const [mixOpen, setMixOpen] = useState(false);
  const [downloadingMix, setDownloadingMix] = useState(false);
  const [resourcesReady, setResourcesReady] = useState(false);
  const [preparedAccompanimentUrl, setPreparedAccompanimentUrl] = useState<string | null>(null);
  const [preparedSourceUrl, setPreparedSourceUrl] = useState<string | null>(null);
  const [playbackProgress, setPlaybackProgress] = useState(0);
  const [playbackDuration, setPlaybackDuration] = useState(0);
  const [playingLabel, setPlayingLabel] = useState<string | null>(null);
  const [playingTakeId, setPlayingTakeId] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const stopTimerRef = useRef<number | null>(null);
  const accompanimentRef = useRef<HTMLAudioElement>(null);
  const sourceRef = useRef<HTMLAudioElement>(null);
  const previewAudioRef = useRef<HTMLAudioElement>(null);
  const singleTakeAudioRef = useRef<HTMLAudioElement | null>(null);
  const sessionId = useMemo(() => getOrCreateSessionId(songId), [songId]);

  const practiceOptions = useMemo<PracticeOption[]>(() => {
    const laneParts = vocalParts.filter((part) => part.lane === lane
      && (part.lane === "secondary" || part.lyrics.replace(/\s*\([^)]*\)/g, "").trim().length > 0))
      .sort((left, right) => left.startSeconds - right.startSeconds);
    if (laneParts.length) return laneParts.map((part) => ({
      id: part.id, label: part.lane === "primary"
        ? part.lyrics.replace(/\s*\([^)]*\)/g, "").trim()
        : part.lyrics.replace(/^\(|\)$/g, ""),
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
  const selectedVocalPartId = selectedOptions.length === 1 ? selectedOptions[0]?.vocalPartId : undefined;
  const editingTake = takes.find((take) => take.takeId === editingTakeId) ?? null;

  useEffect(() => {
    let cancelled = false;
    const objectUrls: string[] = [];
    setResourcesReady(false);
    void Promise.all([accompanimentUrl, sourceUrl].map(async (url) => {
      if (!url) return null;
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 60_000);
      try {
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) throw new Error("读取演唱音频资源失败");
        const objectUrl = URL.createObjectURL(await response.blob());
        objectUrls.push(objectUrl);
        return objectUrl;
      } catch (reason) {
        throw new Error(reason instanceof DOMException && reason.name === "AbortError"
          ? "演唱资源下载超时，请检查网络后刷新重试。"
          : "演唱资源未能完整下载，暂不能开始录音。", { cause: reason });
      } finally {
        window.clearTimeout(timeout);
      }
    })).then(([accompaniment, source]) => {
      if (cancelled) return;
      setPreparedAccompanimentUrl(accompaniment);
      setPreparedSourceUrl(source);
      setResourcesReady(true);
    }).catch((reason: unknown) => {
      if (!cancelled) {
        setResourcesReady(false);
        setError(reason instanceof Error ? reason.message : "音频资源准备失败");
      }
    });
    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [accompanimentUrl, sourceUrl]);

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
    singleTakeAudioRef.current?.pause();
  }, [previewUrl]);

  useEffect(() => {
    previewAudioRef.current?.pause();
    sourceRef.current?.pause();
    stopPlayback();
  }, [playbackStopToken]);

  useEffect(() => {
    if (accompanimentRef.current) accompanimentRef.current.volume = accompanimentVolume;
  }, [accompanimentVolume]);

  function resetPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setPreviewBlob(null);
    setState("idle");
  }

  async function startRecording() {
    onExclusivePlaybackStart?.();
    stopPlayback();
    sourceRef.current?.pause();
    accompanimentRef.current?.pause();
    setError(null);
    setSavedNotice(null);
    resetPreview();
    if (!window.isSecureContext) {
      setError("手机麦克风需要 HTTPS 安全连接，请使用移动端 HTTPS 预览地址。");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("当前浏览器不支持麦克风录音，请使用新版 Safari 或 Chrome。");
      return;
    }
    if (!resourcesReady) {
      setError("伴奏与原唱尚未完整下载，为避免录音中途卡顿，请等待准备完成。");
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
        onRecordingFinished?.();
      };

      recorder.start(250);
      setState("recording");
      onRecordingStart?.();
      const referencePlayer = recordingReference === "source"
        ? sourceRef.current : accompanimentRef.current;
      if (referencePlayer) {
        referencePlayer.currentTime = selectionStart;
        referencePlayer.volume = recordingReference === "source" ? 0.3 : accompanimentVolume;
        await referencePlayer.play();
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
    sourceRef.current?.pause();
  }

  async function uploadRecording() {
    if (!previewBlob) return;
    previewAudioRef.current?.pause();
    sourceRef.current?.pause();
    stopPlayback();
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
    form.set("purpose", purpose);
    form.set("client_duration_seconds", String(selectionEnd - selectionStart));
    form.set("latency_compensation_ms", String(DEFAULT_RECORDING_ADVANCE_MS));
    form.set("manual_offset_ms", String(previewOffsetMs));
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
      if (purpose === "guided_practice") {
        await analyzeTake(created.takeId);
      } else {
        setSavedNotice("清唱叠录已保存，可在已保存音轨中试听和编辑；不会参与演唱分析或长期记忆。");
      }
      resetPreview();
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

  async function playTake(take: RecordingTake) {
    if (playingTakeId === take.takeId) {
      stopPlayback();
      return;
    }
    stopPlayback();
    onExclusivePlaybackStart?.();
    sourceRef.current?.pause();
    previewAudioRef.current?.pause();
    setError(null);
    const audio = new Audio(take.audioUrl);
    singleTakeAudioRef.current = audio;
    audio.volume = Math.min(take.gain ?? 1, 1);
    audio.onended = stopPlayback;
    audio.ontimeupdate = () => {
      setPlaybackProgress(audio.currentTime);
      setPlaybackDuration(audio.duration || take.selectionEndSeconds - take.selectionStartSeconds);
      onTimelineChange?.(take.timelineStartSeconds + audio.currentTime);
    };
    try {
      if (accompanimentRef.current && preparedAccompanimentUrl) {
        accompanimentRef.current.currentTime = take.timelineStartSeconds;
        accompanimentRef.current.volume = accompanimentVolume;
        const offsetSeconds = ((take.latencyCompensationMs ?? 0) + (take.manualOffsetMs ?? 0)) / 1000;
        if (offsetSeconds > 0) audio.currentTime = Math.min(offsetSeconds, audio.duration || offsetSeconds);
        if (offsetSeconds < 0) accompanimentRef.current.currentTime += -offsetSeconds;
        await Promise.all([audio.play(), accompanimentRef.current.play()]);
      } else {
        await audio.play();
      }
      setPlayingTakeId(take.takeId);
      setPlayingLabel(take.displayName);
      onTimelineChange?.(take.timelineStartSeconds);
    } catch {
      stopPlayback();
      setError("浏览器阻止了播放，请再点一次试听。");
    }
  }

  function stopPlayback() {
    const singleAudio = singleTakeAudioRef.current;
    singleTakeAudioRef.current = null;
    if (singleAudio) {
      singleAudio.pause();
      singleAudio.src = "";
    }
    accompanimentRef.current?.pause();
    setPlayingLabel(null);
    setPlayingTakeId(null);
  }

  async function updateTake(takeId: string, update: {
    displayName?: string; gain?: number; manualOffsetMs?: number; muted?: boolean;
  }) {
    try {
      const response = await fetch(`/api/v1/takes/${takeId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(update),
      });
      if (!response.ok) throw new Error("保存音轨设置失败");
      const updated = await response.json() as RecordingTake;
      setTakes((current) => current.map((item) => item.takeId === takeId ? updated : item));
      if (playingTakeId === takeId && update.displayName) setPlayingLabel(updated.displayName);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存音轨设置失败");
    }
  }

  function patchTake(takeId: string, patch: {
    gain?: number; manualOffsetMs?: number; muted?: boolean;
  }, persist = false) {
    setTakes((current) => current.map((item) => item.takeId === takeId
      ? { ...item, ...patch } : item));
    if (persist) void updateTake(takeId, patch);
  }

  async function downloadMixdown() {
    stopPlayback();
    onExclusivePlaybackStart?.();
    setDownloadingMix(true);
    setError(null);
    try {
      const query = new URLSearchParams({
        session_id: sessionId,
        accompaniment_volume: String(accompanimentVolume),
        voice_volume: String(mixVoiceVolume),
      });
      const response = await fetch(`/api/v1/songs/${songId}/mixdown?${query}`);
      if (!response.ok) {
        const payload = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "整体混音生成失败");
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = "VerseViva-整体混音.mp3";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "整体混音下载失败");
    } finally {
      setDownloadingMix(false);
    }
  }

  if (!sentences.length) return null;

  return (
    <section className="recording-studio" aria-label="用户练唱录音">
      <div className="recording-heading">
        <div>
          <h3>选择轨道与演唱范围</h3>
        </div>
        <span className={window.isSecureContext ? "secure-ok" : "secure-warning"}>
          {window.isSecureContext ? "麦克风环境可用" : "需要 HTTPS"}
        </span>
      </div>

      <div className="recording-switch-row"><div className="recording-mode-switch" role="group" aria-label="演唱轨道">
        <button type="button" className={lane === "primary" ? "active" : ""}
          onClick={() => setLane("primary")}>主轨</button>
        <button type="button" className={lane === "secondary" ? "active" : ""}
          onClick={() => setLane("secondary")}>次轨</button>
      </div>

      <div className="recording-mode-switch purpose-switch" role="group" aria-label="录音用途">
        <button type="button" className={purpose === "guided_practice" ? "active" : ""}
          onClick={() => setPurpose("guided_practice")}>分析</button>
        <button type="button" className={purpose === "free_overdub" ? "active" : ""}
          onClick={() => setPurpose("free_overdub")}>纯唱</button>
      </div>
      <div className="recording-mode-switch reference-switch" role="group" aria-label="录制参考音源">
        <button type="button" className={recordingReference === "accompaniment" ? "active" : ""}
          onClick={() => setRecordingReference("accompaniment")}>听伴奏</button>
        <button type="button" className={recordingReference === "source" ? "active" : ""}
          onClick={() => setRecordingReference("source")}>听原唱</button>
      </div></div>
      <p className="recording-purpose-note">{purpose === "guided_practice"
        ? "上传后分析语言技巧，并计入个人练唱记忆。"
        : "自由选择句子并保存为叠录音轨，不分析，也不计入个人练唱记忆。"}</p>

      {editingTake && <section className="current-track-editor">
        <strong>{editingTake.displayName}</strong>
        <input className="playback-progress" type="range" min="0"
          max={Math.max(playbackDuration, 0.01)} step="0.01" value={Math.min(playbackProgress, playbackDuration)}
          readOnly aria-label="当前轨道播放进度" />
        <small>{formatTime(playbackProgress)} / {formatTime(playbackDuration)}</small>
        <div className="current-track-mix">
          <label><span>伴奏音量</span>
            <input type="range" min="0" max="1" step="0.01" value={accompanimentVolume}
              onChange={(event) => setAccompanimentVolume(Number(event.target.value))} /></label>
          <label><span>人声音量</span>
            <input type="range" min="0" max="1" step="0.01"
              value={editingTake.gain ?? 1}
              onChange={(event) => {
                const gain = Number(event.target.value);
                if (editingTake) setTakes((current) => current.map((item) =>
                  item.takeId === editingTake.takeId ? { ...item, gain } : item));
              }}
              onPointerUp={(event) => {
                if (editingTake) void updateTake(editingTake.takeId, { gain: Number(event.currentTarget.value) });
              }} /></label>
          {editingTake && <label><span>人声时间 {editingTake.manualOffsetMs ?? 0} ms</span>
            <input type="range" min="-1000" max="1000" step="10" value={editingTake.manualOffsetMs ?? 0}
              onChange={(event) => {
                const manualOffsetMs = Number(event.target.value);
                setTakes((current) => current.map((item) => item.takeId === editingTake.takeId
                  ? { ...item, manualOffsetMs } : item));
              }} onPointerUp={(event) => void updateTake(editingTake.takeId, {
                manualOffsetMs: Number(event.currentTarget.value),
              })} /></label>}
          <button type="button" className={`mute-button ${editingTake.muted ? "active" : ""}`}
            onClick={() => patchTake(editingTake.takeId, { muted: !editingTake.muted }, true)}>
            {editingTake.muted ? "🔇 取消静音" : "🔊 静音该轨"}
          </button>
        </div>
      </section>}

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
      <p className="headphone-note">建议佩戴耳机，避免伴奏被收录。</p>

      {state === "preview" && previewUrl && <div className="recording-preview preview-editor">
        <audio ref={previewAudioRef} controls src={previewUrl}
          onVolumeChange={(event) => setPreviewVoiceVolume(event.currentTarget.volume)}
          onPlay={(event) => {
            onExclusivePlaybackStart?.();
            stopPlayback();
            sourceRef.current?.pause();
            event.currentTarget.volume = previewVoiceVolume;
            if (previewOffsetMs > 0) event.currentTarget.currentTime = previewOffsetMs / 1000;
            if (accompanimentRef.current && accompanimentUrl) {
              accompanimentRef.current.currentTime = selectionStart + Math.max(0, -previewOffsetMs / 1000);
              accompanimentRef.current.volume = accompanimentVolume;
              void accompanimentRef.current.play().catch(() => undefined);
            }
          }}
          onPause={() => accompanimentRef.current?.pause()}
          onTimeUpdate={(event) => onTimelineChange?.(selectionStart + event.currentTarget.currentTime)}
          onEnded={() => accompanimentRef.current?.pause()} />
        <div className="preview-mix-controls">
          <label><span>伴奏音量</span><input type="range" min="0" max="1" step="0.01"
            value={accompanimentVolume} onChange={(event) => setAccompanimentVolume(Number(event.target.value))} /></label>
          <label><span>人声音量</span><input type="range" min="0" max="1" step="0.01"
            value={previewVoiceVolume} onChange={(event) => setPreviewVoiceVolume(Number(event.target.value))} /></label>
          <label><span>人声时间 {previewOffsetMs > 0 ? "+" : ""}{previewOffsetMs} ms（正值提前）</span>
            <input type="range" min="-1000" max="1000" step="10" value={previewOffsetMs}
              onChange={(event) => setPreviewOffsetMs(Number(event.target.value))} /></label>
        </div>
      </div>}

      <div className="recording-actions">
        {(state === "idle" || state === "requesting" || state === "uploaded") &&
          <button type="button" className="primary-button"
            onClick={() => void startRecording()}
            disabled={state === "requesting" || practiceOptions.length === 0 || !resourcesReady}>
            {!resourcesReady ? "正在准备音频…" : state === "requesting" ? "正在请求麦克风…" : "开始录音"}
          </button>}
        {state === "recording" &&
          <button type="button" className="record-stop-button" onClick={stopRecording}>停止录音</button>}
        {(state === "preview" || state === "uploading") && previewBlob && <>
          <button type="button" className="primary-button analyzing-button"
            disabled={state === "uploading"} onClick={() => void uploadRecording()}>
            {state === "uploading" && <span className="button-spinner" aria-hidden="true" />}
            {state === "uploading"
              ? purpose === "guided_practice" ? "正在上传并分析…" : "正在保存叠录…"
              : purpose === "guided_practice" ? "分析并上传" : "保存清唱叠录"}
          </button>
          <button type="button" className="secondary-button"
            disabled={state === "uploading"} onClick={() => void startRecording()}>重录</button>
          <button type="button" className="text-button cancel-recording-button"
            disabled={state === "uploading"} onClick={resetPreview}>取消</button>
        </>}
      </div>

      {error && <p className="recording-error">{error}</p>}
      {savedNotice && <p className="recording-success">{savedNotice}</p>}
      {state === "recording" && <p className="recording-live">● 正在录制；到片段结尾会自动停止</p>}
      {analyzingTakeId && <p className="recording-live">正在分析，请保持页面打开…</p>}

      {purpose === "guided_practice" && (() => {
        const trackSlotId = `${lane}:${Array.from(new Set(selectedOptions.flatMap(
          (option) => option.sentenceIds,
        ))).join("+")}`;
        const attempt = [...attempts].reverse().find((item) => item.trackSlotId === trackSlotId);
        return attempt
          ? <PracticeFeedback attempt={attempt} memory={memory} sentences={sentences} />
          : null;
      })()}

      {preparedAccompanimentUrl
        ? <audio ref={accompanimentRef} src={preparedAccompanimentUrl} preload="auto"
            onTimeUpdate={(event) => {
              if (state === "recording" || playingLabel) {
                onTimelineChange?.(event.currentTarget.currentTime);
              }
            }} />
        : <p className="recording-warning">当前 Profile 没有 Demucs 伴奏资产，可录音但无法混合伴奏。</p>}
      {preparedSourceUrl && <audio ref={sourceRef} src={preparedSourceUrl} preload="auto"
        onTimeUpdate={(event) => {
          onTimelineChange?.(event.currentTarget.currentTime);
          if (event.currentTarget.currentTime >= selectionEnd) event.currentTarget.pause();
        }} />}

      {takes.length > 0 && <div className="take-history">
        <div className="take-history-heading">
          <h4>已保存音轨</h4>
          <div className="take-history-actions">
            <button type="button" className="primary-button" onClick={() => {
              stopPlayback(); setEditingTakeId(null); setMixOpen(true);
            }}>
              打开多轨对齐与混音
            </button>
            <button type="button" className="secondary-button" disabled={downloadingMix}
              onClick={() => void downloadMixdown()}>
              {downloadingMix ? "正在生成…" : "下载整体混音"}
            </button>
          </div>
        </div>
        {playingLabel && <p className="now-playing">正在播放：{playingLabel}</p>}
        {[...takes].reverse().map((take) => <article key={take.takeId}
          className={`take-row ${take.isCurrent ? "current" : "history"}`}>
          <div className="take-details">
            <input className="track-name-input" value={take.displayName}
              aria-label="音轨名称"
              onChange={(event) => {
                const displayName = event.target.value;
                setTakes((current) => current.map((item) =>
                  item.takeId === take.takeId ? { ...item, displayName } : item));
              }}
              onBlur={(event) => {
                const displayName = event.target.value.trim();
                if (displayName) void updateTake(take.takeId, { displayName });
              }} />
            <small>{formatTime(take.selectionStartSeconds)}–{formatTime(take.selectionEndSeconds)} · {takeLyricSummary(take, sentences)}</small>
            {take.purpose === "free_overdub" && <small className="take-purpose">清唱叠录 · 不参与分析与记忆</small>}
          </div>
          <div className="take-inline-controls">
            <button type="button" className="secondary-button"
              onClick={() => { setEditingTakeId(take.takeId);
                void playTake(take); }}>编辑</button>
            <button type="button" className={`mute-button ${take.muted ? "active" : ""}`}
              aria-label={take.muted ? `取消静音 ${take.displayName}` : `静音 ${take.displayName}`}
              title={take.muted ? "取消静音" : "静音"}
              onClick={() => patchTake(take.takeId, { muted: !take.muted }, true)}>
              {take.muted ? "🔇" : "🔊"}
            </button>
            {take.purpose === "guided_practice" && <button type="button" className="secondary-button"
              disabled={analyzingTakeId === take.takeId}
              onClick={() => void analyzeTake(take.takeId)}>
              {analyzingTakeId === take.takeId ? "分析中…" : "重分析"}
            </button>}
          </div>
        </article>)}
      </div>}
      {mixOpen && <MixTimeline takes={takes} accompanimentUrl={preparedAccompanimentUrl}
        accompanimentVolume={accompanimentVolume} voiceVolume={mixVoiceVolume}
        onAccompanimentVolume={setAccompanimentVolume} onVoiceVolume={setMixVoiceVolume}
        onClose={() => setMixOpen(false)} onPatch={patchTake}
        onTimelineChange={onTimelineChange} />}
    </section>
  );
}

function takeLyricSummary(take: RecordingTake, sentences: RecordingSentence[]) {
  const text = sentences.filter((sentence) => take.sentenceIds.includes(sentence.id))
    .map((sentence) => sentence.lyrics).join(" ").trim();
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length <= 4) return words.join(" ");
  return `${words.slice(0, 2).join(" ")} … ${words.slice(-2).join(" ")}`;
}

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${(seconds - minutes * 60).toFixed(1).padStart(4, "0")}`;
}
