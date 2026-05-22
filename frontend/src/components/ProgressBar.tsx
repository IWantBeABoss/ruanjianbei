interface Props {
  current: number;
  total: number;
  label: string;
}

export default function ProgressBar({ current, total, label }: Props) {
  const pct = Math.round((current / total) * 100);

  return (
    <div className="progress-bar-container">
      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-bar-label">
        <span className="progress-step">{current}/{total}</span>
        <span>{label}...</span>
      </div>
    </div>
  );
}
