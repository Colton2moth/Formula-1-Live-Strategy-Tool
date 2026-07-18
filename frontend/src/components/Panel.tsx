import type { ReactNode } from "react";

type PanelProps = {
  label: string;
  children: ReactNode;
  className?: string;
  headerContent?: ReactNode;
};

export function Panel({ label, children, className = "", headerContent }: PanelProps) {
  return (
    <section className={`panel ${className}`.trim()}>
      <div className="panel-header">
        <div role="heading" aria-level={2} className="panel-title">
          {label}
        </div>
        {headerContent}
      </div>
      {children}
    </section>
  );
}
