type StatusChipProps = {
  label: string;
  tone?: "red" | "green" | "amber" | "neutral";
};

export function StatusChip({ label, tone = "neutral" }: StatusChipProps) {
  return (
    <span className={`status-chip status-chip--${tone}`}>
      <span className={`status-chip-dot status-chip-dot--${tone}`} aria-hidden="true" />
      {label}
    </span>
  );
}