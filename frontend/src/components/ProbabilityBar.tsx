type ProbabilityBarProps = {
  label: string;
  value: number;
  color?: string;
};

export function ProbabilityBar({ label, value, color = "var(--color-f1-red)" }: ProbabilityBarProps) {
  return (
    <div className="grid gap-1">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-app-text">{label}</span>
        <span className="text-xs font-semibold tabular-nums text-app-muted">{value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-sm bg-app-panelAlt" aria-label={`${label} probability ${value}%`}>
        <div className="h-full rounded-sm" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}