import { useState, useEffect } from "react";
import type { Exercise } from "../types";
import * as api from "../api/chat";

interface Props {
  onSelectConversation: (id: string) => void;
}

const TYPE_LABELS: Record<string, string> = {
  choice: "选择题",
  fill_blank: "填空题",
  true_false: "判断题",
};

const TYPE_BADGES: Record<string, string> = {
  choice: "📝",
  fill_blank: "✍️",
  true_false: "✅",
};

function ChoiceExercise({ ex }: { ex: Exercise }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [showExplanation, setShowExplanation] = useState(false);

  const isCorrect = selected === ex.answer;

  return (
    <div className="ex-card">
      <div className="ex-question">
        <span className="ex-type-badge">{TYPE_BADGES[ex.question_type]} {TYPE_LABELS[ex.question_type]}</span>
        <span className="ex-subject">{ex.subject}</span>
        <div className="ex-qtext">{ex.question}</div>
      </div>
      <div className="ex-options">
        {ex.options.map((opt) => {
          const letter = opt.charAt(0);
          const selected_ = selected === letter;
          let cls = "ex-option";
          if (checked && selected_) {
            cls += isCorrect ? " ex-correct" : " ex-wrong";
          } else if (checked && letter === ex.answer) {
            cls += " ex-correct";
          } else if (selected_) {
            cls += " ex-selected";
          }
          return (
            <div
              key={letter}
              className={cls}
              onClick={() => { if (!checked) setSelected(letter); }}
            >
              <span className="ex-opt-letter">{letter}</span>
              <span>{opt.slice(3)}</span>
              {checked && letter === ex.answer && <span className="ex-check-mark"> ✓</span>}
              {checked && selected_ && !isCorrect && <span className="ex-cross-mark"> ✗</span>}
            </div>
          );
        })}
      </div>
      {!checked && selected && (
        <button className="ex-check-btn" onClick={() => setChecked(true)}>
          确认答案
        </button>
      )}
      {checked && (
        <div className="ex-result">
          {isCorrect ? (
            <span className="ex-result-correct">✅ 回答正确！</span>
          ) : (
            <span className="ex-result-wrong">❌ 正确答案是 {ex.answer}</span>
          )}
          <button
            className="ex-toggle-explanation"
            onClick={() => setShowExplanation(!showExplanation)}
          >
            {showExplanation ? "▲ 收起解析" : "▼ 查看解析"}
          </button>
          {showExplanation && (
            <div className="ex-explanation">{ex.explanation || "暂无解析"}</div>
          )}
        </div>
      )}
    </div>
  );
}

function GenericExercise({ ex }: { ex: Exercise }) {
  const [showExplanation, setShowExplanation] = useState(false);

  return (
    <div className="ex-card">
      <div className="ex-question">
        <span className="ex-type-badge">{TYPE_BADGES[ex.question_type]} {TYPE_LABELS[ex.question_type]}</span>
        <span className="ex-subject">{ex.subject}</span>
        <div className="ex-qtext">{ex.question}</div>
      </div>
      <button
        className="ex-toggle-explanation"
        onClick={() => setShowExplanation(!showExplanation)}
      >
        {showExplanation ? "▲ 收起答案与解析" : "▼ 查看答案与解析"}
      </button>
      {showExplanation && (
        <div className="ex-explanation">
          {ex.answer && <div className="ex-answer-block"><strong>答案：</strong>{ex.answer}</div>}
          <div>{ex.explanation || "暂无解析"}</div>
        </div>
      )}
    </div>
  );
}

