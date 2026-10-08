import type { PracticeAttempt, PracticeMemory } from "./RecordingStudio";

export function PracticeFeedback({ attempt, memory }: {
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
        <h4>{attempt.status === "analyzed"
          ? comparisonLabels[attempt.comparison.result] : "暂不下结论"}</h4>
      </div>
      {memory && <span>{memory.reliableAttempts}/{memory.totalAttempts} 次可靠分析</span>}
    </div>
    {attempt.status === "failed"
      ? <p className="recording-error">{attempt.insufficientReason ?? "分析服务暂时不可用，请稍后重试。"}</p>
      : attempt.status === "insufficient_data"
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
