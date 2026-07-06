type StatusChipProps = {
  label: string;
  tone?: "red" | "green" | "neutral";
};

export function StatusChip({ label, tone = "neutral" }: StatusChipProps) {
  const toneClass = tone === "red" ? "border-app-red text-white" : tone === "green" ? "border-emerald-500 text-emerald-200" : "border-app-line text-app-muted";
  return <span className={`inline-flex items-center rounded-sm border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${toneClass}`}>{label}</span>;
}