function TrueFalseExercise({ ex }: { ex: Exercise }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [showExplanation, setShowExplanation] = useState(false);

  const isCorrect = selected !== null && ex.answer.includes(selected);

  return (
    <div className="ex-card">
      <div className="ex-question">
        <span className="ex-type-badge">{TYPE_BADGES[ex.question_type]} {TYPE_LABELS[ex.question_type]}</span>
        <span className="ex-subject">{ex.subject}</span>
        <div className="ex-qtext">{ex.question}</div>
      </div>
      <div className="ex-options">
        {["正确", "错误"].map((label) => {
          const key = label === "正确" ? "正确" : "错误";
          const selected_ = selected === key;
          let cls = "ex-option";
          if (checked && selected_) {
            cls += isCorrect ? " ex-correct" : " ex-wrong";
          } else if (checked && ex.answer.includes(key)) {
            cls += " ex-correct";
          } else if (selected_) {
            cls += " ex-selected";
          }
          return (
            <div
              key={key}
              className={cls}
              onClick={() => { if (!checked) setSelected(key); }}
            >
              <span className="ex-opt-letter">{label === "正确" ? "✓" : "✗"}</span>
              <span>{label}</span>
              {checked && ex.answer.includes(key) && <span className="ex-check-mark"> ✓</span>}
              {checked && selected_ && !isCorrect && <span className="ex-cross-mark"> ✗</span>}
            </div>
          );
        })}
      </div>
      {!checked && selected && (
        <button className="ex-check-btn" onClick={() => setChecked(true)}>
          确认答案
        </button>
      )}
      {checked && (
        <div className="ex-result">
          {isCorrect ? (
            <span className="ex-result-correct">✅ 回答正确！</span>
          ) : (
            <span className="ex-result-wrong">❌ 正确答案是「{ex.answer}」</span>
          )}
          <button
            className="ex-toggle-explanation"
            onClick={() => setShowExplanation(!showExplanation)}
          >
            {showExplanation ? "▲ 收起解析" : "▼ 查看解析"}
          </button>
          {showExplanation && (
            <div className="ex-explanation">{ex.explanation || "暂无解析"}</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ExercisePanel({ onSelectConversation }: Props) {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    api.listExercises().then((data) => {
      setExercises(data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  // Group by conversation/subject
  const grouped: Record<string, Exercise[]> = {};
  for (const ex of exercises) {
    const key = ex.subject || ex.conversation_id;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(ex);
  }

  const filterTypes = ["all", "choice", "fill_blank", "true_false"];

  if (loading) {
    return (
      <div className="exercise-panel">
        <div className="ex-panel-header">📝 历史题目练习</div>
        <div className="materials-loading">加载中...</div>
      </div>
    );
  }

  if (exercises.length === 0) {
    return (
      <div className="exercise-panel">
        <div className="ex-panel-header">📝 历史题目练习</div>
        <div className="ex-empty">
          <p>暂无练习题记录</p>
          <p className="ex-empty-hint">使用学习模式对话，系统将自动提取并保存题目</p>
        </div>
      </div>
    );
  }

  const filteredGroups = Object.entries(grouped).map(([key, exs]) => {
    const filtered = filter === "all" ? exs : exs.filter((e) => e.question_type === filter);
    return [key, filtered] as const;
  }).filter(([, exs]) => exs.length > 0);

  return (
    <div className="exercise-panel">
      <div className="ex-panel-header">
        <span>📝 历史题目练习</span>
        <span className="ex-count">{exercises.length} 题</span>
      </div>
      <div className="ex-filter-bar">
        {filterTypes.map((t) => (
          <button
            key={t}
            className={`ex-filter-btn ${filter === t ? "active" : ""}`}
            onClick={() => setFilter(t)}
          >
            {t === "all" ? "全部" : TYPE_LABELS[t]}
          </button>
        ))}
      </div>
      <div className="ex-list">
        {filteredGroups.map(([key, exs]) => (
          <div key={key} className="ex-group">
            <div
              className="ex-group-header"
              onClick={() => {
                const convId = exs[0]?.conversation_id;
                if (convId) onSelectConversation(convId);
              }}
            >
              <span>{key}</span>
              <span className="ex-group-count">{exs.length} 题</span>
            </div>
            {exs.map((ex) => {
              if (ex.question_type === "choice") {
                return <ChoiceExercise key={ex.id} ex={ex} />;
              }
              if (ex.question_type === "true_false") {
                return <TrueFalseExercise key={ex.id} ex={ex} />;
              }
              return <GenericExercise key={ex.id} ex={ex} />;
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
