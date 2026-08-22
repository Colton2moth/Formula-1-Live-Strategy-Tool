import type { ReactNode } from "react";

type PanelProps = {
  label: string;
  children: ReactNode;
  className?: string;
  headerContent?: ReactNode;
  icon?: string;
};

export function Panel({ label, children, className = "", headerContent, icon }: PanelProps) {
  return (
    <section className={`panel ${className}`.trim()}>
      <div className="panel-header">
        <div role="heading" aria-level={2} className="panel-title">
          {icon ? (
            <span className="material-symbols-rounded panel-title-icon" aria-hidden="true">
              {icon}
            </span>
          ) : null}
          <span>{label}</span>
        </div>
        {headerContent}
      </div>
      {children}
    </section>
  );
}
