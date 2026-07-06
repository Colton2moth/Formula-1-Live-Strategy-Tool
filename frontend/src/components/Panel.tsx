import type { ReactNode } from "react";

type PanelProps = {
  label: string;
  children: ReactNode;
  prominent?: boolean;
};

export function Panel({ label, children, prominent = false }: PanelProps) {
  return (
    <section className={`panel ${prominent ? "panel--prominent" : ""}`}>
      <div className={`panel-header ${prominent ? "panel-header--prominent" : ""}`}>
        <div role="heading" aria-level={2} className="panel-title">
          {label}
        </div>
      </div>
      {children}
    </section>
  );
}