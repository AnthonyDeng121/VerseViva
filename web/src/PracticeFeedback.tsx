import { useEffect, useState } from "react";

import { lyricsForLane } from "./audioTimeline";
import type { PracticeAttempt, PracticeMemory } from "./RecordingStudio";

type FeedbackSentence = { id: string; lyrics: string };

export function PracticeFeedback({ attempt, memory, sentences }: {
  attempt: PracticeAttempt;
  memory: PracticeMemory | null;
  sentences: FeedbackSentence[];
}) {
  const lane = attempt.trackSlotId.startsWith("secondary:") ? "secondary" : "primary";
  const cards = attempt.sentenceIds.map((sentenceId) => ({
    sentenceId,
    lyrics: lyricsForLane(
      sentences.find((item) => item.id === sentenceId)?.lyrics ?? "所选句子",
      lane,
    ),
    issues: attempt.issues.filter((issue) => issue.sentenceId === sentenceId),
  }));
  const [index, setIndex] = useState(0);
  useEffect(() => setIndex(0), [attempt.attemptId]);
  const card = cards[Math.min(index, Math.max(cards.length - 1, 0))];
  if (!card) return null;
  const issueIds = new Set(card.issues.map((issue) => issue.issueId));
  const recommendations = attempt.recommendations.filter((item) => issueIds.has(item.issueId));
  const comparison = attempt.sentenceComparisons?.[card.sentenceId] ?? attempt.comparison;
  const comparisonLabels = {
    first_attempt: "这是这句的第一遍可靠记录",
    improved: "与这句的上一遍相比有改善",
    unchanged: "与这句的上一遍相比暂未变化",
    regressed: "这句出现了新的重点，可再试一遍",
    insufficient_data: "本次证据不足，未计入趋势",
  };
  return <section className="practice-feedback" aria-live="polite">
    <div className="practice-feedback-heading">
      <button className="hint-arrow" type="button" aria-label="上一句"
        disabled={index === 0} onClick={() => setIndex((value) => value - 1)}>‹</button>
      <div className="practice-feedback-card">
        <p className="eyebrow">本次建议 · {index + 1}/{cards.length}</p>
        <h4>{card.lyrics}</h4>
        <p className="feedback-comparison">{attempt.status === "analyzed"
          ? comparisonLabels[comparison.result] : "暂不下结论"}</p>
        {attempt.status === "failed"
          ? <p className="recording-error">{attempt.insufficientReason ?? "分析服务暂时不可用，请稍后重试。"}</p>
          : attempt.status === "insufficient_data"
          ? <p className="recording-warning">{attempt.insufficientReason ?? "本次录音不足以可靠判断，请重录。"}</p>
          : recommendations.length > 0
            ? <ol className="practice-recommendations">
                {recommendations.map((item) => <li key={item.issueId}>
                  <strong>{item.headline}</strong>
                  <p>{item.observation}</p>
                  <p className="practice-action">下一遍：{item.action}</p>
                </li>)}
              </ol>
            : <p className="practice-success">这句话的现有目标没有发现可靠差异。</p>}
      </div>
      <button className="hint-arrow" type="button" aria-label="下一句"
        disabled={index >= cards.length - 1} onClick={() => setIndex((value) => value + 1)}>›</button>
    </div>
    {memory && <p className="feedback-memory-count">
      练唱记忆：{memory.reliableAttempts}/{memory.totalAttempts} 次可靠分析
    </p>}
  </section>;
}
