type StatusChipProps = {
  label: string;
  tone?: "red" | "green" | "neutral";
};

export function StatusChip({ label, tone = "neutral" }: StatusChipProps) {
  return <span className={`status-chip status-chip--${tone}`}>{label}</span>;
}