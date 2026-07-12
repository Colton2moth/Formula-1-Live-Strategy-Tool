import type { ReactNode } from "react";

type PanelProps = {
  label: string;
  children: ReactNode;
  prominent?: boolean;
  className?: string;
  headerContent?: ReactNode;
};

export function Panel({ label, children, prominent = false, className = "", headerContent }: PanelProps) {
  return (
    <section className={`panel ${prominent ? "panel--prominent" : ""} ${className}`.trim()}>
      <div className={`panel-header ${prominent ? "panel-header--prominent" : ""}`}>
        <div role="heading" aria-level={2} className="panel-title">
          {label}
        </div>
        {headerContent}
      </div>
      {children}
    </section>
  );
}
