import type { ReactNode } from "react";

type PanelProps = {
  label: string;
  children: ReactNode;
  prominent?: boolean;
};

export function Panel({ label, children, prominent = false }: PanelProps) {
  return (
    <section className={`rounded border bg-app-panel ${prominent ? "border-app-red" : "border-app-line"}`}>
      <div className={`border-b px-4 py-3 ${prominent ? "border-app-red" : "border-app-line"}`}>
        <div role="heading" aria-level={2} className="text-xs font-semibold uppercase tracking-wide text-app-muted">
          {label}
        </div>
      </div>
      {children}
    </section>
  );
}