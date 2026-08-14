import type { CSSProperties } from "react";

type ProbabilityBarProps = {
  label: string;
  value: number;
  color?: string;
};

export function ProbabilityBar({ label, value, color = "var(--color-f1-red)" }: ProbabilityBarProps) {
  const fillStyle = { "--probability-value": `${value}%`, "--probability-colour": color } as CSSProperties;
  return (
    <div className="probability-bar">
      <div className="probability-bar-header">
        <span className="probability-bar-label">{label}</span>
        <span className="probability-bar-value">{value}%</span>
      </div>
      <div className="probability-bar-track" aria-label={`${label} probability ${value}%`}>
        <div className="probability-bar-fill" style={fillStyle} />
      </div>
    </div>
  );
}
