import { useEffect, useMemo, useRef, useState } from "react";

export type TimelineTake = {
  takeId: string;
  displayName: string;
  audioUrl: string;
  selectionStartSeconds: number;
  selectionEndSeconds: number;
  timelineStartSeconds: number;
  latencyCompensationMs?: number;
  manualOffsetMs?: number;
  gain?: number;
  muted?: boolean;
  isCurrent: boolean;
};

type TakePatch = { manualOffsetMs?: number; muted?: boolean; gain?: number };

export function MixTimeline({
  takes,
  accompanimentUrl,
  accompanimentVolume,
  voiceVolume,
  onAccompanimentVolume,
  onVoiceVolume,
  onClose,
  onPatch,
  onTimelineChange,
}: {
  takes: TimelineTake[];
  accompanimentUrl?: string | null;
  accompanimentVolume: number;
  voiceVolume: number;
  onAccompanimentVolume: (value: number) => void;
  onVoiceVolume: (value: number) => void;
  onClose: () => void;
  onPatch: (takeId: string, patch: TakePatch, persist?: boolean) => void;
  onTimelineChange?: (seconds: number) => void;
}) {
  const currentTakes = useMemo(() => takes.filter((take) => take.isCurrent), [takes]);
  const rangeStart = currentTakes.length
    ? Math.min(...currentTakes.map((take) => take.selectionStartSeconds)) : 0;
  const rangeEnd = currentTakes.length
    ? Math.max(...currentTakes.map((take) => take.selectionEndSeconds)) : 0;
  const duration = Math.max(rangeEnd - rangeStart, 0.01);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const animationRef = useRef<number | null>(null);
  const dragRef = useRef<{
    takeId: string; startX: number; originalOffset: number; latestOffset: number; width: number;
  } | null>(null);

  useEffect(() => () => {
    if (animationRef.current !== null) cancelAnimationFrame(animationRef.current);
    const context = contextRef.current;
    if (context && context.state !== "closed") void context.close();
  }, []);

  function stop() {
    if (animationRef.current !== null) cancelAnimationFrame(animationRef.current);
    animationRef.current = null;
    const context = contextRef.current;
    contextRef.current = null;
    if (context && context.state !== "closed") void context.close();
    setPlaying(false);
  }

  async function play() {
    if (playing) {
      stop();
      return;
    }
    if (!accompanimentUrl) {
      setError("当前歌曲没有伴奏，无法进行整体混音。");
      return;
    }
    stop();
    setError(null);
    try {
      const context = new AudioContext();
      contextRef.current = context;
      await context.resume();
      const audibleTakes = currentTakes.filter((take) => !take.muted);
      const urls = [accompanimentUrl, ...audibleTakes.map((take) => take.audioUrl)];
      const buffers = await Promise.all(urls.map(async (url) => {
        const response = await fetch(url);
        if (!response.ok) throw new Error("读取混音资源失败");
        return context.decodeAudioData(await response.arrayBuffer());
      }));
      const startAt = context.currentTime + 0.08;
      const accompaniment = context.createBufferSource();
      const accompanimentGain = context.createGain();
      accompaniment.buffer = buffers[0];
      accompanimentGain.gain.value = accompanimentVolume;
      accompaniment.connect(accompanimentGain).connect(context.destination);
      accompaniment.start(startAt, rangeStart, duration);

      audibleTakes.forEach((take, index) => {
        const source = context.createBufferSource();
        const gain = context.createGain();
        source.buffer = buffers[index + 1];
        gain.gain.value = (take.gain ?? 1) * voiceVolume;
        source.connect(gain).connect(context.destination);
        const correction = ((take.latencyCompensationMs ?? 0) + (take.manualOffsetMs ?? 0)) / 1000;
        const clipStart = take.timelineStartSeconds - correction;
        const delay = Math.max(0, clipStart - rangeStart);
        const bufferOffset = Math.max(0, rangeStart - clipStart);
        const available = Math.min(source.buffer.duration - bufferOffset, duration - delay);
        if (available > 0) source.start(startAt + delay, bufferOffset, available);
      });

      setPlaying(true);
      setProgress(0);
      const tick = () => {
        const elapsed = Math.max(0, context.currentTime - startAt);
        setProgress(Math.min(elapsed, duration));
        onTimelineChange?.(rangeStart + Math.min(elapsed, duration));
        if (elapsed >= duration || context.state === "closed") {
          stop();
          return;
        }
        animationRef.current = requestAnimationFrame(tick);
      };
      animationRef.current = requestAnimationFrame(tick);
    } catch (reason) {
      stop();
      setError(reason instanceof Error ? reason.message : "无法播放整体混音");
    }
  }

  function beginDrag(event: React.PointerEvent<HTMLDivElement>, take: TimelineTake) {
    const width = event.currentTarget.parentElement?.clientWidth ?? 1;
    dragRef.current = {
      takeId: take.takeId,
      startX: event.clientX,
      originalOffset: take.manualOffsetMs ?? 0,
      latestOffset: take.manualOffsetMs ?? 0,
      width,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveDrag(event: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const deltaSeconds = ((event.clientX - drag.startX) / drag.width) * duration;
    const manualOffsetMs = clampOffset(Math.round((drag.originalOffset - deltaSeconds * 1000) / 10) * 10);
    drag.latestOffset = manualOffsetMs;
    onPatch(drag.takeId, { manualOffsetMs });
  }

  function endDrag() {
    const drag = dragRef.current;
    if (!drag) return;
    dragRef.current = null;
    onPatch(drag.takeId, { manualOffsetMs: drag.latestOffset }, true);
  }

  return <div className="mix-modal-backdrop" role="presentation" onMouseDown={(event) => {
    if (event.target === event.currentTarget) onClose();
  }}>
    <section className="mix-modal" role="dialog" aria-modal="true" aria-label="多轨对齐与混音">
      <header className="mix-modal-header">
        <div><p className="eyebrow">多轨混音</p><h3>对齐伴奏与人声</h3></div>
        <button type="button" className="icon-button" aria-label="关闭混音窗口" onClick={onClose}>×</button>
      </header>
      <p className="mix-modal-note">伴奏是固定时间轴；拖动下方人声片段来对齐。中间没有录音的区间仍会完整播放伴奏。</p>
      <div className="mix-ruler">
        <span>{formatTime(rangeStart)}</span><span>{formatTime(rangeStart + duration / 2)}</span><span>{formatTime(rangeEnd)}</span>
      </div>
      <div className="mix-lanes">
        <div className="mix-lane accompaniment-lane">
          <div className="mix-lane-label"><strong>伴奏</strong><small>基准 · 不可拖动</small></div>
          <div className="mix-lane-bed"><div className="wave-pattern accompaniment-wave" /></div>
        </div>
        {currentTakes.map((take) => {
          const correction = ((take.latencyCompensationMs ?? 0) + (take.manualOffsetMs ?? 0)) / 1000;
          const clipStart = take.timelineStartSeconds - correction;
          const clipDuration = Math.max(take.selectionEndSeconds - take.selectionStartSeconds, 0.05);
          const left = ((clipStart - rangeStart) / duration) * 100;
          const width = (clipDuration / duration) * 100;
          return <div className={`mix-lane ${take.muted ? "muted" : ""}`} key={take.takeId}>
            <div className="mix-lane-label">
              <strong>{take.displayName}</strong>
              <small>{take.manualOffsetMs ?? 0} ms</small>
              <button type="button" className={`mute-button ${take.muted ? "active" : ""}`}
                aria-label={take.muted ? `取消静音 ${take.displayName}` : `静音 ${take.displayName}`}
                title={take.muted ? "取消静音" : "静音"}
                onClick={() => onPatch(take.takeId, { muted: !take.muted }, true)}>
                {take.muted ? "🔇" : "🔊"}
              </button>
            </div>
            <div className="mix-lane-bed">
              <div className="mix-clip" style={{ left: `${left}%`, width: `${Math.max(width, 2)}%` }}
                onPointerDown={(event) => beginDrag(event, take)} onPointerMove={moveDrag}
                onPointerUp={endDrag} onPointerCancel={endDrag}>
                <span>{take.displayName}</span><div className="wave-pattern" />
              </div>
            </div>
          </div>;
        })}
        <div className="mix-playhead" style={{ left: `${(progress / duration) * 100}%` }} />
      </div>
      {error && <p className="recording-error">{error}</p>}
      <div className="mix-master-controls">
        <label><span>整体伴奏音量</span><input type="range" min="0" max="1" step="0.01"
          value={accompanimentVolume} onChange={(event) => onAccompanimentVolume(Number(event.target.value))} /></label>
        <label><span>整体人声音量</span><input type="range" min="0" max="1" step="0.01"
          value={voiceVolume} onChange={(event) => onVoiceVolume(Number(event.target.value))} /></label>
      </div>
      <footer className="mix-modal-footer">
        <span>{formatTime(progress)} / {formatTime(duration)}</span>
        <button type="button" className="primary-button" onClick={() => void play()}>
          {playing ? "停止整体试听" : "播放整体混音"}
        </button>
      </footer>
    </section>
  </div>;
}

function clampOffset(value: number) {
  return Math.max(-2000, Math.min(2000, value));
}

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${(seconds - minutes * 60).toFixed(1).padStart(4, "0")}`;
}
